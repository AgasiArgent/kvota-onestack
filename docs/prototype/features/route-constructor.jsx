/* global React, useApp,
   cn, Icon, LocationChip, Badge, Button, Card, UserAvatarChip, SlaTimerBadge, Tabs, Input, Select, Dropdown, Kbd, rub, num, __SEED__ */
/**
 * prototype/features/route-constructor.jsx
 *
 * Mirrors:
 *   features/route-constructor/ui/route-constructor.tsx
 *   features/route-constructor/ui/segment-timeline.tsx
 *   features/route-constructor/ui/segment-card.tsx
 *   features/route-constructor/ui/segment-details-panel.tsx
 *   features/route-constructor/ui/segment-expenses-list.tsx
 *   features/route-constructor/ui/template-picker.tsx
 *
 * Hosted inside the Quote Logistics step — selected invoice comes from AppContext.
 */
const { useState: rcUse, useMemo: rcMemo, useRef: rcRef } = React;

function LogisticsStepSurface() {
  const { seed, activeInvoiceId, setActiveInvoiceId } = useApp();

  // Invoice switcher (2 invoices under same quote in normal seed)
  const invoicesInQuote = seed.invoices.filter(i => ["inv-1001", "inv-1002"].includes(i.id));
  const invoice = invoicesInQuote.find(i => i.id === activeInvoiceId) ?? invoicesInQuote[0];

  const [segmentsByInvoice, setSegmentsByInvoice] = rcUse(() => ({
    "inv-1001": __SEED__.segmentsForInvoice("inv-1001"),
    "inv-1002": __SEED__.segmentsForInvoice("inv-1002"),
  }));
  const segments = segmentsByInvoice[invoice.id] ?? [];

  const [selectedId, setSelectedId] = rcUse(segments[0]?.id ?? null);
  const selected = segments.find(s => s.id === selectedId) ?? segments[0];

  const updateSegments = (next) => setSegmentsByInvoice({ ...segmentsByInvoice, [invoice.id]: next });

  const totals = rcMemo(() => {
    const days = segments.reduce((a, s) => a + (s.transitDays ?? 0), 0);
    const main = segments.reduce((a, s) => a + (s.mainCostRub ?? 0), 0);
    const extra = segments.reduce((a, s) => a + (s.expenses ?? []).reduce((x, e) => x + (e.costRub ?? 0), 0), 0);
    return { days, main, extra, total: main + extra };
  }, [segments]);

  return (
    <>
      <div className="page-header row items-end justify-between">
        <div>
          <h1>Конструктор маршрута</h1>
          <p className="page-header__sub">{invoice.customer.name} · Накладная {invoice.idn_quote}</p>
        </div>
        <div className="row items-center gap-3">
          <TemplatePicker templates={seed.templates} onApply={(tpl) => applyTemplate(tpl, invoice, seed, updateSegments, setSelectedId)} />
          <Button variant="secondary" icon="plus" onClick={() => {
            const newSeg = emptySegment(segments.length + 1, invoice.id);
            updateSegments([...segments, newSeg]);
            setSelectedId(newSeg.id);
          }}>Добавить сегмент</Button>
        </div>
      </div>

      <InvoiceSwitch invoices={invoicesInQuote} activeId={invoice.id} onChange={setActiveInvoiceId} />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 420px", gap: 16, marginTop: 16 }}>
        <div className="col gap-4">
          <SegmentTimeline
            segments={segments}
            selectedId={selected?.id}
            onSelect={setSelectedId}
            onReorder={(next) => updateSegments(next)}
            onDelete={(id) => {
              const next = segments.filter(s => s.id !== id).map((s, i) => ({ ...s, sequenceOrder: i + 1 }));
              updateSegments(next);
              if (selectedId === id) setSelectedId(next[0]?.id ?? null);
            }}
          />
          <RouteTotalsCard totals={totals} segmentsCount={segments.length} />
        </div>
        <SegmentDetailsPanel
          segment={selected}
          locations={seed.locations}
          onChange={(patch) => {
            if (!selected) return;
            const next = segments.map(s => s.id === selected.id ? { ...s, ...patch } : s);
            updateSegments(next);
          }}
        />
      </div>
    </>
  );
}

