/* global React, useApp,
   cn, Icon, LocationChip, Badge, Button, Card, UserAvatarChip, SlaTimerBadge, Tabs, Input, Select, Dropdown, Kbd, rub, num, __SEED__ */
/**
 * prototype/features/customs-table.jsx
 *
 * Mirrors:
 *   features/quotes/ui/customs-step/customs-step-section.tsx → CustomsStepSurface
 *   features/quotes/ui/customs-step/customs-table-toolbar.tsx
 *   features/quotes/ui/customs-step/customs-handsontable.tsx  (simplified rails table, not real HOT)
 *   features/quotes/ui/customs-step/customs-item-expand-dialog.tsx
 *   features/customs-autofill/ui/autofill-banner.tsx
 *   features/customs-autofill/ui/autofill-sparkle.tsx
 *   features/customs-autofill/ui/bulk-accept-modal.tsx
 *   features/quotes/ui/customs-step/quote-customs-expenses.tsx
 *
 * Note: prototype renders a semantic <table>; production uses Handsontable.
 * Column schema, row-expand modal, autofill sparkle, and duty composite are 1:1.
 */
const { useState: csUse, useMemo: csMemo } = React;

function CustomsStepSurface() {
  const [items, setItems] = csUse(() => __SEED__.customsItems());
  const [expandedId, setExpandedId] = csUse(null);
  const [bulkOpen, setBulkOpen] = csUse(false);
  const [autofillDismissed, setAutofillDismissed] = csUse(false);

  const autofillCount = items.filter(i => i.autofill).length;
  const missingHs = items.filter(i => !i.hs_code).length;

  return (
    <>
      <div className="page-header row items-end justify-between">
        <div>
          <h1>Таможенное оформление</h1>
          <p className="page-header__sub">Q-210418 · 7 позиций · 3 бренда</p>
        </div>
        <div className="row items-center gap-2">
          <Button variant="ghost" icon="refresh">Обновить autofill</Button>
          <Button variant="primary" icon="check">Отправить декларацию</Button>
        </div>
      </div>

      {autofillCount > 0 && !autofillDismissed && (
        <AutofillBanner count={autofillCount} onAcceptAll={() => setBulkOpen(true)} onDismiss={() => setAutofillDismissed(true)} />
      )}

      <CustomsTableToolbar missingHs={missingHs} />

      <Card padded={false}>
        <CustomsItemsTable items={items} onExpand={setExpandedId} onUpdate={(id, patch) => setItems(items.map(it => it.id === id ? { ...it, ...patch } : it))} />
      </Card>

      <QuoteCustomsExpenses />

      {expandedId && (
        <CustomsItemExpandDialog
          item={items.find(i => i.id === expandedId)}
          onClose={() => setExpandedId(null)}
          onSave={(patch) => { setItems(items.map(it => it.id === expandedId ? { ...it, ...patch } : it)); setExpandedId(null); }}
        />
      )}
      {bulkOpen && (
        <BulkAcceptModal
          items={items.filter(i => i.autofill)}
          onClose={() => setBulkOpen(false)}
          onConfirm={(ids) => {
            setItems(items.map(it => ids.includes(it.id) ? { ...it, autofill: null } : it));
            setBulkOpen(false);
          }}
        />
      )}
    </>
  );
}

// ---------- Banner ----------
function AutofillBanner({ count, onAcceptAll, onDismiss }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12,
      padding: "12px 16px", marginBottom: 16,
      background: "var(--color-accent-subtle)",
      border: "1px solid var(--color-border-light)",
      borderRadius: "var(--radius-md)",
    }}>
      <Icon name="sparkles" size={18} style={{ color: "var(--color-accent)" }} />
      <div className="flex-1">
        <div className="font-semibold text-sm">Autofill нашёл {count} совпадений</div>
        <div className="text-xs text-subtle">HS-коды, пошлины и разрешительные документы подобраны на основе прошлых заказов — проверьте и примите.</div>
      </div>
      <Button variant="secondary" size="sm" onClick={onAcceptAll}>Принять все</Button>
      <button className="tbl__icon-btn" onClick={onDismiss} aria-label="Скрыть"><Icon name="x" size={14} /></button>
    </div>
  );
}

