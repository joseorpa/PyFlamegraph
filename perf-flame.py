#!/usr/bin/env python3
"""
perf-flame.py - All-in-one script with PNG and SVG support
Usage: perf script | python3 perf-flame.py --format png > output.png
       perf script | python3 perf-flame.py --format svg > output.svg
"""
import sys
import re
import os
import hashlib
import argparse
import io
import struct
import zlib
from collections import defaultdict

def collapse_perf_stacks(input_data, include_unknown=False, include_comm=False):
    """Collapse identical stacks
    
    Args:
        input_data: Raw perf script output
        include_unknown: Include [unknown] frames with binary info
        include_comm: Include process/command name at base of stack
    """
    stacks = {}
    lines = input_data.strip().split('\n')
    current_stack = []
    current_comm = None
    
    for line in lines:
        if not line.strip() or line.startswith('#'):
            continue
        
        # Match header line: "comm pid [cpu] timestamp: event"
        header_match = re.match(r'^(\S+)\s+(\d+)\s+\[(\d+)\]\s+([\d.]+):', line)
        if header_match:
            if current_stack:
                # Add process name at the base of the stack if requested
                if include_comm and current_comm:
                    current_stack.insert(0, current_comm)
                stack_str = ';'.join(current_stack)
                stacks[stack_str] = stacks.get(stack_str, 0) + 1
            current_stack = []
            current_comm = header_match.group(1)  # Extract process name
            continue
        
        # Match function name and binary path: "address func (binary)"
        func_match = re.search(r'\s+([a-f0-9]+)\s+(.+?)\s+\(([^)]+)\)', line)
        if func_match:
            func = func_match.group(2).strip()
            binary = func_match.group(3).strip()
            # Skip unknown/invalid frames unless explicitly included
            if func and func != '-' and func != 'unknown':
                if func == '[unknown]':
                    if include_unknown:
                        # Include binary info for unknown symbols
                        # Extract just the filename from the path for brevity
                        binary_name = os.path.basename(binary)
                        func = f'[unknown:{binary_name}]'
                        current_stack.insert(0, func)
                else:
                    current_stack.insert(0, func)
    
    if current_stack:
        # Add process name at the base of the stack if requested
        if include_comm and current_comm:
            current_stack.insert(0, current_comm)
        stack_str = ';'.join(current_stack)
        stacks[stack_str] = stacks.get(stack_str, 0) + 1
    
    return stacks

def build_flame_tree(stacks):
    """Build a tree structure from collapsed stacks for flamegraph rendering"""
    root = {'name': 'all', 'value': 0, 'children': {}}
    
    for stack_str, count in stacks.items():
        frames = stack_str.split(';')
        node = root
        node['value'] += count
        
        for frame in frames:
            if frame not in node['children']:
                node['children'][frame] = {'name': frame, 'value': 0, 'children': {}}
            node = node['children'][frame]
            node['value'] += count
    
    return root

def flatten_tree(node, depth=0, x_offset=0, total_samples=1, min_samples=0, max_depth=None):
    """Flatten tree into list of rectangles for rendering"""
    rects = []
    
    if node['value'] < min_samples:
        return rects
    
    # Limit depth if specified
    if max_depth is not None and depth > max_depth:
        return rects
    
    width = node['value'] / total_samples
    
    if depth > 0:  # Skip root node
        rects.append({
            'name': node['name'],
            'depth': depth - 1,
            'x': x_offset,
            'width': width,
            'samples': node['value']
        })
    
    # Sort children by value (descending) for better layout - largest first
    sorted_children = sorted(node['children'].values(), key=lambda c: -c['value'])
    
    child_x = x_offset
    for child in sorted_children:
        child_rects = flatten_tree(child, depth + 1, child_x, total_samples, min_samples, max_depth)
        rects.extend(child_rects)
        child_x += child['value'] / total_samples
    
    return rects

def get_flame_color(name):
    """Generate warm flame colors based on function name hash"""
    h = hashlib.md5(name.encode()).hexdigest()
    hash_val = int(h[:8], 16)
    
    # Warm color palette (reds, oranges, yellows) - more vibrant
    r = 205 + (hash_val % 50)
    g = 60 + (hash_val >> 8) % 140
    b = 25 + (hash_val >> 16) % 40
    
    return (r, g, b)

def get_flame_color_hex(name):
    """Generate warm flame colors as hex string"""
    r, g, b = get_flame_color(name)
    return f'#{r:02x}{g:02x}{b:02x}'

def hash_string(s):
    h = hashlib.md5(s.encode()).hexdigest()
    return int(h, 16)

