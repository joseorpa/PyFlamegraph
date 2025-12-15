#!/usr/bin/env python3
"""
flamegraph.py - Python replacement for flamegraph.pl
Generates PNG from collapsed stacks
"""
import sys
import hashlib
import struct
import zlib
import io

def read_folded_stacks(data):
    """Parse folded stack format"""
    stacks = {}
    for line in data.strip().split('\n'):
        if not line.strip():
            continue
        parts = line.rsplit(' ', 1)
        if len(parts) == 2:
            stack, count = parts[0], int(parts[1])
            stacks[stack] = count
    return stacks

def hash_string(s):
    """Generate hash for consistent coloring"""
    h = hashlib.md5(s.encode()).hexdigest()
    return int(h, 16)

def generate_png(stacks, title='Flame Graph'):
    """Generate PNG visualization"""
    try:
        from PIL import Image, ImageDraw
        return generate_png_pil(stacks, title)
    except ImportError:
        return generate_png_fallback(stacks, title)

def generate_png_pil(stacks, title):
    """Generate PNG using Pillow (PIL)"""
    from PIL import Image, ImageDraw
    
    width, height = 1400, min(3000, len(stacks) * 18 + 120)
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    colors = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
        '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B88B', '#A9DFBF',
        '#F38181', '#AA96DA', '#FCBAD3', '#A8D8EA', '#FFE66D'
    ]
    
    # Convert hex colors to RGB tuples
    color_tuples = [tuple(int(c.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) for c in colors]
    
    draw.text((20, 20), title, fill=(0, 0, 0))
    
    total = sum(stacks.values())
    y_offset = 100
    max_frames = (height - 120) // 18
    
    for i, (stack, count) in enumerate(sorted(stacks.items(), key=lambda x: -x[1])):
        if i >= max_frames:
            break
        
        frame_width = (count / total) * (width - 40)
        frames = stack.split(';')
        top_func = frames[-1] if frames else 'unknown'
        color_idx = h
