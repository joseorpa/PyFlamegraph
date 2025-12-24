#!/usr/bin/env python3
"""
stackcollapse_perf.py - Python replacement for stackcollapse-perf.pl
Processes 'perf script' output and collapses similar stacks
"""
import sys
import re
import os
import argparse

def collapse_perf_stacks(input_data, include_unknown=False, include_comm=False):
    """Parse perf script output and collapse identical stacks
    
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
        
        # Check for sample header line: "comm pid [cpu] timestamp: event"
        match = re.match(r'^(\S+)\s+(\d+)\s+\[(\d+)\]\s+([\d.]+):', line)
        if match:
            # Save previous stack
            if current_stack:
                # Add process name at the base of the stack if requested
                if include_comm and current_comm:
                    current_stack.insert(0, current_comm)
                stack_str = ';'.join(current_stack)
                stacks[stack_str] = stacks.get(stack_str, 0) + 1
            
            current_stack = []
            current_comm = match.group(1)  # Extract process name
            continue
        
        # Parse function lines with binary path: "address func (binary)"
        func_match = re.search(r'\s+([a-f0-9]+)\s+(.+?)\s+\(([^)]+)\)', line)
        if func_match:
            func = func_match.group(2).strip()
            binary = func_match.group(3).strip()
            if func and func != '-' and func != 'unknown':
                if func == '[unknown]':
                    if include_unknown:
                        # Include binary info for unknown symbols
                        binary_name = os.path.basename(binary)
                        func = f'[unknown:{binary_name}]'
                        current_stack.insert(0, func)
                else:
                    current_stack.insert(0, func)
    
    # Add last stack
    if current_stack:
        # Add process name at the base of the stack if requested
        if include_comm and current_comm:
            current_stack.insert(0, current_comm)
        stack_str = ';'.join(current_stack)
        stacks[stack_str] = stacks.get(stack_str, 0) + 1
    
    return stacks

def main():
    parser = argparse.ArgumentParser(
        description='Collapse perf script output into folded stacks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  perf script | python3 stackcollapse_perf.py > collapsed.txt
  perf script | python3 stackcollapse_perf.py --include-unknown --include-comm > collapsed.txt
        '''
    )
    parser.add_argument('--include-unknown', action='store_true',
                        help='Include [unknown] frames with binary info')
    parser.add_argument('--include-comm', action='store_true',
                        help='Include process/command name at base of each stack')
    args = parser.parse_args()
    
    input_data = sys.stdin.read()
    stacks = collapse_perf_stacks(input_data, 
                                   include_unknown=args.include_unknown,
                                   include_comm=args.include_comm)
    
    for stack, count in stacks.items():
        print(f'{stack} {count}')

if __name__ == '__main__':
    main()
