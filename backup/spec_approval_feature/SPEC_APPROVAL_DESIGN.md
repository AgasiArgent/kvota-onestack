# Specification Multi-Department Approval System

**Feature:** Granular department-level approval tracking for specifications
**Issue:** Bug #8 follow-up - Connect approval status to workflow stages

## Business Requirements

### Approval Workflow
```
draft → pending_review → [department approvals] → approved → signed
```

**Department Sequence:**
1. **Procurement** (Закупки) - must approve first
2. **Logistics** (Логистика) + **Customs** (Таможня) - approve in parallel after procurement
3. **Sales** (Продажи) - approve after BOTH logistics AND customs
4. **Control** (Контроль) - approve after sales
5. **Auto-transition**: When control approves → status becomes "approved"

### Required Approvals
- **All 5 departments** must approve every specification
- Departments can only approve when prerequisites are met
- Any department can **reject** and send back to previous stage

### Quote Dependency
- Specification approval is the **last step** in the quote workflow
- Assumes quote has already gone through its workflow stages
- Quote should be at advanced stage (e.g., "pending_spec_control") before spec approval begins

---

## Technical Design

### 1. Database Schema

**Add to specifications table:**
```sql
ALTER TABLE specifications
ADD COLUMN approvals JSONB DEFAULT '{
  "procurement": {
    "approved": false,
    "approved_by": null,
    "approved_at": null,
    "comments": null
  },
  "logistics": {
    "approved": false,
    "approved_by": null,
    "approved_at": null,
    "comments": null
  },
  "customs": {
    "approved": false,
    "approved_by": null,
    "approved_at": null,
    "comments": null
  },
  "sales": {
    "approved": false,
    "approved_by": null,
    "approved_at": null,
    "comments": null
  },
  "control": {
    "approved": false,
    "approved_by": null,
    "approved_at": null,
    "comments": null
  }
}'::JSONB;
```

**Approval Object Structure:**
```python
{
  "approved": bool,          # True if department approved
  "approved_by": str | null, # User ID who approved
  "approved_at": str | null, # ISO timestamp
  "comments": str | null     # Optional comments/notes
}
```

---

### 2. Approval Logic

**Service:** `services/specification_approval_service.py`

#### 2.1 Can Approve Check
```python
def can_department_approve(approvals: dict, department: str) -> bool:
    """
    Check if department can approve based on workflow rules.

    Rules:
    - procurement: Always can approve (first step)
    - logistics/customs: Require procurement approval
    - sales: Require BOTH logistics AND customs approval
    - control: Require sales approval
    """
    if department == 'procurement':
        return True

    elif department in ['logistics', 'customs']:
        return approvals.get('procurement', {}).get('approved', False)

    elif department == 'sales':
        logistics_ok = approvals.get('logistics', {}).get('approved', False)
        customs_ok = approvals.get('customs', {}).get('approved', False)
        return logistics_ok and customs_ok

    elif department == 'control':
        return approvals.get('sales', {}).get('approved', False)

    return False
```

#### 2.2 Approve Department
```python
def approve_department(
    spec_id: str,
    organization_id: str,
    department: str,
    user_id: str,
    comments: str = None
) -> tuple[bool, str]:
    """
    Approve specification for a specific department.

    Returns:
        (success: bool, message: str)

    Side effects:
        - Updates approvals[department]
        - If all 5 departments approved → changes status to 'approved'
    """
    # 1. Get current spec
    # 2. Check status is 'pending_review'
    # 3. Check if can_department_approve
    # 4. Update approvals[department] = {approved: true, approved_by, approved_at, comments}
    # 5. Check if all 5 departments approved
    # 6. If all approved → status = 'approved'
    # 7. Save to database
    pass
```