// ---------- Toolbar ----------
function CustomsTableToolbar({ missingHs }) {
  const [view, setView] = csUse("all");
  return (
    <div className="row items-center gap-3 mb-4 flex-wrap">
      <Tabs
        active={view}
        onChange={setView}
        tabs={[
          { key: "all", label: "Все позиции", count: 7 },
          { key: "missing", label: "Без HS-кода", count: missingHs },
          { key: "licensed", label: "С разрешительными", count: 3 },
        ]}
      />
      <div style={{ flex: 1 }} />
      <div className="row items-center gap-2">
        <span className="text-xs text-subtle">Представление:</span>
        <Button variant="ghost" size="sm" icon="grid">Компактное</Button>
        <Button variant="ghost" size="sm" icon="plus">Сохранить вид</Button>
      </div>
    </div>
  );
}

// ---------- Items table ----------
function CustomsItemsTable({ items, onExpand, onUpdate }) {
  return (
    <div style={{ overflow: "auto" }}>
      <table className="tbl" style={{ minWidth: 1200 }}>
        <thead>
          <tr>
            <th style={{ width: 40 }}></th>
            <th style={{ width: 100 }}>Бренд</th>
            <th>Артикул / Название</th>
            <th style={{ width: 80 }}>Кол-во</th>
            <th style={{ width: 80 }}>Вес, кг</th>
            <th style={{ width: 140 }}>HS-код</th>
            <th style={{ width: 180 }}>Пошлина</th>
            <th style={{ width: 80 }}>НДС</th>
            <th style={{ width: 130 }}>Разрешения</th>
            <th style={{ width: 100 }}>ЧЗ</th>
          </tr>
        </thead>
        <tbody>
          {items.map(it => {
            const rowCls = it.autofill ? "row--autofill" : !it.hs_code ? "row--review" : "";
            return (
              <tr key={it.id} className={rowCls}>
                <td>
                  <button className="tbl__icon-btn" onClick={() => onExpand(it.id)} aria-label="Развернуть"><Icon name="arrowUp" size={12} style={{ transform: "rotate(45deg)" }} /></button>
                </td>
                <td><span className="font-semibold text-sm">{it.brand}</span></td>
                <td>
                  <div className="font-semibold text-sm">{it.product_code}</div>
                  <div className="text-xs text-subtle">{it.product_name}</div>
                </td>
                <td className="tabular">{num(it.qty)}</td>
                <td className="tabular">{num(it.weight_kg)}</td>
                <td>
                  <HsCodeCell item={it} onUpdate={(v) => onUpdate(it.id, { hs_code: v })} />
                </td>
                <td>
                  <DutyCompositeCell item={it} onUpdate={(patch) => onUpdate(it.id, patch)} />
                </td>
                <td className="tabular">{it.vat_pct != null ? `${it.vat_pct}%` : "—"}</td>
                <td>
                  <LicenseChips item={it} />
                </td>
                <td>
                  {it.honest_mark ? <Badge tone="info" size="sm">ЧЗ</Badge> : <span className="text-subtle text-xs">—</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------- Cells ----------
function HsCodeCell({ item, onUpdate }) {
  if (!item.hs_code) {
    return <input className="field__input" style={{ width: 130 }} placeholder="Укажите код…" defaultValue="" onBlur={(e) => e.target.value && onUpdate(e.target.value)} />;
  }
  return (
    <div className="row gap-1 items-center">
      {item.autofill && <AutofillSparkle source={item.autofill.source} date={item.autofill.date} />}
      <span className="tabular text-sm font-semibold">{item.hs_code}</span>
    </div>
  );
}

function AutofillSparkle({ source, date }) {
  return (
    <span title={`Взято из ${source} (${date})`} style={{ display: "inline-flex", cursor: "help" }}>
      <Icon name="sparkles" size={12} style={{ color: "var(--color-accent)" }} />
    </span>
  );
}

function DutyCompositeCell({ item, onUpdate }) {
  const mode = item.duty_per_kg != null ? "perKg" : "pct";
  const value = mode === "perKg" ? item.duty_per_kg : item.duty_pct;
  return (
    <div className="row gap-1 items-center">
      <input
        className="field__input tabular"
        style={{ width: 70 }}
        type="number"
        value={value ?? ""}
        onChange={(e) => {
          const v = e.target.value === "" ? null : Number(e.target.value);
          onUpdate(mode === "perKg" ? { duty_per_kg: v, duty_pct: null } : { duty_pct: v, duty_per_kg: null });
        }}
      />
      <div style={{ display: "inline-flex", borderRadius: "var(--radius-sm)", overflow: "hidden", border: "1px solid var(--color-border-light)" }}>
        <button
          onClick={() => onUpdate({ duty_pct: item.duty_pct ?? item.duty_per_kg ?? 0, duty_per_kg: null })}
          style={{ padding: "4px 8px", fontSize: 11, fontWeight: 600, background: mode === "pct" ? "var(--color-accent-subtle)" : "transparent", color: mode === "pct" ? "var(--color-accent)" : "var(--color-text-muted)" }}>%</button>
        <button
          onClick={() => onUpdate({ duty_per_kg: item.duty_per_kg ?? item.duty_pct ?? 0, duty_pct: null })}
          style={{ padding: "4px 8px", fontSize: 11, fontWeight: 600, background: mode === "perKg" ? "var(--color-accent-subtle)" : "transparent", color: mode === "perKg" ? "var(--color-accent)" : "var(--color-text-muted)" }}>₽/кг</button>
      </div>
    </div>
  );
}

function LicenseChips({ item }) {
  const items = [
    { flag: item.license_ds,  label: "ДС" },
    { flag: item.license_ss,  label: "СС" },
    { flag: item.license_sgr, label: "СГР" },
  ].filter(x => x.flag);
  if (!items.length) return <span className="text-subtle text-xs">—</span>;
  return (
    <div className="row gap-1 flex-wrap">
      {items.map(x => <Badge key={x.label} tone="info" size="sm">{x.label}</Badge>)}
    </div>
  );
}

// ---------- Expand dialog ----------
function CustomsItemExpandDialog({ item, onClose, onSave }) {
  const [draft, setDraft] = csUse({ ...item, notes: item.notes ?? "" });
  return (
    <ModalShell title={`${item.brand} · ${item.product_code}`} onClose={onClose} wide>
      <div className="col gap-4">
        <Section title="Основные">
          <div className="row gap-3">
            <Input label="Название" value={draft.product_name} onChange={(e) => setDraft({ ...draft, product_name: e.target.value })} />
            <Input label="HS-код"   value={draft.hs_code ?? ""} onChange={(e) => setDraft({ ...draft, hs_code: e.target.value })} />
          </div>
          <div className="row gap-3">
            <Input label="Кол-во, шт" type="number" value={draft.qty}       onChange={(e) => setDraft({ ...draft, qty: Number(e.target.value) })} />
            <Input label="Вес, кг"    type="number" value={draft.weight_kg} onChange={(e) => setDraft({ ...draft, weight_kg: Number(e.target.value) })} />
            <Input label="НДС, %"     type="number" value={draft.vat_pct ?? ""} onChange={(e) => setDraft({ ...draft, vat_pct: Number(e.target.value) })} />
          </div>
        </Section>

        <Section title="Разрешительные документы">
          <div className="row gap-4">
            {[["license_ds","Декларация соответствия"],["license_ss","Сертификат соответствия"],["license_sgr","СГР"]].map(([k, label]) => (
              <label key={k} className="row gap-2 items-center">
                <input type="checkbox" checked={draft[k]} onChange={(e) => setDraft({ ...draft, [k]: e.target.checked })} />
                <span>{label}</span>
              </label>
            ))}
            <label className="row gap-2 items-center">
              <input type="checkbox" checked={draft.honest_mark} onChange={(e) => setDraft({ ...draft, honest_mark: e.target.checked })} />
              <span>Честный знак</span>
            </label>
          </div>
        </Section>

        <Section title="Примечание">
          <textarea className="field__input" rows={4} value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} placeholder="Особые условия ввоза, причина запрета, и т.п." />
        </Section>
      </div>

      <div className="row justify-end gap-2 mt-4" style={{ borderTop: "1px solid var(--color-border-light)", paddingTop: 16 }}>
        <Button variant="secondary" onClick={onClose}>Отмена</Button>
        <Button variant="primary" icon="check" onClick={() => onSave(draft)}>Сохранить</Button>
      </div>
    </ModalShell>
  );
}

// ---------- Bulk accept modal ----------
function BulkAcceptModal({ items, onClose, onConfirm }) {
  const [selected, setSelected] = csUse(new Set(items.map(i => i.id)));
  const toggle = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelected(next);
  };
  return (
    <ModalShell title="Подтвердите autofill" onClose={onClose}>
      <div className="text-sm mb-4">Будут применены значения из прошлых заказов. Снимите галочку, чтобы пропустить.</div>
      <div className="col gap-2">
        {items.map(it => (
          <label key={it.id} className="row gap-3 items-center" style={{ padding: 10, border: "1px solid var(--color-border-light)", borderRadius: "var(--radius-md)" }}>
            <input type="checkbox" checked={selected.has(it.id)} onChange={() => toggle(it.id)} />
            <div className="flex-1">
              <div className="font-semibold text-sm">{it.brand} · {it.product_code}</div>
              <div className="text-xs text-subtle">HS {it.hs_code} · Пошлина {it.duty_pct ?? it.duty_per_kg}{it.duty_pct != null ? "%" : " ₽/кг"}</div>
            </div>
            <div className="text-xs text-subtle row items-center gap-1">
              <Icon name="sparkles" size={11} style={{ color: "var(--color-accent)" }} />
              <span>{it.autofill.source}</span>
            </div>
          </label>
        ))}
      </div>
      <div className="row justify-end gap-2 mt-4" style={{ borderTop: "1px solid var(--color-border-light)", paddingTop: 16 }}>
        <Button variant="secondary" onClick={onClose}>Отмена</Button>
        <Button variant="primary" icon="check" onClick={() => onConfirm([...selected])}>Принять ({selected.size})</Button>
      </div>
    </ModalShell>
  );
}

// ---------- Quote customs expenses ----------
function QuoteCustomsExpenses() {
  const [expenses, setExpenses] = csUse([
    { id: "qe-1", label: "Услуги таможенного брокера", costRub: 45000 },
    { id: "qe-2", label: "СВХ Москва",                  costRub: 18000 },
  ]);
  const total = expenses.reduce((a, e) => a + e.costRub, 0);
  return (
    <Card className="mt-4">
      <div className="row items-center justify-between mb-3">
        <div className="font-semibold">Расходы по таможенному оформлению</div>
        <div className="text-sm tabular font-semibold">Σ {rub(total)}</div>
      </div>
      <div className="col gap-2">
        {expenses.map(e => (
          <div key={e.id} className="row gap-2 items-center">
            <input className="field__input flex-1" value={e.label} onChange={(ev) => setExpenses(expenses.map(x => x.id === e.id ? { ...x, label: ev.target.value } : x))} />
            <input className="field__input tabular" style={{ width: 120 }} type="number" value={e.costRub} onChange={(ev) => setExpenses(expenses.map(x => x.id === e.id ? { ...x, costRub: Number(ev.target.value) } : x))} />
            <button className="tbl__icon-btn" onClick={() => setExpenses(expenses.filter(x => x.id !== e.id))} aria-label="Удалить"><Icon name="trash" size={13} /></button>
          </div>
        ))}
        <Button variant="ghost" size="sm" icon="plus" onClick={() => setExpenses([...expenses, { id: `qe-${Date.now()}`, label: "Новый расход", costRub: 0 }])}>Добавить расход</Button>
      </div>
    </Card>
  );
}

// ---------- Modal shell ----------
function ModalShell({ title, onClose, wide, children }) {
  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 80,
      background: "rgba(28,25,23,0.45)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: 24,
    }} onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--color-card)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-md)",
          maxWidth: wide ? 760 : 560,
          width: "100%",
          maxHeight: "88vh",
          overflow: "auto",
          padding: 24,
        }}>
        <div className="row items-center justify-between mb-3">
          <div className="font-semibold text-lg">{title}</div>
          <button className="tbl__icon-btn" onClick={onClose} aria-label="Закрыть"><Icon name="x" size={14} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section>
      <div className="field__label mb-2">{title}</div>
      <div className="col gap-3">{children}</div>
    </section>
  );
}

Object.assign(window, { CustomsStepSurface });
