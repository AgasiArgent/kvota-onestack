# Testing Loop Protocol

## Critical Rules

### PROTECTED FILES - DO NOT MODIFY

The following files are **FROZEN** and must **NEVER** be modified during bug fixing:

```
calculation_engine.py    # Core calculation logic - verified against Excel
calculation_models.py    # Data models for calculation engine
```

**Why:** The calculation engine has been validated against Excel reference values. Any changes could break the business logic that took significant effort to verify.

**If a bug appears related to calculation:**
1. Check if the issue is in `calculation_mapper.py` (this CAN be modified)
2. Check if the issue is in the calling code (main.py, services)
3. If the bug is truly in calculation_engine.py, mark it as "stuck" with note "requires calc engine review"

---

## Testing Loop Flow

```
START
  │
  ▼
[1. Run Tests]
  │
  ├─ All Pass? ──► SUCCESS ──► Generate Report ──► EXIT
  │
  ▼
[2. Collect Failures]
  │
  ▼
[3. Categorize by Severity]
  │
  ▼
[4. For each bug (by priority):]
  │
  ├─ Is file protected? ──► Mark "stuck" ──► Skip
  │
  ├─ Already at max_fix_attempts? ──► Mark "stuck" ──► Skip
  │
  ▼
[5. Attempt Fix]
  │
  ▼
[6. Record attempt in bugs.json]
  │
  ▼
[7. Increment iteration]
  │
  ├─ iteration > max_iterations? ──► TIMEOUT ──► Generate Report ──► EXIT
  │
  └─► Go to [1. Run Tests]
```

---

## Bug Severity Classification

| Severity | Description | Examples |
|----------|-------------|----------|
| **critical** | App won't start, data corruption | Import errors, DB connection failures |
| **high** | Core feature broken | Auth failure, quote creation broken |
| **medium** | Feature partially broken | Export fails for some cases, UI glitch |
| **low** | Minor issues | Styling, non-blocking validation |

---

## Session Initialization Checklist

Before starting a testing loop session:

- [ ] Verify location: `pwd` should be project root
- [ ] Check git status: no uncommitted changes to protected files
- [ ] Read `bugs.json` for any previous session context
- [ ] Run `source venv/bin/activate`
- [ ] Verify database connection works

---

## Bug Record Format

```json
{
  "id": "BUG-001",
  "fingerprint": "unique_identifier_for_dedup",
  "file": "services/role_service.py",
  "line": 45,
  "error_type": "AttributeError",
  "message": "'NoneType' object has no attribute 'get'",
  "test_file": "tests/test_services.py::test_get_user_roles",
  "severity": "high",
  "status": "found",
  "fix_attempts": 0,
  "history": [
    {"event": "found", "iteration": 1, "timestamp": "..."}
  ]
}
```

---

## Fix Attempt Process

1. **Read the failing test** - understand what it expects
2. **Read the error traceback** - identify the root cause
3. **Check if file is protected** - if yes, find alternative fix
4. **Make minimal change** - fix only what's broken
5. **Run single test** - verify fix works: `pytest tests/test_file.py::test_name -v`
6. **Run full suite** - ensure no regressions
7. **Update bugs.json** - record attempt and result

---

## Report Generation

At end of session (success, timeout, or manual stop), generate:

1. **Summary Stats:**
   - Total bugs found
   - Resolved count
   - Stuck count
   - Iterations used

2. **Stuck Bugs List:**
   - Bug ID
   - Reason stuck
   - Suggested action

3. **Recurring Bugs:**
   - Bugs that reappeared after being "resolved"
   - May indicate architectural issue

---

## Ralph Integration

To run overnight with Ralph:

```bash
ralph run -P .claude/autonomous/testing-loop-prompt.md -a claude --acp-permission-mode auto_approve
```

Ralph will:
1. Start Claude with the testing-loop-prompt.md
2. Claude follows this protocol
3. Progress logged to `claude-progress.txt`
4. Bugs tracked in `bugs.json`
