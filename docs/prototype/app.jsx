/* global React, ReactDOM, __SEED__,
   cn, Icon, LocationChip, Badge, Button, Card, UserAvatarChip, SlaTimerBadge, Tabs, Input, Select, Dropdown, Kbd, rub, num */
/**
 * prototype/app.jsx — top-level shell for prototype.html
 *
 * Wires together:
 *   - Sidebar + Topbar chrome
 *   - Global context: current user/role, seed dataset (normal/edge-cases), current quote/invoice
 *   - 4 surface screens: Workspace, Route Constructor (inside quote shell), Customs (inside quote shell), Admin Routing
 *   - Tweaks panel: role switcher, dataset toggle, table-density toggle
 *
 * Surface components live in prototype/features/*.jsx and attach to window.
 * Mirrors: app/(app)/{workspace,quotes/[id],admin/routing}/page.tsx
 */
const { useState: apUseState, useMemo: apUseMemo, useEffect: apUseEffect, createContext, useContext } = React;

// ---------- Global context ----------
const AppContext = createContext(null);
function useApp() { return useContext(AppContext); }

// ---------- Roles ----------
const ROLES = [
  { value: "head_of_logistics", label: "Head of Logistics", userId: "u-head-log" },
  { value: "logistics",         label: "Logistics",         userId: "u-log-1" },
  { value: "head_of_customs",   label: "Head of Customs",   userId: "u-head-cus" },
  { value: "customs",           label: "Customs",           userId: "u-cus-1" },
  { value: "admin",             label: "Admin",             userId: "u-admin" },
];

// ---------- Surfaces ----------
const SURFACES = [
  { key: "workspace", label: "Рабочий стол",     icon: "home",     roles: ["head_of_logistics","logistics","head_of_customs","customs"] },
  { key: "quote",     label: "Заказ Q-210418",   icon: "truck",    roles: ["head_of_logistics","logistics","head_of_customs","customs","admin"] },
  { key: "admin",     label: "Администрирование", icon: "settings", roles: ["admin"] },
];

// ---------- Root ----------
function App() {
  // Persisted Tweaks
  const initial = (() => {
    try { return JSON.parse(localStorage.getItem("proto-state") ?? "{}"); } catch { return {}; }
  })();

  const [roleValue, setRoleValue] = apUseState(initial.role ?? "head_of_logistics");
  const [dataset, setDataset] = apUseState(initial.dataset ?? "normal");
  const [surface, setSurface] = apUseState(initial.surface ?? "workspace");
  const [activeInvoiceId, setActiveInvoiceId] = apUseState(initial.activeInvoiceId ?? "inv-1001");
  const [quoteStep, setQuoteStep] = apUseState(initial.quoteStep ?? "logistics"); // 'logistics' | 'customs'
  const [tweaksOpen, setTweaksOpen] = apUseState(false);

  const seed = apUseMemo(
    () => dataset === "edgeCases" ? __SEED__.edgeCases() : __SEED__.normal(),
    [dataset]
  );
  const role = ROLES.find(r => r.value === roleValue) ?? ROLES[0];
  const currentUser = seed.users.find(u => u.id === role.userId) ?? seed.users[0];

  apUseEffect(() => {
    localStorage.setItem("proto-state", JSON.stringify({ role: roleValue, dataset, surface, activeInvoiceId, quoteStep }));
  }, [roleValue, dataset, surface, activeInvoiceId, quoteStep]);

  // Tweaks protocol — register listener BEFORE announcing availability
  apUseEffect(() => {
    const onMsg = (e) => {
      if (e.data?.type === "__activate_edit_mode") setTweaksOpen(true);
      if (e.data?.type === "__deactivate_edit_mode") setTweaksOpen(false);
    };
    window.addEventListener("message", onMsg);
    window.parent.postMessage({ type: "__edit_mode_available" }, "*");
    return () => window.removeEventListener("message", onMsg);
  }, []);

  const ctxValue = {
    role, currentUser, seed, dataset,
    surface, setSurface,
    activeInvoiceId, setActiveInvoiceId,
    quoteStep, setQuoteStep,
    setRoleValue, setDataset,
  };

  const visibleSurfaces = SURFACES.filter(s => s.roles.includes(role.value));

  return (
    <AppContext.Provider value={ctxValue}>
      <div className="app">
        <Sidebar surfaces={visibleSurfaces} surface={surface} onSelect={setSurface} />
        <div className="main">
          <Topbar />
          <main className="content" data-screen-label={surface === "quote" ? `Quote · ${quoteStep}` : surface}>
            {surface === "workspace" && <WorkspaceLogisticsPage />}
            {surface === "quote" && <QuotePage />}
            {surface === "admin" && <AdminRoutingPage />}
          </main>
        </div>
        {tweaksOpen && <TweaksPanel onClose={() => setTweaksOpen(false)} />}
      </div>
    </AppContext.Provider>
  );
}

