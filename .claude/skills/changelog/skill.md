# Skill: changelog

Create or update changelog entries for OneStack after deploying and testing changes.

## Activation

**Trigger:** `/changelog` command
**Arguments:** optional date (defaults to today), optional `--list` flag

**Examples:**
- `/changelog` — draft a new entry for today based on recent commits
- `/changelog 2026-03-05` — draft entry for a specific date
- `/changelog --list` — show all existing entries

## How It Works

1. Determine the date range (last changelog entry → now)
2. Gather git commits in that range
3. Categorize changes into sections (Новое / Улучшения / Исправления)
4. Draft the markdown entry in user-facing Russian
5. Present to user for review/editing
6. Write to `changelog/YYYY-MM-DD.md`

## Entry Format

```markdown
---
title: "Short summary of this release"
date: YYYY-MM-DD
version: "X.Y"
---

## Новое
- Feature descriptions in plain Russian, no jargon

## Улучшения
- Improvements to existing functionality

## Исправления
- Bug fixes, error corrections
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `title` | Yes | Short release title (shown as card heading) |
| `date` | Yes | ISO date, determines sort order and unread tracking |
| `version` | No | Optional version string (shown as purple badge) |

### Categories

| Category | When to use | Commit signals |
|----------|-------------|----------------|
| **Новое** | Brand new features, pages, capabilities | "Add", "Create", "Implement", new routes |
| **Улучшения** | Enhancements to existing features | "Improve", "Update", "Enhance", "Refactor" |
| **Исправления** | Bug fixes, error corrections | "Fix", "Resolve", "Correct", "Handle" |
| **Безопасность** | Security patches (rare) | "Security", "Vulnerability", "CVE" |

## Writing Guidelines

**DO:**
- Write for end users (managers, sales, procurement), not developers
- Describe WHAT changed and WHY it matters, not HOW it was implemented
- Use plain Russian without technical jargon
- Group related changes into a single bullet point
- Keep bullet points to 1-2 sentences max

**DON'T:**
- Mention file names, function names, or technical details
- Include internal refactoring that doesn't affect users
- List every single commit — consolidate related work
- Include debug/logging/CI changes

**Examples of good vs bad:**

```
Bad:  Fix null pointer in count_unread_entries when result.data is empty
Good: Исправлена ошибка отображения счётчика обновлений

Bad:  Add RLS policies to changelog_reads table
Good: (skip — not user-visible)

Bad:  Refactor sidebar menu items to use data-driven approach
Good: (skip — not user-visible)

Bad:  Add delivery_method dropdown with air/auto/sea/multimodal options
Good: Добавлен выбор способа доставки при создании КП (авиа, авто, море, мультимодально)
```

## Procedure

### Step 1: Find date range

```bash
# Find the latest existing changelog entry
ls -1 changelog/*.md | sort -r | head -1
```

The new entry covers commits from the day AFTER the last entry through today.

### Step 2: Gather commits

```bash
# Get commits since last entry (exclude merge commits, CI-only changes)
git log --oneline --since="LAST_ENTRY_DATE" --until="tomorrow"
```

### Step 3: Filter and categorize

Skip commits that are:
- CI/CD fixes (pin dependencies, fix workflow)
- Debug logging (add/remove temporary logging)
- Internal refactoring with no user-visible effect
- Revert + re-apply pairs (only include the final state)

Group remaining commits:
- `Add/Create/Implement` → **Новое**
- `Improve/Update/Enhance` → **Улучшения**
- `Fix/Resolve/Correct` → **Исправления**

### Step 4: Draft entry

Write the draft and present it to the user:

```
Here's the changelog draft for YYYY-MM-DD:

---
title: "..."
date: YYYY-MM-DD
version: "X.Y"
---

## Новое
- ...

## Исправления
- ...

---

Changes to make? (approve / edit / skip)
```

### Step 5: Write file

On approval, write to `changelog/YYYY-MM-DD.md`.

If multiple entries exist for the same date (rare), append a suffix: `changelog/YYYY-MM-DD-2.md`.

### Step 6: Commit (optional)

Ask user if they want to commit the entry:
```bash
git add changelog/YYYY-MM-DD.md
git commit -m "Add changelog entry for YYYY-MM-DD"
```

## Version Numbering

No strict scheme required. Suggested convention:
- Increment minor version for each entry (1.1, 1.2, ... 1.9, 1.10, ...)
- Increment major version for significant milestones
- Check the latest entry's version and increment from there
- Version is optional — dates are the primary identifier

## File Location

All entries stored in: `changelog/` directory at project root.
One file per release date. Parsed by `services/changelog_service.py` at runtime.

## Listing Entries

When invoked with `--list`:

```
Changelog entries:
  2026-03-06  v1.5  Журнал обновлений и маршрутизация закупок (4 items)
  (total: 1 entry)
```
