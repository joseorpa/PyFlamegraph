#!/usr/bin/env python3
"""
perf-flame.py - All-in-one script with PNG and SVG support
Usage: perf script | python3 perf-flame.py --format png > output.png
       perf script | python3 perf-flame.py --format svg > output.svg
"""
import sys
import re
import hashlib
import argparse
import io
import struct
import zlib

def collapse_perf_stacks(input_data):
    """Collapse identical stacks"""
    stacks = {}
    lines = input_data.strip().split('\n')
    current_stack = []
    
    for line in lines:
        if not line.strip() or line.startswith('#'):
            continue
        
        if re.match(r'^(\S+)\s+(\d+)\s+\[(\d+)\]\s+([\d.]+):', line):
            if current_stack:
                stack_str = ';'.join(current_stack)
                stacks[stack_str] = stacks.get(stack_str, 0) + 1
            current_stack = []
            continue
        
        func_match = re.search(r'\s+([a-f0-9]+)\s+(.+?)\s+\(', line)
        if func_match:
            func = func_match.group(2).strip()
            if func and func != '-' and func != 'unknown':
                current_stack.insert(0, func)
    
    if current_stack:
        stack_str = ';'.join(current_stack)
        stacks[stack_str] = stacks.get(stack_str, 0) + 1
    
    return stacks

def hash_string(s):
    h = hashlib.md5(s.encode()).hexdigest()
    return int(h, 16)

