# Pytest Testing Loop (Unit Tests Only)

## Mission

Run pytest, find failures, fix them, repeat. No browser testing.

## CRITICAL: Protected Files

**NEVER modify:**
- `calculation_engine.py`
- `calculation_models.py`

## Session Start

```bash
pwd
source venv/bin/activate
cat .claude/autonomous/pytest-state.json 2>/dev/null || echo '{"iteration":0}'
```

## Main Loop (MAX 5 ITERATIONS)

```bash
# Run tests
pytest tests/ -v --tb=short 2>&1 | tee .claude/autonomous/pytest-output.txt

# Check results
tail -20 .claude/autonomous/pytest-output.txt
```

**If all pass:** EXIT SUCCESS
**If failures:** Fix them (check protected files first), re-run
**If iteration > 5:** EXIT TIMEOUT

## Bug Fixing

1. Read failing test
2. Read error traceback
3. Check if file is protected → skip if yes
4. Make minimal fix
5. Run single test to verify
6. Run full suite

## Final Report

```
=== PYTEST LOOP COMPLETE ===
Status: SUCCESS/TIMEOUT
Iterations: N
Tests: X passed, Y skipped, Z failed
Fixes applied: [list]
```

## START NOW

Run session start, then loop until success or timeout.
