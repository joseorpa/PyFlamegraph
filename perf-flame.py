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

def generate_png(stacks, title='CPU Flame Graph'):
    """Generate PNG using PIL if available"""
    try:
        from PIL import Image, ImageDraw
        return _generate_png_pil(stacks, title)
    except ImportError:
        return _generate_png_fallback(stacks, title)

def _generate_png_pil(stacks, title):
    from PIL import Image, ImageDraw
    
    width, height = 1400, min(3000, len(stacks) * 18 + 120)
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
              '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B88B', '#A9DFBF']
    color_tuples = [tuple(int(c.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) for c in colors]
    
    draw.text((20, 20), title, fill=(0, 0, 0))
    
    total = sum(stacks.values())
    y = 100
    
    for stack, count in sorted(stacks.items(), key=lambda x: -x[1])[:200]:
        w = (count / total) * (width - 40)
        func = stack.split(';')[-1]
        color = color_tuples[hash_string(func) % len(color_tuples)]
        draw.rectangle([20, y, 20+w, y+16], fill=color, outline=(255, 255, 255))
        if w > 40:
            draw.text((24, y+2), func[:35], fill=(255, 255, 255))
        y += 18
        if y > height - 20:
            break
    
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

def generate_svg(stacks, title='CPU Flame Graph'):
    """Generate SVG"""
    width, height = 1200, min(2000, len(stacks) * 15 + 100)
    total = sum(stacks.values())
    
    svg = '<?xml version="1.0" encoding="UTF-8"?>\n'
    svg += f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">\n'
    svg += f'<rect width="{width}" height="{height}" fill="white"/>\n'
    svg += f'<text x="20" y="40" font-size="20" font-weight="bold">{title}</text>\n'
    
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
              '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B88B', '#A9DFBF']
    
    y = 80
    for stack, count in sorted(stacks.items(), key=lambda x: -x[1])[:500]:
        w = (count / total) * (width - 40)
        func = stack.split(';')[-1]
        color = colors[hash_string(func) % len(colors)]
        pct = (count / total) * 100
        svg += f'<rect x="20" y="{y}" width="{w}" height="14" fill="{color}" stroke="white"/>\n'
        if w > 30:
            svg += f'<text x="24" y="{y+10}" fill="white" font-size="11">{func[:20]}</text>\n'
        y += 15
        if y > height - 20:
            break
    
    svg += '</svg>'
    return svg

def main():
    parser = argparse.ArgumentParser(description='Perf to Flamegraph')
    parser.add_argument('--format', choices=['png', 'svg'], default='png')
    parser.add_argument('--title', default='CPU Flame Graph')
    args = parser.parse_args()
    
    data = sys.stdin.read()
    stacks = collapse_perf_stacks(data)
    
    if args.format == 'png':
        output = generate_png(stacks, args.title)
        sys.stdout.buffer.write(output)
    else:
        output = generate_svg(stacks, args.title)
        print(output)

if __name__ == '__main__':
    main()
