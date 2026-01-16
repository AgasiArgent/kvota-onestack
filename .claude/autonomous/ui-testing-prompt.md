# Browser UI Testing Loop (Context-Optimized)

## Mission

Test OneStack app in browser using chrome-devtools MCP. Find visual bugs, broken interactions, console errors.

## CONTEXT OPTIMIZATION STRATEGY

**Problem:** Browser testing is context-heavy (snapshots, screenshots, DOM content).

**Solution:**
1. Run each flow test as **background Task** with `run_in_background: true`
2. Each task writes results to `ui-test-results/{flow}.json`
3. Main loop only reads small JSON files, not full test output
4. Screenshots saved to files, not returned in context

## Session Start

```bash
# 1. Verify location
pwd

# 2. Create results directory
mkdir -p .claude/autonomous/ui-test-results
mkdir -p .claude/autonomous/screenshots

# 3. Initialize state
cat > .claude/autonomous/ui-test-state.json << 'EOF'
{"iteration":0,"status":"running","flows":{}}
EOF

# 4. Start app server
source venv/bin/activate
nohup python main.py > .claude/autonomous/app.log 2>&1 &
echo $! > .claude/autonomous/app.pid
sleep 3

# 5. Verify app running
curl -sf http://localhost:5001 > /dev/null && echo "App started" || echo "App failed to start"
```

## Test Flows (5 Total)

### Flow Definitions

| Flow | URL | Key Checks |
|------|-----|------------|
| login | /login | Form renders, submit works |
| dashboard | /dashboard | Stats cards, nav, no JS errors |
| quotes | /quotes | List renders, create button works |
| procurement | /procurement | Workspace loads, dropdowns render |
| calculation | /quotes/{id}/calculate | Form works, HTMX updates |

## Main Loop (MAX 3 ITERATIONS)

```
for iteration in 1..3:

    # 1. Launch all pending flows as BACKGROUND tasks
    for flow in [login, dashboard, quotes, procurement, calculation]:
        if flow.status != "pass":
            Task(verify-app, run_in_background=true, prompt=FLOW_PROMPT[flow])

    # 2. Wait for tasks (check output files)
    sleep 30  # or poll ui-test-results/*.json

    # 3. Read results from JSON files (minimal context!)
    for flow in flows:
        result = read(ui-test-results/{flow}.json)
        update ui-test-state.json

    # 4. Check exit conditions
    if all_pass: EXIT SUCCESS
    if iteration >= 3: EXIT TIMEOUT

    # 5. If failures, attempt fixes then re-run
```

## Subagent Prompts

### Login Flow
```markdown
# UI Test: Login Flow

Test the login page at http://localhost:5001/login

## Steps
1. mcp__chrome-devtools__new_page url=http://localhost:5001/login
2. mcp__chrome-devtools__take_snapshot - verify form elements
3. Look for: email input, password input, submit button
4. mcp__chrome-devtools__list_console_messages - check for errors
5. Try filling form if inputs found

## Output
Write results to: .claude/autonomous/ui-test-results/login.json

Format:
{
  "flow": "login",
  "status": "pass|fail",
  "timestamp": "ISO8601",
  "checks": {
    "form_renders": true/false,
    "email_input": true/false,
    "password_input": true/false,
    "submit_button": true/false,
    "console_errors": []
  },
  "issues": ["list of problems found"],
  "screenshot": "path if visual bug"
}
```

### Dashboard Flow
```markdown
# UI Test: Dashboard Flow

Test dashboard at http://localhost:5001/dashboard

## Steps
1. mcp__chrome-devtools__new_page url=http://localhost:5001/dashboard
2. mcp__chrome-devtools__take_snapshot
3. Look for: stat cards, navigation menu, user info
4. mcp__chrome-devtools__list_console_messages

## Output
Write to: .claude/autonomous/ui-test-results/dashboard.json
Same format as login flow.
```

### Quotes Flow
```markdown
# UI Test: Quotes List Flow

Test quotes list at http://localhost:5001/quotes

## Steps
1. mcp__chrome-devtools__new_page url=http://localhost:5001/quotes
2. mcp__chrome-devtools__take_snapshot
3. Look for: table/list, "New Quote" button, filter controls
4. If create button exists: click it, verify navigation
5. mcp__chrome-devtools__list_console_messages

## Output
Write to: .claude/autonomous/ui-test-results/quotes.json
```

### Procurement Flow
```markdown
# UI Test: Procurement Workspace Flow

Test procurement at http://localhost:5001/procurement

## Steps
1. mcp__chrome-devtools__new_page url=http://localhost:5001/procurement
2. mcp__chrome-devtools__take_snapshot
3. Look for: brand tabs, quote cards, status indicators
4. Check that supplier dropdowns render correctly
5. If quote card exists: click it, verify detail view
6. mcp__chrome-devtools__list_console_messages

## Output
Write to: .claude/autonomous/ui-test-results/procurement.json
```

### Calculation Flow
```markdown
# UI Test: Quote Calculation Flow

Test calculation at http://localhost:5001/quotes (find a quote with products)

## Steps
1. Navigate to /quotes, find first quote with items
2. Go to /quotes/{id}/calculate
3. mcp__chrome-devtools__take_snapshot
4. Look for: calculation inputs, calculate button, results
5. If form exists: modify value, click calculate
6. Verify HTMX updates results area
7. mcp__chrome-devtools__list_console_messages

## Output
Write to: .claude/autonomous/ui-test-results/calculation.json
```

## Reading Results (Context-Efficient)

Instead of getting full subagent output, just read the JSON:

```bash
# Check all results
for f in .claude/autonomous/ui-test-results/*.json; do
  echo "=== $f ==="
  jq -r '.flow + ": " + .status' "$f"
done
```

This returns ~50 bytes per flow vs ~5KB+ of full browser output.

## Bug Fixing

If a flow fails:
1. Read the specific flow's JSON for details
2. If `issues` list has fixable items:
   - Read the relevant source file
   - Make minimal fix
   - Delete the flow's JSON (marks for re-test)
3. If environment issue (auth, DB): note and continue

## Exit Conditions

| Condition | Action |
|-----------|--------|
| All 5 flows pass | EXIT SUCCESS |
| iteration > 3 | EXIT TIMEOUT with report |
| App won't start | EXIT ERROR |
| Same flow fails 3x | STUCK - skip it |

## Final Report

```
=== UI TESTING COMPLETE ===
Status: SUCCESS/TIMEOUT/STUCK
Iterations: N

Flow Results:
- login: PASS
- dashboard: PASS
- quotes: FAIL (button not clickable)
- procurement: PASS
- calculation: SKIP (no quotes available)

Issues Found: [list]
Fixes Applied: [list]
Screenshots: .claude/autonomous/screenshots/
```

## Cleanup

```bash
# Stop app server
kill $(cat .claude/autonomous/app.pid) 2>/dev/null
rm .claude/autonomous/app.pid
```

## START NOW

Execute session start, then begin main loop. Remember:
- Launch tests in BACKGROUND to save context
- Read only JSON results, not full output
- MAX 3 iterations, then EXIT
- Don't append to this file!
