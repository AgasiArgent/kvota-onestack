/* global React, useApp,
   cn, Icon, LocationChip, Badge, Button, Card, UserAvatarChip, SlaTimerBadge, Tabs, Input, Select, Dropdown, Kbd, rub, num */
/**
 * prototype/features/admin-routing.jsx
 *
 * Mirrors:
 *   app/(app)/admin/routing/page.tsx → AdminRoutingPage (logistics tab)
 *   features/admin-routing-logistics/ui/routing-stats-strip.tsx
 *   features/admin-routing-logistics/ui/unassigned-alert.tsx
 *   features/admin-routing-logistics/ui/routing-patterns-table.tsx
 *   features/admin-routing-logistics/ui/new-pattern-side-panel.tsx
 *   features/admin-routing-logistics/ui/coverage-warnings.tsx
 */
const { useState: arUse, useMemo: arMemo } = React;

function AdminRoutingPage() {
  const { seed } = useApp();
  const [activeTab, setActiveTab] = arUse("logistics");
  const [patterns, setPatterns] = arUse(seed.routing_patterns);
  const [editingId, setEditingId] = arUse(null);

  const tabs = [
    { key: "procurement", label: "Закупки" },
    { key: "brands",      label: "Бренды" },
    { key: "logistics",   label: "Логистика", count: patterns.length },
    { key: "customs",     label: "Таможня" },
  ];

  const stats = arMemo(() => ({
    patterns: patterns.length,
    coverageExact: patterns.filter(p => p.specificity === "exact").length,
    coverageWildcard: patterns.filter(p => p.specificity === "wildcard").length,
    unassigned: seed.unassigned.length,
    gaps: seed.coverage_gaps?.length ?? 0,
  }), [patterns, seed]);

  return (
    <>
      <div className="page-header">
        <h1>Администрирование</h1>
        <p className="page-header__sub">Правила автоматической маршрутизации по доменам</p>
      </div>

      <Tabs tabs={tabs} active={activeTab} onChange={setActiveTab} className="mb-6" />

      {activeTab !== "logistics" && (
        <Card><div className="empty">Раздел «{tabs.find(t => t.key === activeTab)?.label}» вне скоупа этого прототипа.</div></Card>
      )}

      {activeTab === "logistics" && (
        <>
          <RoutingStatsStrip stats={stats} />
          {seed.unassigned.length > 0 && <UnassignedAlert invoices={seed.unassigned} users={seed.users.filter(u => u.roles.includes("logistics"))} />}
          {(seed.coverage_gaps?.length ?? 0) > 0 && <CoverageWarnings gaps={seed.coverage_gaps} />}

          <div style={{ display: "grid", gridTemplateColumns: editingId ? "1fr 420px" : "1fr", gap: 16, marginTop: 16 }}>
            <RoutingPatternsTable
              patterns={patterns}
              editingId={editingId}
              onEdit={setEditingId}
              onDelete={(id) => setPatterns(patterns.filter(p => p.id !== id))}
              onAdd={() => setEditingId("new")}
            />
            {editingId && (
              <NewPatternSidePanel
                users={seed.users.filter(u => u.roles.includes("logistics"))}
                locations={seed.locations}
                pattern={editingId === "new" ? null : patterns.find(p => p.id === editingId)}
                onSave={(draft) => {
                  if (editingId === "new") {
                    setPatterns([...patterns, { ...draft, id: `rp-${Date.now()}`, usage_month: 0 }]);
                  } else {
                    setPatterns(patterns.map(p => p.id === editingId ? { ...p, ...draft } : p));
                  }
                  setEditingId(null);
                }}
                onCancel={() => setEditingId(null)}
              />
            )}
          </div>
        </>
      )}
    </>
  );
}