def generate_png(stacks, title='CPU Flame Graph', min_pct=1.0, max_depth=None):
    """Generate PNG flamegraph using PIL if available"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        return _generate_png_pil(stacks, title, min_pct, max_depth)
    except ImportError:
        return _generate_png_fallback(stacks, title)

def _generate_png_pil(stacks, title, min_pct=1.0, max_depth=None):
    from PIL import Image, ImageDraw, ImageFont
    
    total = sum(stacks.values())
    min_samples = int(total * min_pct / 100)
    
    # Build flame tree and flatten to rectangles
    tree = build_flame_tree(stacks)
    rects = flatten_tree(tree, 0, 0, total, min_samples, max_depth)
    
    if not rects:
        rects = [{'name': 'no data', 'depth': 0, 'x': 0, 'width': 1, 'samples': 0}]
    
    # Find max depth
    actual_max_depth = max(r['depth'] for r in rects) + 1
    
    # Collect top functions for legend (unique by name, sorted by samples)
    func_samples = {}
    for rect in rects:
        name = rect['name']
        if name not in func_samples or rect['samples'] > func_samples[name]:
            func_samples[name] = rect['samples']
    
    top_functions = sorted(func_samples.items(), key=lambda x: -x[1])[:25]
    
    # Layout parameters - WIDER for readability
    frame_height = 24
    margin = 30
    header_height = 60
    legend_height = 20 + len(top_functions) * 18  # Space for legend
    
    width = 2400  # Wider image
    graph_height = actual_max_depth * frame_height
    height = header_height + graph_height + legend_height + 40
    
    img = Image.new('RGB', (width, height), color=(250, 250, 250))
    draw = ImageDraw.Draw(img)
    
    # Try to load fonts - LARGER sizes
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
        label_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
        small_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 11)
        legend_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 11)
    except (OSError, IOError):
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
            label_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
            legend_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        except (OSError, IOError):
            title_font = ImageFont.load_default()
            label_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
            legend_font = ImageFont.load_default()
    
    # Draw title
    draw.text((margin, 18), title, fill=(30, 30, 30), font=title_font)
    
    # Draw subtitle
    subtitle = f"Samples: {total:,} | Functions >= {min_pct}% | Depth: {actual_max_depth} levels"
    draw.text((width - margin - 420, 22), subtitle, fill=(100, 100, 100), font=small_font)
    
    # Draw frames (bottom-up: root at bottom, leaves at top)
    graph_width = width - 2 * margin
    graph_bottom = header_height + graph_height
    
    for rect in rects:
        # Calculate position (inverted: depth 0 at bottom)
        y = graph_bottom - (rect['depth'] + 1) * frame_height
        x = margin + rect['x'] * graph_width
        w = rect['width'] * graph_width
        
        if w < 2:
            continue
        
        color = get_flame_color(rect['name'])
        
        # Draw rectangle with slight border
        draw.rectangle([x, y, x + w - 1, y + frame_height - 2], 
                       fill=color, outline=(255, 255, 255))
        
        # Draw label if wide enough - more generous character limit
        if w > 50:
            # Calculate chars that fit (approx 7px per char)
            max_chars = int(w / 7)
            label = rect['name'][:max_chars]
            if len(rect['name']) > max_chars and max_chars > 3:
                label = label[:-2] + '..'
            
            # Use black or white text depending on background brightness
            brightness = (color[0] * 299 + color[1] * 587 + color[2] * 114) / 1000
            text_color = (20, 20, 20) if brightness > 140 else (255, 255, 255)
            
            draw.text((x + 4, y + 5), label, fill=text_color, font=label_font)
    
    # Draw legend section
    legend_y = graph_bottom + 25
    draw.text((margin, legend_y - 5), "Top Functions:", fill=(50, 50, 50), font=title_font)
    
    # Draw legend in 2 columns
    col_width = (width - 2 * margin) // 2
    
    for i, (func_name, samples) in enumerate(top_functions):
        col = i % 2
        row = i // 2
        x = margin + col * col_width
        y = legend_y + 25 + row * 18
        
        # Draw color box
        color = get_flame_color(func_name)
        draw.rectangle([x, y + 2, x + 12, y + 14], fill=color, outline=(200, 200, 200))
        
        # Draw function name and percentage
        pct = (samples / total) * 100
        # Truncate long names for legend (show more chars)
        display_name = func_name[:80] if len(func_name) <= 80 else func_name[:77] + '...'
        legend_text = f"{display_name} ({pct:.1f}%)"
        draw.text((x + 18, y), legend_text, fill=(40, 40, 40), font=legend_font)
    
    b = io.BytesIO()
    img.save(b, format='PNG')
    return b.getvalue()

def _generate_png_fallback(stacks, title):
    """Fallback PNG generation without PIL"""
    width, height = 1800, 400
    png_header = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr) & 0xffffffff
    ihdr_chunk = struct.pack('>I', 13) + b'IHDR' + ihdr + struct.pack('>I', ihdr_crc)
    
    # Create gradient background
    rows = []
    for y in range(height):
        row = b'\x00'  # Filter byte
        for x in range(width):
            # Warm gradient from orange to red
            r = min(255, 200 + (y * 55 // height))
            g = max(50, 150 - (y * 100 // height))
            b = 30
            row += bytes([r, g, b])
        rows.append(row)
    
    raw_data = b''.join(rows)
    compressed = zlib.compress(raw_data, 9)
    idat_crc = zlib.crc32(b'IDAT' + compressed) & 0xffffffff
    idat_chunk = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)
    iend_crc = zlib.crc32(b'IEND') & 0xffffffff
    iend_chunk = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
    return png_header + ihdr_chunk + idat_chunk + iend_chunk

def generate_svg(stacks, title='CPU Flame Graph', min_pct=1.0, max_depth=None):
    """Generate SVG flamegraph"""
    total = sum(stacks.values())
    min_samples = int(total * min_pct / 100)
    
    # Build flame tree and flatten to rectangles
    tree = build_flame_tree(stacks)
    rects = flatten_tree(tree, 0, 0, total, min_samples, max_depth)
    
    if not rects:
        rects = [{'name': 'no data', 'depth': 0, 'x': 0, 'width': 1, 'samples': 0}]
    
    # Find max depth
    actual_max_depth = max(r['depth'] for r in rects) + 1
    
    # Layout parameters - LARGER for readability
    frame_height = 24
    margin = 30
    header_height = 60
    footer_height = 40
    
    width = 1800
    height = header_height + actual_max_depth * frame_height + footer_height
    graph_width = width - 2 * margin
    
    svg_parts = []
    svg_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    svg_parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    
    # Styles - LARGER fonts
    svg_parts.append('''<defs>
    <style>
      .frame { transition: opacity 0.1s; }
      .frame:hover { stroke: #000; stroke-width: 2; cursor: pointer; opacity: 0.8; }
      .label { font-family: ui-monospace, "SF Mono", Menlo, Monaco, monospace; font-size: 13px; pointer-events: none; }
      .title { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 20px; font-weight: bold; }
      .subtitle { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 11px; fill: #666; }
    </style>
  </defs>''')
    
    # Background
    svg_parts.append(f'<rect width="{width}" height="{height}" fill="#fafafa"/>')
    
    # Title
    svg_parts.append(f'<text x="{margin}" y="38" class="title">{title}</text>')
    subtitle = f"Samples: {total:,} | Functions >= {min_pct}% | Depth: {actual_max_depth} levels"
    svg_parts.append(f'<text x="{width - margin - 350}" y="35" class="subtitle">{subtitle}</text>')
    
    # Draw frames
    for rect in rects:
        # Calculate position (inverted: depth 0 at bottom)
        y = height - footer_height - (rect['depth'] + 1) * frame_height
        x = margin + rect['x'] * graph_width
        w = rect['width'] * graph_width
        
        if w < 2:
            continue
        
        color = get_flame_color_hex(rect['name'])
        pct = (rect['samples'] / total) * 100
        
        # Escape special characters for XML
        safe_name = rect['name'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
        tooltip = f"{safe_name} ({rect['samples']:,} samples, {pct:.2f}%)"
        
        svg_parts.append(f'<g>')
        svg_parts.append(f'  <title>{tooltip}</title>')
        svg_parts.append(f'  <rect class="frame" x="{x:.1f}" y="{y}" width="{w:.1f}" height="{frame_height - 2}" fill="{color}" rx="2"/>')
        
        # Add label if wide enough
        if w > 35:
            # Calculate max characters that fit
            max_chars = int(w / 8)
            label = safe_name[:max_chars]
            if len(rect['name']) > max_chars and max_chars > 3:
                label = safe_name[:max_chars-2] + '..'
            
            # Determine text color based on background brightness
            r, g, b = get_flame_color(rect['name'])
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            text_color = '#111' if brightness > 140 else '#fff'
            
            svg_parts.append(f'  <text class="label" x="{x + 4:.1f}" y="{y + 16}" fill="{text_color}">{label}</text>')
        
        svg_parts.append('</g>')
    
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)

def main():
    parser = argparse.ArgumentParser(
        description='Generate CPU Flamegraph from perf data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  perf script | python3 perf-flame.py > flamegraph.svg
  perf script | python3 perf-flame.py --min-pct 2 --max-depth 20 > flamegraph.svg
  perf script | python3 perf-flame.py --format png --include-unknown > flamegraph.png
        '''
    )
    parser.add_argument('--format', choices=['png', 'svg'], default='svg',
                        help='Output format (default: svg)')
    parser.add_argument('--title', default='CPU Flame Graph',
                        help='Title for the flamegraph')
    parser.add_argument('--min-pct', type=float, default=1.0,
                        help='Minimum percentage threshold to include a function (default: 1.0)')
    parser.add_argument('--max-depth', type=int, default=None,
                        help='Maximum stack depth to display (default: unlimited)')
    parser.add_argument('--include-unknown', action='store_true',
                        help='Include [unknown] frames (usually noise from missing symbols)')
    parser.add_argument('--include-comm', action='store_true',
                        help='Include process/command name at base of each stack (e.g., ovnkube, ovs-vswitchd)')
    args = parser.parse_args()
    
    data = sys.stdin.read()
    stacks = collapse_perf_stacks(data, include_unknown=args.include_unknown, include_comm=args.include_comm)
    
    if not stacks:
        sys.stderr.write("Warning: No stacks found in input\n")
    
    if args.format == 'png':
        output = generate_png(stacks, args.title, args.min_pct, args.max_depth)
        sys.stdout.buffer.write(output)
    else:
        output = generate_svg(stacks, args.title, args.min_pct, args.max_depth)
        print(output)

if __name__ == '__main__':
    main()