def generate_png(stacks, title='CPU Flame Graph', min_pct=0.5):
    """Generate PNG using PIL if available"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        return _generate_png_pil(stacks, title, min_pct)
    except ImportError:
        return _generate_png_fallback(stacks, title)

def _generate_png_pil(stacks, title, min_pct=0.5):
    from PIL import Image, ImageDraw, ImageFont
    
    total = sum(stacks.values())
    
    # Filter stacks: only keep those above minimum percentage threshold
    filtered_stacks = {k: v for k, v in stacks.items() 
                       if (v / total) * 100 >= min_pct}
    
    # Sort by count descending and limit to top 50 for readability
    sorted_stacks = sorted(filtered_stacks.items(), key=lambda x: -x[1])[:50]
    
    # Layout parameters - larger for better readability
    bar_height = 28
    bar_spacing = 32
    margin = 30
    header_height = 80
    
    width = 1600
    height = header_height + len(sorted_stacks) * bar_spacing + margin
    
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    colors = ['#E74C3C', '#3498DB', '#2ECC71', '#F39C12', '#9B59B6',
              '#1ABC9C', '#E67E22', '#34495E', '#16A085', '#C0392B']
    color_tuples = [tuple(int(c.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) for c in colors]
    
    # Try to load a larger font, fall back to default
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        label_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    except (OSError, IOError):
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            label_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except (OSError, IOError):
            title_font = ImageFont.load_default()
            label_font = ImageFont.load_default()
    
    # Draw title
    draw.text((margin, 20), title, fill=(0, 0, 0), font=title_font)
    draw.text((margin, 50), f"Showing top {len(sorted_stacks)} stacks (>= {min_pct}% of samples)", 
              fill=(100, 100, 100), font=label_font)
    
    y = header_height
    
    for stack, count in sorted_stacks:
        pct = (count / total) * 100
        w = (count / total) * (width - 2 * margin - 120)  # Leave space for percentage
        func = stack.split(';')[-1]
        color = color_tuples[hash_string(func) % len(color_tuples)]
        
        # Draw bar
        draw.rectangle([margin, y, margin + w, y + bar_height], 
                       fill=color, outline=(255, 255, 255))
        
        # Draw function name inside bar if it fits
        label = func[:50]  # Show more characters
        if w > 100:
            draw.text((margin + 8, y + 6), label, fill=(255, 255, 255), font=label_font)
        
        # Draw percentage on the right side
        pct_text = f"{pct:.1f}% ({count})"
        draw.text((width - margin - 100, y + 6), pct_text, fill=(60, 60, 60), font=label_font)
        
        y += bar_spacing
    
    b = io.BytesIO()
    img.save(b, format='PNG')
    return b.getvalue()

def _generate_png_fallback(stacks, title):
    width, height = 1400, 100
    png_header = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr) & 0xffffffff
    ihdr_chunk = struct.pack('>I', 13) + b'IHDR' + ihdr + struct.pack('>I', ihdr_crc)
    raw_data = b'\x00' * (width * height * 3)
    compressed = zlib.compress(raw_data)
    idat_crc = zlib.crc32(b'IDAT' + compressed) & 0xffffffff
    idat_chunk = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)
    iend_crc = zlib.crc32(b'IEND') & 0xffffffff
    iend_chunk = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
    return png_header + ihdr_chunk + idat_chunk + iend_chunk

def generate_svg(stacks, title='CPU Flame Graph', min_pct=0.5):
    """Generate SVG"""
    total = sum(stacks.values())
    
    # Filter stacks: only keep those above minimum percentage threshold
    filtered_stacks = {k: v for k, v in stacks.items() 
                       if (v / total) * 100 >= min_pct}
    
    # Sort by count descending and limit to top 50 for readability
    sorted_stacks = sorted(filtered_stacks.items(), key=lambda x: -x[1])[:50]
    
    # Layout parameters
    bar_height = 24
    bar_spacing = 28
    margin = 30
    header_height = 90
    
    width = 1400
    height = header_height + len(sorted_stacks) * bar_spacing + margin
    
    colors = ['#E74C3C', '#3498DB', '#2ECC71', '#F39C12', '#9B59B6',
              '#1ABC9C', '#E67E22', '#34495E', '#16A085', '#C0392B']
    
    svg = '<?xml version="1.0" encoding="UTF-8"?>\n'
    svg += f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">\n'
    svg += '<style>text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }</style>\n'
    svg += f'<rect width="{width}" height="{height}" fill="white"/>\n'
    svg += f'<text x="{margin}" y="35" font-size="22" font-weight="bold">{title}</text>\n'
    svg += f'<text x="{margin}" y="60" font-size="13" fill="#666">Showing top {len(sorted_stacks)} stacks (>= {min_pct}% of samples)</text>\n'
    
    y = header_height
    for stack, count in sorted_stacks:
        pct = (count / total) * 100
        w = (count / total) * (width - 2 * margin - 120)  # Leave space for percentage
        func = stack.split(';')[-1]
        color = colors[hash_string(func) % len(colors)]
        
        # Draw bar
        svg += f'<rect x="{margin}" y="{y}" width="{w}" height="{bar_height}" fill="{color}" rx="3"/>\n'
        
        # Draw function name inside bar if it fits
        if w > 80:
            label = func[:60]  # Show more characters
            svg += f'<text x="{margin + 8}" y="{y + 16}" fill="white" font-size="13">{label}</text>\n'
        
        # Draw percentage on the right side
        pct_text = f"{pct:.1f}% ({count})"
        svg += f'<text x="{width - margin - 90}" y="{y + 16}" fill="#444" font-size="12">{pct_text}</text>\n'
        
        y += bar_spacing
    
    svg += '</svg>'
    return svg

def main():
    parser = argparse.ArgumentParser(description='Perf to Flamegraph')
    parser.add_argument('--format', choices=['png', 'svg'], default='png',
                        help='Output format (default: png)')
    parser.add_argument('--title', default='CPU Flame Graph',
                        help='Title for the flamegraph')
    parser.add_argument('--min-pct', type=float, default=0.5,
                        help='Minimum percentage threshold to include a stack (default: 0.5)')
    args = parser.parse_args()
    
    data = sys.stdin.read()
    stacks = collapse_perf_stacks(data)
    
    if args.format == 'png':
        output = generate_png(stacks, args.title, args.min_pct)
        sys.stdout.buffer.write(output)
    else:
        output = generate_svg(stacks, args.title, args.min_pct)
        print(output)

if __name__ == '__main__':
    main()
