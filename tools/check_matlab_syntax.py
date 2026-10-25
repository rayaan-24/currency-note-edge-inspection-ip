#!/usr/bin/env python3
"""
Static syntax, block nesting, and structural integrity verifier for MATLAB .m files.
Properly distinguishes block closing 'end' from MATLAB array indexing 'end' (e.g., A(end), cell{end+1}).
"""

import os
import re
import sys

BLOCK_OPENERS = {
    'function', 'if', 'for', 'while', 'switch', 'try', 'classdef', 'methods', 'properties', 'events'
}

def clean_matlab_line(line):
    """Strip comments and string literals to isolate structural syntax tokens."""
    in_str = False
    cleaned = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == "'" and not in_str:
            prev = ''.join(cleaned).rstrip()
            if prev and (prev[-1].isalnum() or prev[-1] in ')]}_'):
                cleaned.append(c) # matrix transpose
            else:
                in_str = True
                cleaned.append(' ')
        elif c == "'" and in_str:
            in_str = False
            cleaned.append(' ')
        elif c == '%' and not in_str:
            break # comment begins
        elif in_str:
            cleaned.append(' ')
        else:
            cleaned.append(c)
        i += 1
    return ''.join(cleaned)

def check_file(filepath):
    errors = []
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    stack = []
    paren_depth = 0
    bracket_depth = 0
    brace_depth = 0

    for line_num, raw_line in enumerate(lines, 1):
        line = clean_matlab_line(raw_line)
        
        # Tokenize preserving character positions
        tokens_with_pos = [(m.group(0), m.start(), m.end()) for m in re.finditer(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b|[()\[\]{}]', line)]
        
        line_chars = list(line)
        idx = 0
        while idx < len(tokens_with_pos):
            token, start_pos, end_pos = tokens_with_pos[idx]
            
            if token == '(': paren_depth += 1
            elif token == ')': paren_depth = max(0, paren_depth - 1)
            elif token == '[': bracket_depth += 1
            elif token == ']': bracket_depth = max(0, bracket_depth - 1)
            elif token == '{': brace_depth += 1
            elif token == '}': brace_depth = max(0, brace_depth - 1)
            elif token in BLOCK_OPENERS:
                # Check for anonymous function like @(x) which is not a function block
                prev_text = line[:start_pos].rstrip()
                if token == 'function' and prev_text.endswith('@'):
                    idx += 1
                    continue
                stack.append((token, line_num))
            elif token == 'end':
                # In MATLAB:
                # 1. Any 'end' inside parentheses () or curly braces {} is an indexing expression (e.g., A(end), A(1:end), c{end+1}).
                # 2. Any 'end' followed by '+' or '-' or ':' or preceded by ':' is an index.
                is_index = False
                if paren_depth > 0 or brace_depth > 0:
                    is_index = True
                else:
                    # Look ahead or behind for indexing operators
                    after = line[end_pos:].lstrip()
                    before = line[:start_pos].rstrip()
                    if after and after[0] in '+-:':
                        is_index = True
                    elif before and before[-1] in '+-:':
                        is_index = True

                if not is_index:
                    if not stack:
                        errors.append(f"Line {line_num}: Unexpected 'end' without matching block opener")
                    else:
                        opener, op_line = stack.pop()
            idx += 1

    if stack:
        for opener, op_line in stack:
            errors.append(f"Unclosed '{opener}' opened at line {op_line}")

    if paren_depth != 0:
        errors.append(f"Mismatched parenthesis count (depth {paren_depth})")
    if bracket_depth != 0:
        errors.append(f"Mismatched square bracket count (depth {bracket_depth})")
    if brace_depth != 0:
        errors.append(f"Mismatched curly brace count (depth {brace_depth})")

    return errors

def main():
    proj_dir = "/Users/mohammedathark/Downloads/currency_note_edge_inspection"
    m_files = sorted([f for f in os.listdir(proj_dir) if f.endswith('.m')])
    
    print(f"Checking {len(m_files)} MATLAB .m files in {proj_dir}...")
    total_errors = 0

    for mf in m_files:
        fpath = os.path.join(proj_dir, mf)
        errs = check_file(fpath)
        if not errs:
            print(f"  ✓ {mf:<32} PASSED static checks")
        else:
            print(f"  ✗ {mf:<32} FAILED ({len(errs)} issues):")
            for e in errs:
                print(f"      - {e}")
            total_errors += len(errs)

    # Also check root main.m
    root_main = "/Users/mohammedathark/Downloads/main.m"
    if os.path.exists(root_main):
        errs = check_file(root_main)
        if not errs:
            print(f"  ✓ {'../main.m':<32} PASSED static checks")
        else:
            print(f"  ✗ {'../main.m':<32} FAILED:")
            for e in errs:
                print(f"      - {e}")
            total_errors += len(errs)

    print("-" * 65)
    if total_errors == 0:
        print("ALL MATLAB FILES PASSED STATIC SYNTAX AND NESTING INTEGRITY CHECKS!")
    else:
        print(f"Found {total_errors} syntax issues. Please inspect and fix.")
        sys.exit(1)

if __name__ == "__main__":
    main()
