#!/usr/bin/env python3
"""
stackcollapse_perf.py - Reemplazo de stackcollapse-perf.pl en Python
Procesa salida de 'perf script' y colapsa stacks similares
"""
import sys
import re

def collapse_perf_stacks(input_data):
    """Parse perf script output and collapse identical stacks"""
    stacks = {}
    lines = input_data.strip().split('\n')
    
    current_stack = []
    current_pid = None
    
    for line in lines:
        if not line.strip() or line.startswith('#'):
            continue
        
        # Check for sample header line
        match = re.match(r'^(\S+)\s+(\d+)\s+\[(\d+)\]\s+([\d.]+):', line)
        if match:
            # Save previous stack
            if current_stack:
                stack_str = ';'.join(current_stack)
                stacks[stack_str] = stacks.get(stack_str, 0) + 1
            
            current_stack = []
            current_pid = match.group(1)
            continue
        
        # Parse function lines
        func_match = re.search(r'\s+([a-f0-9]+)\s+(.+?)\s+\(', line)
        if func_match:
            func = func_match.group(2).strip()
            if func and func != '-' and func != 'unknown':
                current_stack.insert(0, func)
    
    # Add last stack
    if current_stack:
        stack_str = ';'.join(current_stack)
        stacks[stack_str] = stacks.get(stack_str, 0) + 1
    
    return stacks

def main():
    input_data = sys.stdin.read()
    stacks = collapse_perf_stacks(input_data)
    
    for stack, count in stacks.items():
        print(f'{stack} {count}')

if __name__ == '__main__':
    main()
