# Test: "Передать в закупки" button after sub-tab split

**Date:** 2026-02-16
**Commit:** af724cd
**Fix:** Validation now uses server-side data when DOM fields are on other sub-tab

---

## Test Steps

### 1. Draft quote with ALL fields filled
- Open a draft quote that has customer, seller, delivery city/country/method/terms filled
- Go to **Позиции** sub-tab
- **Expected:** "Передать в закупки" button is GREEN (enabled)
- **Check:** Hover tooltip says "Передать КП в отдел закупок"

### 2. Draft quote with MISSING fields
- Open/create a draft quote with NO customer or delivery info
- Go to **Позиции** sub-tab
- **Expected:** Button is GRAY (disabled)
- **Check:** Hover tooltip lists missing fields (e.g. "Заполните: Клиент, Продавец, ...")

### 3. Fill fields on Обзор, switch to Позиции
- Open a draft quote with missing fields
- Go to **Обзор** sub-tab, fill customer + seller + delivery fields
- Switch to **Позиции** sub-tab (page reloads)
- **Expected:** Button becomes GREEN after filling all required fields

### 4. Button click works when enabled
- On a fully-filled draft quote, **Позиции** sub-tab
- Click "Передать в закупки"
- **Expected:** Checklist modal opens (not an error or no-op)

### 5. Validation on Обзор sub-tab still works
- Open a draft quote, stay on **Обзор** sub-tab
- Change customer dropdown to empty ("Выберите клиента...")
- Check that button state updates live (if button visible)