#### 2.3 Reject and Rollback
```python
def reject_department(
    spec_id: str,
    organization_id: str,
    department: str,
    user_id: str,
    reason: str
) -> tuple[bool, str]:
    """
    Reject specification and rollback approvals.

    Rollback rules:
    - procurement reject → clear all approvals
    - logistics/customs reject → clear sales, control
    - sales reject → clear control
    - control reject → clear only control
    """
    pass
```

#### 2.4 Get Approval Status
```python
def get_approval_status(spec_id: str, organization_id: str) -> dict:
    """
    Get detailed approval status for UI display.

    Returns:
        {
          'procurement': {
            'approved': bool,
            'can_approve': bool,
            'approved_by_name': str | null,
            'approved_at': str | null,
            'comments': str | null
          },
          ... (for each department)
          'all_approved': bool,
          'next_departments': ['logistics', 'customs']  # Departments that can approve next
        }
    """
    pass
```

---

### 3. UI Changes

#### 3.1 Progress Indicator Enhancement
**Location:** Spec control page top

**Before:**
```
✓ Черновик → ✓ Закупки → ✓ Лог+Там → ✓ Продажи → ✓ Контроль
→ ✓ Согласование → ✓ Клиент → ✓ Спец-я → 9 Сделка
```

**After (with approval details):**
```
✓ Черновик → ✓ Закупки (Иванов И., 15.01) → ⏳ Логистика → ⏳ Таможня
→ 🚫 Продажи → 🚫 Контроль → Согласование → Клиент → Спец-я → Сделка
```

Legend:
- ✓ = Approved
- ⏳ = Awaiting approval (can approve now)
- 🚫 = Blocked (prerequisites not met)
- Gray = Not yet reached

#### 3.2 Approval Progress Section
**Location:** Spec control page, after admin panel, before form fields

```
┌─────────────────────────────────────────────────────────────┐
│ 📋 Прогресс согласования спецификации                        │
├─────────────────────────────────────────────────────────────┤
│ ✅ Закупки - Одобрено                                        │
│    Иван Петров • 15 января 2025, 14:30                      │
│    "Цены согласованы с поставщиками"                         │
│                                                              │
│ ⏳ Логистика - Ожидает проверки                              │
│    [Одобрить] [Отклонить]                                    │
│                                                              │
│ ⏳ Таможня - Ожидает проверки                                │
│    [Одобрить] [Отклонить]                                    │
│                                                              │
│ 🚫 Продажи - Недоступно                                      │
│    Требуется одобрение: Логистика, Таможня                   │
│                                                              │
│ 🚫 Контроль - Недоступно                                     │
│    Требуется одобрение: Продажи                              │
└─────────────────────────────────────────────────────────────┘
```

**Features:**
- Show approval status for each department
- Show approver name and timestamp
- Show comments if any
- Show action buttons only if user has role AND can approve
- Show blocking reason if can't approve

#### 3.3 Department Pages
**Locations:** /procurement, /logistics, /customs, /quote-control (sales), /spec-control (control)

**Add section: "Спецификации на проверке"**
```
┌─────────────────────────────────────────────────────────────┐
│ 📄 Спецификации, ожидающие одобрения (3)                     │
├─────────────────────────────────────────────────────────────┤
│ SPEC-2026-0001 • Test Company • 38,620 RUB                  │
│ [Открыть] [Одобрить] [Отклонить]                             │
│                                                              │
│ SPEC-2026-0002 • Another Company • 125,000 RUB              │
│ [Открыть] [Одобрить] [Отклонить]                             │
└─────────────────────────────────────────────────────────────┘
```

**Query:** Specs where:
- `status = 'pending_review'`
- `can_department_approve(approvals, current_department) = true`
- User has role for this department

#### 3.4 Rejection Modal
**Trigger:** Click "Отклонить" button