// ---------- Stats strip ----------
function RoutingStatsStrip({ stats }) {
  return (
    <div className="stats-strip">
      <Card className="stat-card">
        <div className="stat-card__label">Всего правил</div>
        <div className="stat-card__value tabular">{stats.patterns}</div>
        <div className="stat-card__delta">{stats.coverageExact} точных · {stats.coverageWildcard} с wildcard</div>
      </Card>
      <Card className="stat-card">
        <div className="stat-card__label">Неназначенных</div>
        <div className="stat-card__value tabular" style={{ color: stats.unassigned > 0 ? "var(--color-error)" : "var(--color-text)" }}>{stats.unassigned}</div>
        <div className="stat-card__delta">Ждут ручной маршрутизации</div>
      </Card>
      <Card className="stat-card">
        <div className="stat-card__label">Пробелы покрытия</div>
        <div className="stat-card__value tabular" style={{ color: stats.gaps > 0 ? "var(--color-warning)" : "var(--color-text)" }}>{stats.gaps}</div>
        <div className="stat-card__delta">Стран без правил</div>
      </Card>
      <Card className="stat-card">
        <div className="stat-card__label">Автоматизация</div>
        <div className="stat-card__value tabular" style={{ color: "var(--color-success)" }}>
          {stats.unassigned === 0 ? "100%" : Math.round((1 - stats.unassigned / 20) * 100) + "%"}
        </div>
        <div className="stat-card__delta">Накладных распределено автоматически</div>
      </Card>
    </div>
  );
}

