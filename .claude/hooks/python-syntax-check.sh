#!/bin/bash
# PostToolUse hook: Python syntax check after Edit/Write
# Receives JSON on stdin with tool_input.file_path
# Exit 0 = OK, Exit 2 = blocking error (shown to Claude)

input=$(cat)
file_path=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)

# Only check Python files
if [[ "$file_path" == *.py ]] && [[ -f "$file_path" ]]; then
    result=$(python3 -m py_compile "$file_path" 2>&1)
    if [[ $? -ne 0 ]]; then
        echo "SYNTAX ERROR in $file_path:" >&2
        echo "$result" >&2
        exit 2
    fi
fi
exit 0
