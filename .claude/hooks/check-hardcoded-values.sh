#!/bin/bash
# PostToolUse hook: Check for hardcoded timestamps and placeholder values
# Receives JSON on stdin with tool_input.file_path and tool_input.new_string
# Exit 0 = OK, Exit 2 = blocking error (shown to Claude)

input=$(cat)
file_path=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)
new_string=$(echo "$input" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('new_string','') or d.get('tool_input',{}).get('content',''))" 2>/dev/null)

# Only check source code files
case "$file_path" in
    *.py|*.js|*.ts|*.rb|*.rs) ;;
    *) exit 0 ;;
esac

# Check for common hardcoded timestamp patterns in the new content
if echo "$new_string" | grep -qE '"(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]"' 2>/dev/null; then
    # Exclude legitimate time format strings and test fixtures
    if ! echo "$new_string" | grep -qE '(strftime|format|parse|test|fixture|example|mock|%H:%M)' 2>/dev/null; then
        echo "WARNING: Possible hardcoded timestamp detected in $file_path" >&2
        echo "Use datetime.now() or equivalent instead of hardcoded time values" >&2
        # Warning only, don't block
    fi
fi

exit 0