// ---------- Unassigned alert ----------
function UnassignedAlert({ invoices, users }) {
  const [open, setOpen] = arUse(false);
  return (
    <Card padded={false} className="mb-4">
      <div style={{ padding: 16, display: "flex", alignItems: "center", gap: 12, background: "var(--color-error-bg)", borderRadius: "var(--radius-lg) var(--radius-lg) 0 0" }}>
        <Icon name="alert" size={18} style={{ color: "var(--color-error)" }} />
        <div className="flex-1">
          <div className="font-semibold">{invoices.length} накладных ждут ручного назначения</div>
          <div className="text-xs text-subtle">Ни одно правило ниже не подошло — нужна быстрая раздача или новое правило для этих стран.</div>
        </div>
        <Button variant="secondary" size="sm" onClick={() => setOpen(!open)}>
          {open ? "Свернуть" : "Показать список"}
        </Button>
      </div>
      {open && (
        <table className="tbl">
          <thead>
            <tr>
              <th>Накладная</th>
              <th>Маршрут</th>
              <th>Клиент</th>
              <th style={{ width: 90 }}>Ждёт</th>
              <th style={{ width: 180 }}>Быстрое назначение</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map(inv => (
              <tr key={inv.id}>
                <td><span className="font-semibold text-sm">{inv.idn_quote}</span></td>
                <td>
                  <div className="row gap-2 items-center">
                    <LocationChip location={{ country: inv.pickup.country, iso2: inv.pickup.iso2, city: inv.pickup.city, type: "supplier" }} size="sm" />
                    <Icon name="chevronRight" size={12} className="text-subtle" />
                    <LocationChip location={{ country: inv.delivery.country, iso2: inv.delivery.iso2, city: inv.delivery.city, type: "client" }} size="sm" />
                  </div>
                </td>
                <td>{inv.customer.name}</td>
                <td className="tabular text-sm">{inv.stuck_for_hours} ч</td>
                <td>
                  <QuickAssign users={users} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

function QuickAssign({ users }) {
  const [open, setOpen] = arUse(false);
  const [picked, setPicked] = arUse(null);
  return (
    <Dropdown
      open={open}
      onOpenChange={setOpen}
      align="end"
      trigger={picked ? (
        <div className="row gap-2 items-center">
          <UserAvatarChip user={picked} size="sm" />
          <Icon name="check" size={14} style={{ color: "var(--color-success)" }} />
        </div>
      ) : (
        <Button variant="secondary" size="sm" icon="user" onClick={() => setOpen(!open)}>Назначить</Button>
      )}
    >
      {users.map(u => (
        <button key={u.id} className="dropdown__item" onClick={() => { setPicked(u); setOpen(false); }}>
          <UserAvatarChip user={u} size="sm" showEmail />
        </button>
      ))}
    </Dropdown>
  );
}

// ---------- Coverage warnings ----------
function CoverageWarnings({ gaps }) {
  return (
    <Card padded={false} className="mb-4">
      <div style={{ padding: 16, display: "flex", alignItems: "center", gap: 12, background: "var(--color-warning-bg)", borderRadius: "var(--radius-lg)" }}>
        <Icon name="alert" size={18} style={{ color: "var(--color-warning)" }} />
        <div className="flex-1">
          <div className="font-semibold">Страны без правил маршрутизации</div>
          <div className="row gap-2 mt-2 flex-wrap">
            {gaps.map(g => (
              <span key={g.iso2} style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 10px", background: "var(--color-card)", border: "1px solid var(--color-border-light)", borderRadius: "var(--radius-sm)", fontSize: 12 }}>
                <span aria-hidden>{g.country === "Вьетнам" ? "🇻🇳" : g.country === "Индия" ? "🇮🇳" : "🌐"}</span>
                <span className="font-semibold">{g.country}</span>
                <span className="text-subtle">· {g.stuck_count} ждёт</span>
                <button className="tbl__icon-btn" aria-label="Добавить правило"><Icon name="plus" size={12} /></button>
              </span>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}

// ---------- Patterns table ----------
function RoutingPatternsTable({ patterns, editingId, onEdit, onDelete, onAdd }) {
  return (
    <Card padded={false}>
      <div className="card__header">
        <div className="card__title">Правила маршрутизации · Логистика</div>
        <Button variant="primary" size="sm" icon="plus" onClick={onAdd}>Новое правило</Button>
      </div>
      <table className="tbl">
        <thead>
          <tr>
            <th>Откуда</th>
            <th>Куда</th>
            <th>Специфичность</th>
            <th>Исполнитель</th>
            <th style={{ width: 130 }}>Использовано</th>
            <th style={{ width: 90 }}></th>
          </tr>
        </thead>
        <tbody>
          {patterns.map(p => (
            <tr key={p.id} className={editingId === p.id ? "row--review" : ""}>
              <td><LocationChip variant={p.origin_iso2 ? "solid" : "wildcard"} location={p.origin_iso2 ? { country: p.origin_country, iso2: p.origin_iso2 } : null} label={p.origin_iso2 ? undefined : "Любая страна"} size="sm" /></td>
              <td><LocationChip variant={p.dest_iso2 && p.dest_city !== "*" ? "solid" : "wildcard"} location={p.dest_iso2 ? { country: "Россия", iso2: p.dest_iso2, city: p.dest_city } : null} label={p.dest_city === "*" ? "Любой город" : undefined} size="sm" /></td>
              <td>
                <Badge tone={p.specificity === "exact" ? "success" : "neutral"} size="sm">
                  {p.specificity === "exact" ? "Точное совпадение" : "С wildcard"}
                </Badge>
              </td>
              <td><UserAvatarChipFor userId={p.assignee} /></td>
              <td className="tabular text-sm">
                <div>{p.usage_month} / мес</div>
                <UsageBar value={p.usage_month} max={20} />
              </td>
              <td>
                <div className="tbl__actions">
                  <button className="tbl__icon-btn" onClick={() => onEdit(p.id)} aria-label="Редактировать"><Icon name="pencil" size={13} /></button>
                  <button className="tbl__icon-btn" onClick={() => onDelete(p.id)} aria-label="Удалить"><Icon name="trash" size={13} /></button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function UserAvatarChipFor({ userId }) {
  const { seed } = useApp();
  const user = seed.users.find(u => u.id === userId);
  return <UserAvatarChip user={user} size="sm" />;
}

function UsageBar({ value, max }) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  return (
    <div style={{ height: 3, background: "var(--color-border-light)", borderRadius: 2, marginTop: 4, overflow: "hidden" }}>
      <div style={{ width: `${pct}%`, height: "100%", background: pct > 70 ? "var(--color-success)" : pct > 30 ? "var(--color-info)" : "var(--color-border)" }} />
    </div>
  );
}

// ---------- New/Edit pattern side panel ----------
function NewPatternSidePanel({ users, locations, pattern, onSave, onCancel }) {
  const [draft, setDraft] = arUse(pattern ?? {
    origin_country: "", origin_iso2: null,
    dest_city: "*", dest_iso2: null,
    assignee: users[0]?.id ?? "",
    specificity: "wildcard",
  });

  const originCountries = [...new Set(locations.filter(l => l.type === "supplier").map(l => l.country))];
  const destCities = [...new Set(locations.filter(l => l.type === "client" || l.type === "own_warehouse").map(l => l.city))];

  const assignedUser = users.find(u => u.id === draft.assignee);

  return (
    <Card>
      <div className="row items-center justify-between mb-4">
        <div className="font-semibold">{pattern ? "Редактирование правила" : "Новое правило"}</div>
        <button className="tbl__icon-btn" onClick={onCancel} aria-label="Закрыть"><Icon name="x" size={14} /></button>
      </div>

      <div className="col gap-4">
        <section>
          <div className="field__label mb-2">Откуда</div>
          <Select
            value={draft.origin_iso2 ?? ""}
            onChange={(v) => {
              const loc = locations.find(l => l.iso2 === v);
              setDraft({ ...draft, origin_iso2: v || null, origin_country: loc?.country ?? "" });
            }}
            options={[{ value: "", label: "Любая страна (wildcard)" }, ...originCountries.map(c => {
              const loc = locations.find(l => l.country === c);
              return { value: loc.iso2, label: c };
            })]}
          />
        </section>

        <section>
          <div className="field__label mb-2">Куда</div>
          <Select
            value={draft.dest_city}
            onChange={(v) => setDraft({ ...draft, dest_city: v, dest_iso2: v === "*" ? null : "ru", specificity: v === "*" ? "wildcard" : "exact" })}
            options={[{ value: "*", label: "Любой город (wildcard)" }, ...destCities.map(c => ({ value: c, label: c }))]}
          />
        </section>

        <section>
          <div className="field__label mb-2">Исполнитель</div>
          <Select
            value={draft.assignee}
            onChange={(v) => setDraft({ ...draft, assignee: v })}
            options={users.map(u => ({ value: u.id, label: `${u.name} · ${u.email}` }))}
          />
          {assignedUser && <div className="mt-2"><UserAvatarChip user={assignedUser} showEmail /></div>}
        </section>

        <section style={{ padding: 12, background: "var(--color-accent-subtle)", borderRadius: "var(--radius-md)" }}>
          <div className="row items-center gap-2 mb-1">
            <Icon name="alert" size={13} style={{ color: "var(--color-info)" }} />
            <span className="font-semibold text-sm">Предпросмотр покрытия</span>
          </div>
          <div className="text-xs">
            Правило сработает для накладных {draft.origin_country || "любой страны"} → {draft.dest_city === "*" ? "любого города РФ" : draft.dest_city}.
            Примерно <b>2-4 накладных в месяц</b> попадут под это правило.
          </div>
        </section>
      </div>

      <div className="row justify-end gap-2 mt-6" style={{ borderTop: "1px solid var(--color-border-light)", paddingTop: 16 }}>
        <Button variant="secondary" onClick={onCancel}>Отмена</Button>
        <Button variant="primary" icon="check" onClick={() => onSave(draft)}>{pattern ? "Сохранить" : "Создать правило"}</Button>
      </div>
    </Card>
  );
}

Object.assign(window, { AdminRoutingPage });