// ---------- Sidebar ----------
function Sidebar({ surfaces, surface, onSelect }) {
  return (
    <aside className="sidebar">
      <div className="sidebar__logo">OneStack</div>
      <nav className="col gap-3">
        <div>
          <div className="sidebar__section-label mb-2">Навигация</div>
          <div className="sidebar__nav">
            {surfaces.map(s => (
              <button key={s.key} onClick={() => onSelect(s.key)} className={cn("sidebar__item", surface === s.key && "sidebar__item--active")}>
                <Icon name={s.icon} size={15} />
                <span>{s.label}</span>
              </button>
            ))}
          </div>
        </div>
      </nav>
    </aside>
  );
}

// ---------- Topbar ----------
function Topbar() {
  const { role, currentUser, surface, quoteStep, setQuoteStep } = useApp();
  return (
    <header className="topbar">
      <div className="row items-center gap-4">
        <div className="topbar__title">
          {surface === "workspace" && "Рабочий стол"}
          {surface === "quote" && "Заказ Q-210418 · ООО Лего Плюс"}
          {surface === "admin" && "Администрирование"}
        </div>
        {surface === "quote" && (
          <Tabs
            tabs={[
              { key: "logistics", label: "Логистика" },
              { key: "customs",   label: "Таможня" },
            ]}
            active={quoteStep}
            onChange={setQuoteStep}
          />
        )}
      </div>
      <div className="topbar__right">
        <Badge tone="neutral" size="sm">{role.label}</Badge>
        <UserAvatarChip user={currentUser} size="sm" />
      </div>
    </header>
  );
}

// ---------- Quote page (routes to LogisticsStep / CustomsStep) ----------
function QuotePage() {
  const { quoteStep } = useApp();
  if (quoteStep === "logistics") return <LogisticsStepSurface />;
  if (quoteStep === "customs") return <CustomsStepSurface />;
  return null;
}

// ---------- Tweaks panel ----------
const TWEAKS_DEFAULTS = /*EDITMODE-BEGIN*/{
  "role": "head_of_logistics",
  "dataset": "normal",
  "surface": "workspace"
}/*EDITMODE-END*/;

function TweaksPanel({ onClose }) {
  const { role, setRoleValue, dataset, setDataset, surface, setSurface, seed } = useApp();

  const change = (edits) => {
    window.parent.postMessage({ type: "__edit_mode_set_keys", edits }, "*");
  };

  return (
    <aside style={{
      position: "fixed", bottom: 16, right: 16, width: 320,
      background: "var(--color-card)", border: "1px solid var(--color-border-light)",
      borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow-md)",
      zIndex: 100, padding: 16, display: "flex", flexDirection: "column", gap: 12,
    }}>
      <div className="row items-center justify-between">
        <div className="font-semibold">Tweaks</div>
        <button className="tbl__icon-btn" onClick={onClose} aria-label="Close"><Icon name="x" size={14} /></button>
      </div>

      <Select
        label="Роль"
        value={role.value}
        onChange={(v) => { setRoleValue(v); change({ role: v }); }}
        options={ROLES.map(r => ({ value: r.value, label: r.label }))}
      />
      <Select
        label="Набор данных"
        value={dataset}
        onChange={(v) => { setDataset(v); change({ dataset: v }); }}
        options={[
          { value: "normal", label: "Обычный (здоровая база)" },
          { value: "edgeCases", label: "Edge-cases (просрочки + неназначенные)" },
        ]}
      />
      <Select
        label="Поверхность"
        value={surface}
        onChange={(v) => { setSurface(v); change({ surface: v }); }}
        options={[
          { value: "workspace", label: "Рабочий стол" },
          { value: "quote",     label: "Карточка заказа" },
          { value: "admin",     label: "Админка" },
        ]}
      />

      <div className="text-xs text-subtle" style={{ borderTop: "1px solid var(--color-border-light)", paddingTop: 10 }}>
        {seed.invoices.length} накладных, {seed.unassigned.length} неназначенных, {seed.routing_patterns.length} правил маршрутизации
      </div>
    </aside>
  );
}

// ---------- Mount ----------
Object.assign(window, { AppContext, useApp, App, ROLES });

// Wait for feature scripts to load (they each Object.assign to window)
function mount() {
  const required = ["WorkspaceLogisticsPage", "LogisticsStepSurface", "CustomsStepSurface", "AdminRoutingPage"];
  const missing = required.filter(k => !window[k]);
  if (missing.length) {
    setTimeout(mount, 30);
    return;
  }
  ReactDOM.createRoot(document.getElementById("root")).render(<App />);
}
mount();