// ---------- Invoice switch ----------
function InvoiceSwitch({ invoices, activeId, onChange }) {
  if (invoices.length <= 1) return null;
  return (
    <Tabs
      className="mt-4"
      active={activeId}
      onChange={onChange}
      tabs={invoices.map(i => ({ key: i.id, label: `${i.idn_quote} · ${i.supplier_name}` }))}
    />
  );
}

// ---------- Timeline ----------
function SegmentTimeline({ segments, selectedId, onSelect, onReorder, onDelete }) {
  const dragSrc = rcRef(null);

  const onDragStart = (i) => (e) => {
    dragSrc.current = i;
    e.dataTransfer.effectAllowed = "move";
  };
  const onDragOver = (e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; };
  const onDrop = (i) => (e) => {
    e.preventDefault();
    const src = dragSrc.current;
    if (src == null || src === i) return;
    const next = [...segments];
    const [moved] = next.splice(src, 1);
    next.splice(i, 0, moved);
    onReorder(next.map((s, idx) => ({ ...s, sequenceOrder: idx + 1 })));
  };

  if (!segments.length) {
    return <Card><div className="empty">Маршрут пока пуст. Примените шаблон или добавьте сегмент.</div></Card>;
  }

  return (
    <Card padded={false}>
      <div className="card__header">
        <div className="card__title">Маршрут · {segments.length} сегмент{segments.length === 1 ? "" : "а"}</div>
        <div className="text-xs text-subtle">Перетаскивайте карточки, чтобы изменить порядок</div>
      </div>
      <div className="col" style={{ padding: 16, gap: 8 }}>
        {segments.map((seg, i) => (
          <div key={seg.id}
               draggable
               onDragStart={onDragStart(i)}
               onDragOver={onDragOver}
               onDrop={onDrop(i)}
               onClick={() => onSelect(seg.id)}
               role="button"
               tabIndex={0}
               aria-selected={selectedId === seg.id}
               style={{
                 display: "grid", gridTemplateColumns: "32px 1fr auto", gap: 12, alignItems: "center",
                 padding: 12,
                 border: `1px solid ${selectedId === seg.id ? "var(--color-accent)" : "var(--color-border-light)"}`,
                 borderRadius: "var(--radius-md)",
                 background: selectedId === seg.id ? "var(--color-accent-subtle)" : "var(--color-card)",
                 cursor: "grab",
               }}>
            <div className="row items-center justify-center" style={{ width: 32, height: 32, borderRadius: "var(--radius-sm)", background: "var(--color-sidebar)", fontWeight: 700 }}>{seg.sequenceOrder}</div>
            <div className="col gap-1">
              <div className="row gap-2 items-center flex-wrap">
                <LocationChip location={seg.fromLocation} size="sm" />
                <Icon name="chevronRight" size={12} className="text-subtle" />
                <LocationChip location={seg.toLocation} size="sm" />
              </div>
              <div className="row gap-3 items-center text-xs text-subtle">
                <span>{seg.label}</span>
                <span>·</span>
                <span>{seg.transitDays} дн</span>
                <span>·</span>
                <span>{seg.carrier ?? "—"}</span>
                {(seg.expenses?.length ?? 0) > 0 && (<><span>·</span><span>+{seg.expenses.length} расх.</span></>)}
              </div>
            </div>
            <div className="row gap-1 items-center">
              <div className="tabular text-sm font-semibold">{rub(seg.mainCostRub)}</div>
              <button className="tbl__icon-btn" onClick={(e) => { e.stopPropagation(); onDelete(seg.id); }} aria-label="Удалить"><Icon name="trash" size={13} /></button>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ---------- Details panel ----------
function SegmentDetailsPanel({ segment, locations, onChange }) {
  if (!segment) {
    return <Card><div className="empty">Выберите сегмент слева, чтобы увидеть детали.</div></Card>;
  }
  const locOptions = locations.map(l => ({ value: l.id, label: `${l.country} · ${l.city}` }));

  return (
    <Card>
      <div className="row items-center justify-between mb-4">
        <div className="font-semibold">Детали сегмента {segment.sequenceOrder}</div>
        <Badge tone="info" size="sm">{segment.label}</Badge>
      </div>

      <div className="col gap-3">
        <Select label="Откуда" value={segment.fromLocation?.id ?? ""} onChange={(id) => onChange({ fromLocation: __SEED__.byId(id) })} options={locOptions} />
        <Select label="Куда"   value={segment.toLocation?.id ?? ""}   onChange={(id) => onChange({ toLocation:   __SEED__.byId(id) })} options={locOptions} />

        <div className="row gap-3">
          <Input label="Транзит (дней)" type="number" value={segment.transitDays ?? 0} onChange={(e) => onChange({ transitDays: Number(e.target.value) })} />
          <Input label="Стоимость, ₽"    type="number" value={segment.mainCostRub ?? 0} onChange={(e) => onChange({ mainCostRub: Number(e.target.value) })} />
        </div>
        <Input label="Перевозчик" value={segment.carrier ?? ""} onChange={(e) => onChange({ carrier: e.target.value })} />
        <Input label="Метка" value={segment.label ?? ""} onChange={(e) => onChange({ label: e.target.value })} />

        <div className="field">
          <span className="field__label">Примечание</span>
          <textarea
            className="field__input"
            rows={3}
            value={segment.notes ?? ""}
            onChange={(e) => onChange({ notes: e.target.value })}
          />
        </div>

        <SegmentExpensesList
          expenses={segment.expenses ?? []}
          onChange={(expenses) => onChange({ expenses })}
        />
      </div>
    </Card>
  );
}

// ---------- Expenses ----------
function SegmentExpensesList({ expenses, onChange }) {
  const add = () => onChange([...expenses, { id: `e-${Date.now()}`, label: "Новый расход", costRub: 0, days: 0 }]);
  const update = (id, patch) => onChange(expenses.map(e => e.id === id ? { ...e, ...patch } : e));
  const remove = (id) => onChange(expenses.filter(e => e.id !== id));
  const total = expenses.reduce((a, e) => a + (e.costRub ?? 0), 0);

  return (
    <div className="col gap-2" style={{ borderTop: "1px solid var(--color-border-light)", paddingTop: 12 }}>
      <div className="row items-center justify-between">
        <div className="font-semibold text-sm">Дополнительные расходы</div>
        <div className="text-xs text-subtle tabular">Σ {rub(total)}</div>
      </div>
      {expenses.length === 0 && <div className="text-xs text-subtle">Нет дополнительных расходов</div>}
      {expenses.map(e => (
        <div key={e.id} className="row gap-2 items-center">
          <input className="field__input flex-1" value={e.label} onChange={(ev) => update(e.id, { label: ev.target.value })} />
          <input className="field__input tabular" style={{ width: 110 }} type="number" value={e.costRub} onChange={(ev) => update(e.id, { costRub: Number(ev.target.value) })} />
          <button className="tbl__icon-btn" onClick={() => remove(e.id)} aria-label="Удалить"><Icon name="trash" size={13} /></button>
        </div>
      ))}
      <Button variant="ghost" icon="plus" size="sm" onClick={add}>Добавить расход</Button>
    </div>
  );
}

// ---------- Template picker ----------
function TemplatePicker({ templates, onApply }) {
  const [open, setOpen] = rcUse(false);
  const [query, setQuery] = rcUse("");
  const filtered = templates.filter(t => t.name.toLowerCase().includes(query.toLowerCase()));

  return (
    <Dropdown
      open={open}
      onOpenChange={setOpen}
      align="end"
      trigger={<Button variant="secondary" icon="grid" onClick={() => setOpen(!open)}>Шаблон маршрута</Button>}
    >
      <div style={{ width: 320 }}>
        <div style={{ padding: 8, borderBottom: "1px solid var(--color-border-light)" }}>
          <input className="field__input w-full" placeholder="Поиск шаблона…" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="col" style={{ maxHeight: 320, overflow: "auto", padding: 4 }}>
          {filtered.length === 0 && <div className="empty">Ничего не найдено</div>}
          {filtered.map(t => (
            <button key={t.id} className="dropdown__item" onClick={() => { onApply(t); setOpen(false); }}>
              <div className="col gap-1 flex-1" style={{ alignItems: "flex-start" }}>
                <div className="font-semibold">{t.name}</div>
                <div className="text-xs text-subtle">{t.description} · {t.segments.length} сегментов</div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </Dropdown>
  );
}

// ---------- Totals ----------
function RouteTotalsCard({ totals, segmentsCount }) {
  return (
    <Card>
      <div className="row items-center justify-between">
        <div className="font-semibold">Итого по маршруту</div>
        <div className="text-xs text-subtle">{segmentsCount} сегмент{segmentsCount === 1 ? "" : "ов"}</div>
      </div>
      <div className="stats-strip mt-4" style={{ marginBottom: 0 }}>
        <div>
          <div className="stat-card__label">Транзит</div>
          <div className="stat-card__value tabular">{totals.days} дн</div>
        </div>
        <div>
          <div className="stat-card__label">Основная стоимость</div>
          <div className="stat-card__value tabular">{rub(totals.main)}</div>
        </div>
        <div>
          <div className="stat-card__label">Доп. расходы</div>
          <div className="stat-card__value tabular">{rub(totals.extra)}</div>
        </div>
        <div>
          <div className="stat-card__label">Всего</div>
          <div className="stat-card__value tabular" style={{ color: "var(--color-accent)" }}>{rub(totals.total)}</div>
        </div>
      </div>
    </Card>
  );
}

// ---------- Helpers ----------
function emptySegment(order, invoiceId) {
  return { id: `seg-new-${Date.now()}`, invoiceId, sequenceOrder: order, fromLocation: null, toLocation: null, label: "Новый сегмент", transitDays: 0, mainCostRub: 0, carrier: "", notes: "", expenses: [] };
}

function applyTemplate(template, invoice, seed, updateSegments, setSelectedId) {
  // Resolve wildcard types to concrete locations from invoice pickup/delivery
  const supplier = seed.locations.find(l => l.type === "supplier" && l.iso2 === invoice.pickup.iso2) ?? seed.locations.find(l => l.type === "supplier");
  const hub      = seed.locations.find(l => l.type === "hub" && l.iso2 === invoice.pickup.iso2) ?? seed.locations.find(l => l.type === "hub");
  const customs  = seed.locations.find(l => l.type === "customs");
  const wh       = seed.locations.find(l => l.type === "own_warehouse");
  const client   = seed.locations.find(l => l.type === "client" && l.city === invoice.delivery.city) ?? seed.locations.find(l => l.type === "client");
  const byType = { supplier, hub, customs, own_warehouse: wh, client };

  const segs = template.segments.map(s => ({
    id: `seg-t-${s.id}-${Date.now()}`,
    invoiceId: invoice.id,
    sequenceOrder: s.sequenceOrder,
    fromLocation: byType[s.fromLocationType],
    toLocation: byType[s.toLocationType],
    label: s.defaultLabel,
    transitDays: s.defaultDays,
    mainCostRub: 0,
    carrier: "",
    notes: "",
    expenses: [],
  }));
  updateSegments(segs);
  setSelectedId(segs[0]?.id ?? null);
}

Object.assign(window, { LogisticsStepSurface });
