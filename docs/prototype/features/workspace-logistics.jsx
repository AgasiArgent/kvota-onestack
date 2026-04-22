/* global React, useApp,
   cn, Icon, LocationChip, Badge, Button, Card, UserAvatarChip, SlaTimerBadge, Tabs, Input, Select, Dropdown, Kbd, rub, num */
/**
 * prototype/features/workspace-logistics.jsx
 *
 * Mirrors:
 *   app/(app)/workspace/logistics/page.tsx                  → WorkspaceLogisticsPage
 *   features/workspace-logistics/ui/workspace-tab-bar.tsx   → WorkspaceTabBar (via shared Tabs)
 *   features/workspace-logistics/ui/workspace-invoices-table.tsx → WorkspaceInvoicesTable
 *   features/workspace-logistics/ui/unassigned-inbox.tsx    → UnassignedInbox
 *
 * Reads: seed.invoices, seed.unassigned, seed.users, currentUser, role
 * Writes: none (pure view). Assignment actions update in-memory state via setSeed stub.
 */
const { useState: wlsUse, useMemo: wlsMemo } = React;

function WorkspaceLogisticsPage() {
  const { seed, role, currentUser, setActiveInvoiceId, setSurface, setQuoteStep } = useApp();
  const isHead = role.value === "head_of_logistics" || role.value === "head_of_customs";
  const scope = role.value.includes("customs") ? "customs" : "logistics";

  const [activeTab, setActiveTab] = wlsUse("my");

  // Filter invoices by role + scope + assignment
  const { myActive, myDone, teamActive, unassigned } = wlsMemo(() => {
    const mine = seed.invoices.filter(inv => inv[scope]?.assigned_user === currentUser.id);
    const teamUserIds = new Set(seed.users.filter(u => u.roles.includes(scope)).map(u => u.id));
    const team = seed.invoices.filter(inv => teamUserIds.has(inv[scope]?.assigned_user));
    return {
      myActive: mine.filter(i => !i[scope]?.completed_at),
      myDone:   mine.filter(i =>  i[scope]?.completed_at),
      teamActive: team.filter(i => !i[scope]?.completed_at),
      unassigned: seed.unassigned,
    };
  }, [seed, scope, currentUser.id]);

  const tabs = [
    { key: "my",       label: "Мои активные", count: myActive.length },
    { key: "done",     label: "Завершённые",  count: myDone.length },
    ...(isHead ? [
      { key: "team",   label: "Команда",      count: teamActive.length },
      { key: "queue",  label: "Очередь",      count: unassigned.length },
    ] : []),
  ];

  const openInvoice = (inv) => {
    setActiveInvoiceId(inv.id);
    setSurface("quote");
    setQuoteStep(scope === "customs" ? "customs" : "logistics");
  };

  return (
    <>
      <div className="page-header row items-end justify-between">
        <div>
          <h1>Рабочий стол · {scope === "customs" ? "Таможня" : "Логистика"}</h1>
          <p className="page-header__sub">
            {isHead ? "Вы видите свои задачи и всю команду" : "Ваши активные задачи"}
          </p>
        </div>
        <Tabs tabs={tabs} active={activeTab} onChange={setActiveTab} />
      </div>

      {activeTab === "my" && <WorkspaceInvoicesTable invoices={myActive} scope={scope} onOpen={openInvoice} />}
      {activeTab === "done" && <WorkspaceInvoicesTable invoices={myDone} scope={scope} onOpen={openInvoice} viewKind="done" />}
      {activeTab === "team" && <WorkspaceInvoicesTable invoices={teamActive} scope={scope} onOpen={openInvoice} viewKind="team" showAssignee />}
      {activeTab === "queue" && <UnassignedInbox invoices={unassigned} users={seed.users.filter(u => u.roles.includes(scope))} />}
    </>
  );
}