```
┌─────────────────────────────────────────────────────────────┐
│ ⚠️  Отклонить спецификацию                                   │
├─────────────────────────────────────────────────────────────┤
│ Вы отклоняете спецификацию SPEC-2026-0001                   │
│                                                              │
│ Это действие откатит все последующие одобрения:              │
│ • Продажи (будет сброшено)                                   │
│ • Контроль (будет сброшено)                                  │
│                                                              │
│ Причина отклонения (обязательно):                            │
│ ┌───────────────────────────────────────────────────────┐   │
│ │                                                       │   │
│ │                                                       │   │
│ └───────────────────────────────────────────────────────┘   │
│                                                              │
│           [Отменить]  [Отклонить спецификацию]              │
└─────────────────────────────────────────────────────────────┘
```

---

### 4. Department Roles Mapping

| Department | Role(s) Required |
|------------|------------------|
| Procurement | `procurement_specialist` |
| Logistics | `logistics_specialist` |
| Customs | `customs_specialist` |
| Sales | `sales_manager`, `quote_controller` |
| Control | `spec_controller`, `admin` |

**Note:** Admins can always approve any department (for testing/override)

---

### 5. API Endpoints

#### POST /spec-control/{spec_id}/approve
```python
{
  "action": "department_approve",
  "department": "procurement",  # or logistics, customs, sales, control
  "comments": "Optional comments"
}
```

**Response:**
- 200: Approved successfully
- 400: Cannot approve (prerequisites not met)
- 403: User doesn't have role
- 404: Spec not found

#### POST /spec-control/{spec_id}/reject
```python
{
  "action": "department_reject",
  "department": "logistics",
  "reason": "Required reason for rejection"
}
```

**Response:**
- 200: Rejected successfully, approvals rolled back
- 403: User doesn't have role
- 404: Spec not found

---

### 6. Migration Path

**For existing specifications:**
```sql
-- Initialize approvals column with default empty structure
UPDATE specifications
SET approvals = '{
  "procurement": {"approved": false, "approved_by": null, "approved_at": null, "comments": null},
  "logistics": {"approved": false, "approved_by": null, "approved_at": null, "comments": null},
  "customs": {"approved": false, "approved_by": null, "approved_at": null, "comments": null},
  "sales": {"approved": false, "approved_by": null, "approved_at": null, "comments": null},
  "control": {"approved": false, "approved_by": null, "approved_at": null, "comments": null}
}'::JSONB
WHERE approvals IS NULL;

-- For specs already "approved", mark all departments as approved
UPDATE specifications
SET approvals = '{
  "procurement": {"approved": true, "approved_by": null, "approved_at": null, "comments": "Legacy approval"},
  "logistics": {"approved": true, "approved_by": null, "approved_at": null, "comments": "Legacy approval"},
  "customs": {"approved": true, "approved_by": null, "approved_at": null, "comments": "Legacy approval"},
  "sales": {"approved": true, "approved_by": null, "approved_at": null, "comments": "Legacy approval"},
  "control": {"approved": true, "approved_by": null, "approved_at": null, "comments": "Legacy approval"}
}'::JSONB
WHERE status = 'approved';
```

---

### 7. Testing Checklist

- [ ] Procurement can approve first
- [ ] Logistics/Customs cannot approve before procurement
- [ ] Sales cannot approve before logistics+customs
- [ ] Control cannot approve before sales
- [ ] Status changes to "approved" when control approves
- [ ] Rejection rolls back dependent approvals
- [ ] Admin can override and approve any department
- [ ] Users without role cannot approve
- [ ] Approval progress shows correctly on spec page
- [ ] Department pages show pending specs
- [ ] Notification: Users get notified when spec enters their queue

---

## Implementation Order

1. ✅ Create design document (this file)
2. ⏳ Add database migration
3. Create `specification_approval_service.py`
4. Update spec-control page UI with approval progress
5. Add approval buttons to department pages
6. Add rejection modal and logic
7. Test end-to-end workflow
8. Deploy and monitor

---

**Created:** 2026-01-19
**Status:** Design Complete, Ready for Implementation