// ---------- Invoices table ----------
function WorkspaceInvoicesTable({ invoices, scope, onOpen, viewKind = "my", showAssignee = false }) {
  if (!invoices.length) {
    return <Card><div className="empty">Нет накладных в этой вкладке.</div></Card>;
  }
  return (
    <Card padded={false}>
      <table className="tbl">
        <thead>
          <tr>
            <th style={{ width: 120 }}>Заказ</th>
            <th>Маршрут</th>
            <th>Клиент</th>
            <th style={{ width: 140 }}>Объём</th>
            <th style={{ width: 140 }}>HS коды</th>
            {showAssignee && <th style={{ width: 180 }}>Исполнитель</th>}
            <th style={{ width: 150 }}>SLA</th>
            <th style={{ width: 60 }}></th>
          </tr>
        </thead>
        <tbody>
          {invoices.map(inv => {
            const slot = inv[scope] ?? {};
            const needsReview = Boolean(inv.logistics_needs_review_since) && scope === "logistics";
            const rowCls = viewKind === "done" ? "" : needsReview ? "row--review" : undefined;
            return (
              <tr key={inv.id} className={rowCls} onClick={() => onOpen(inv)} style={{ cursor: "pointer" }}>
                <td>
                  <div className="font-semibold">{inv.idn_quote}</div>
                  <div className="text-xs text-subtle">{inv.items_count} поз.</div>
                </td>
                <td>
                  <div className="row gap-2 items-center flex-wrap">
                    <LocationChip location={{ country: inv.pickup.country, iso2: inv.pickup.iso2, city: inv.pickup.city, type: "supplier" }} size="sm" />
                    <Icon name="chevronRight" size={12} className="text-subtle" />
                    <LocationChip location={{ country: inv.delivery.country, iso2: inv.delivery.iso2, city: inv.delivery.city, type: "client" }} size="sm" />
                  </div>
                  {needsReview && (
                    <div className="row gap-1 items-center mt-1">
                      <Icon name="alert" size={11} style={{ color: "var(--color-warning)" }} />
                      <span className="text-xs" style={{ color: "var(--color-warning)" }}>Изменился вес — требует проверки</span>
                    </div>
                  )}
                </td>
                <td>
                  <div>{inv.customer.name}</div>
                  <div className="text-xs text-subtle">{inv.customer.city}</div>
                </td>
                <td className="tabular">
                  <div>{num(inv.total_weight_kg)} кг</div>
                  <div className="text-xs text-subtle">{inv.total_volume_m3} м³ · {inv.packages_count} мест</div>
                </td>
                <td>
                  <HsProgress filled={inv.hs_codes_filled} total={inv.hs_codes_total} />
                </td>
                {showAssignee && (
                  <td>
                    <UserAvatarChip user={useApp().seed.users.find(u => u.id === slot.assigned_user)} size="sm" />
                  </td>
                )}
                <td>
                  <SlaTimerBadge assignedAt={slot.assigned_at} deadlineAt={slot.deadline_at} completedAt={slot.completed_at} size="sm" />
                </td>
                <td>
                  <button className="tbl__icon-btn" aria-label="Открыть"><Icon name="chevronRight" size={14} /></button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}

function HsProgress({ filled, total }) {
  if (total === 0) return <span className="text-subtle text-xs">—</span>;
  const pct = Math.round((filled / total) * 100);
  const tone = filled === total ? "success" : filled === 0 ? "neutral" : "warning";
  return (
    <div className="col gap-1" style={{ minWidth: 100 }}>
      <Badge tone={tone} size="sm">{filled}/{total}</Badge>
      <div style={{ height: 3, background: "var(--color-border-light)", borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: filled === total ? "var(--color-success)" : "var(--color-warning)" }} />
      </div>
    </div>
  );
}

// ---------- Unassigned inbox ----------
function UnassignedInbox({ invoices, users }) {
  const [assignments, setAssignments] = wlsUse({});
  const [openFor, setOpenFor] = wlsUse(null);

  if (!invoices.length) {
    return (
      <Card>
        <div className="empty row gap-2 items-center justify-center">
          <Icon name="check" size={16} style={{ color: "var(--color-success)" }} />
          <span>Все накладные распределены.</span>
        </div>
      </Card>
    );
  }

  return (
    <>
      <Card padded={false}>
        <div className="card__header">
          <div className="card__title row items-center gap-2">
            <Icon name="alert" size={14} style={{ color: "var(--color-warning)" }} />
            Неназначенные накладные — требуют ручной маршрутизации
          </div>
          <Badge tone="warning" size="sm">{invoices.length}</Badge>
        </div>
        <table className="tbl">
          <thead>
            <tr>
              <th style={{ width: 120 }}>Заказ</th>
              <th>Маршрут</th>
              <th>Клиент</th>
              <th style={{ width: 140 }}>Объём</th>
              <th style={{ width: 110 }}>Ждёт</th>
              <th style={{ width: 220 }}>Назначить</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map(inv => {
              const assigned = assignments[inv.id];
              const user = users.find(u => u.id === assigned);
              return (
                <tr key={inv.id} className={inv.stuck_for_hours > 6 ? "row--overdue" : "row--review"}>
                  <td>
                    <div className="font-semibold">{inv.idn_quote}</div>
                    <div className="text-xs text-subtle">{inv.items_count} поз.</div>
                  </td>
                  <td>
                    <div className="row gap-2 items-center flex-wrap">
                      <LocationChip location={{ country: inv.pickup.country, iso2: inv.pickup.iso2, city: inv.pickup.city, type: "supplier" }} size="sm" />
                      <Icon name="chevronRight" size={12} className="text-subtle" />
                      <LocationChip location={{ country: inv.delivery.country, iso2: inv.delivery.iso2, city: inv.delivery.city, type: "client" }} size="sm" />
                    </div>
                    <div className="text-xs text-subtle mt-1">Нет правила маршрутизации для {inv.pickup.country}</div>
                  </td>
                  <td>
                    <div>{inv.customer.name}</div>
                    <div className="text-xs text-subtle">{inv.customer.city}</div>
                  </td>
                  <td className="tabular text-sm">{inv.stuck_for_hours} ч</td>
                  <td>
                    {user ? (
                      <div className="row items-center gap-2">
                        <UserAvatarChip user={user} size="sm" />
                        <button className="tbl__icon-btn" onClick={() => setAssignments({ ...assignments, [inv.id]: null })} aria-label="Отменить"><Icon name="x" size={12} /></button>
                      </div>
                    ) : (
                      <Dropdown
                        open={openFor === inv.id}
                        onOpenChange={(o) => setOpenFor(o ? inv.id : null)}
                        trigger={<Button variant="secondary" size="sm" icon="user" onClick={() => setOpenFor(openFor === inv.id ? null : inv.id)}>Назначить логиста</Button>}
                        align="end"
                      >
                        <div className="dropdown__label">Доступные</div>
                        {users.map(u => (
                          <button key={u.id} className="dropdown__item" onClick={() => { setAssignments({ ...assignments, [inv.id]: u.id }); setOpenFor(null); }}>
                            <UserAvatarChip user={u} size="sm" showEmail />
                          </button>
                        ))}
                      </Dropdown>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
      <div className="mt-4 text-xs text-subtle row gap-2 items-center">
        <Icon name="alert" size={12} />
        <span>Совет: добавьте правило в <b>Администрирование → Маршрутизация</b>, чтобы подобные накладные распределялись автоматически.</span>
      </div>
    </>
  );
}

Object.assign(window, { WorkspaceLogisticsPage });
