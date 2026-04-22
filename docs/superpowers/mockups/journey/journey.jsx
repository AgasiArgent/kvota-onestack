/* global React, Icon, JOURNEY_DATA */
const { useState: _jUseState } = React;
const useState = _jUseState;
const D = window.JOURNEY_DATA;

/* ─── Shared helpers ─────────────────────────────────────────── */

const ClusterDot = ({ cluster, size = 8 }) => {
  const c = D.clusters.find(x => x.id === cluster);
  return <span style={{ width: size, height: size, borderRadius: 999, background: c?.color || "var(--text-muted)", display: "inline-block" }} />;
};

const RoleChips = ({ roles, max = 3 }) => {
  const shown = roles.slice(0, max);
  const extra = roles.length - shown.length;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
      {shown.map(r => <span key={r} className={`role-chip ${r === "admin" ? "role-chip--admin" : ""}`}>{r}</span>)}
      {extra > 0 && <span className="role-chip">+{extra}</span>}
    </div>
  );
};

const StatusDot = ({ kind, value }) => {
  const map = { impl: { done: "Реализовано", partial: "Частично", missing: "Не начато", unset: "Без статуса" }, qa: { verified: "Проверено", broken: "Баг", untested: "Не проверено" } };
  return <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span className={`dot dot--${value}`} /><span style={{ fontSize: 11, color: "var(--text-muted)" }}>{map[kind][value]}</span></span>;
};

/* ─── Node Card Variants ─────────────────────────────────────── */

const RouteText = ({ route }) => <code style={{ fontSize: 11, fontFamily: "'SF Mono', ui-monospace, monospace", color: "var(--text-muted)", background: "transparent" }}>{route}</code>;

/** 1. MINIMUM — route + title + cluster */
const NodeMin = ({ node, selected = false, focused = false }) => (
  <div className="os-card" style={{
    padding: "10px 12px", minWidth: 180, maxWidth: 220,
    borderColor: selected ? "var(--accent)" : "var(--border-light)",
    boxShadow: selected ? "0 0 0 3px rgba(194,65,12,0.14)" : (focused ? "var(--shadow-md)" : "var(--shadow-sm)"),
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
      <ClusterDot cluster={node.cluster} />
      <RouteText route={node.route} />
    </div>
    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", lineHeight: 1.3 }}>{node.title}</div>
  </div>
);

/** 2. WITH IMPL + QA STATUS */
const NodeStatus = ({ node }) => (
  <div className="os-card" style={{ padding: "10px 12px", minWidth: 200, maxWidth: 240, boxShadow: "var(--shadow-sm)" }}>
    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
      <ClusterDot cluster={node.cluster} />
      <RouteText route={node.route} />
    </div>
    <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>{node.title}</div>
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, borderTop: "1px solid var(--border-light)", paddingTop: 7 }}>
      <StatusDot kind="impl" value={node.impl} />
      <div style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
        <span className={`dot dot--${node.qa}`} />
        <span style={{ fontSize: 11, fontVariantNumeric: "tabular-nums", color: "var(--text-muted)", fontWeight: 600 }}>{node.qaCount[0]}/{node.qaCount[1]}</span>
      </div>
    </div>
  </div>
);

/** 3. RICH — all layers on */
const NodeRich = ({ node, withThumb = true }) => (
  <div className="os-card" style={{ padding: 0, minWidth: 240, maxWidth: 260, overflow: "hidden", boxShadow: "var(--shadow-sm)" }}>
    {withThumb && (
      <div style={{ height: 84, background: "linear-gradient(135deg, #F5F1EC 0%, #E7E5E0 100%)", position: "relative", borderBottom: "1px solid var(--border-light)" }}>
        {/* fake screen thumbnail */}
        <div style={{ position: "absolute", inset: 10, background: "#fff", borderRadius: 4, padding: 6, boxShadow: "0 1px 2px rgba(0,0,0,0.06)" }}>
          <div style={{ height: 6, width: "40%", background: "#D6D3CE", borderRadius: 2, marginBottom: 4 }} />
          <div style={{ height: 4, width: "70%", background: "#E7E5E0", borderRadius: 2, marginBottom: 3 }} />
          <div style={{ height: 4, width: "55%", background: "#E7E5E0", borderRadius: 2, marginBottom: 6 }} />
          <div style={{ display: "flex", gap: 3 }}>
            <div style={{ flex: 1, height: 16, background: "#FFF7ED", borderRadius: 2 }} />
            <div style={{ flex: 1, height: 16, background: "#F0EDEA", borderRadius: 2 }} />
            <div style={{ flex: 1, height: 16, background: "#F0EDEA", borderRadius: 2 }} />
          </div>
        </div>
        <span style={{ position: "absolute", top: 6, right: 6, background: "rgba(28,25,23,0.72)", color: "#fff", fontSize: 9, padding: "1px 5px", borderRadius: 3, fontWeight: 600 }}>nightly · 22.04</span>
      </div>
    )}
    <div style={{ padding: "10px 12px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
        <ClusterDot cluster={node.cluster} />
        <RouteText route={node.route} />
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{node.title}</div>
      <div style={{ marginBottom: 7 }}><RoleChips roles={node.roles} max={3} /></div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", borderTop: "1px solid var(--border-light)", paddingTop: 7 }}>
        <StatusDot kind="impl" value={node.impl} />
        <div style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
          <span className={`dot dot--${node.qa}`} />
          <span style={{ fontSize: 11, fontVariantNumeric: "tabular-nums", color: "var(--text-muted)", fontWeight: 600 }}>{node.qaCount[0]}/{node.qaCount[1]}</span>
        </div>
      </div>
      <div style={{ display: "flex", gap: 10, marginTop: 6, fontSize: 11, color: "var(--text-muted)", fontWeight: 500 }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}><Icon name="list-checks" size={11} />{node.stories}</span>
        {node.feedback > 0 && <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}><Icon name="message-square" size={11} />{node.feedback}</span>}
        {node.training > 0 && <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}><Icon name="book-open" size={11} />{node.training}</span>}
      </div>
    </div>
  </div>
);

/** 4. GHOST — proposed, not in code */
const NodeGhost = ({ node }) => (
  <div style={{
    background: "repeating-linear-gradient(135deg, #FAF9F7 0 8px, #F5F1EC 8px 16px)",
    border: "1.5px dashed var(--text-subtle)", borderRadius: 12, padding: "10px 12px",
    minWidth: 220, maxWidth: 240, position: "relative"
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
      <Icon name="ghost" size={13} style={{ color: "var(--text-subtle)" }} />
      <RouteText route={node.route} />
    </div>
    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", marginBottom: 6, opacity: 0.85 }}>{node.title}</div>
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 10, color: "var(--text-muted)" }}>
      <span className="os-badge os-badge--outline" style={{ fontSize: 10 }}>ghost · {node.plannedIn || "backlog"}</span>
      {node.assignee && <span style={{ color: "var(--text-subtle)" }}>· {node.assignee}</span>}
    </div>
  </div>
);

/* ─── Canvas (simplified React-Flow-like) ────────────────────── */

// Coordinates — laid out by cluster
const LAYOUT = {
  main: { x: 40, y: 40, w: 240 },
  customers: { x: 320, y: 40, w: 260 },
  quotes: { x: 620, y: 40, w: 280 },
  procurement: { x: 40, y: 380, w: 260 },
  finance: { x: 340, y: 380, w: 260 },
  admin: { x: 640, y: 380, w: 260 },
};

// compute absolute node positions
const POSITIONS = (() => {
  const out = {};
  const byCluster = {};
  D.nodes.forEach(n => { (byCluster[n.cluster] ||= []).push(n); });
  Object.entries(byCluster).forEach(([cid, nodes]) => {
    const box = LAYOUT[cid];
    if (!box) return;
    nodes.forEach((n, i) => {
      out[n.id] = { x: box.x + 16, y: box.y + 40 + i * 86, w: box.w - 32 };
    });
  });
  return out;
})();

const ClusterFrame = ({ cluster }) => {
  const box = LAYOUT[cluster.id]; if (!box) return null;
  const nodes = D.nodes.filter(n => n.cluster === cluster.id);
  const h = 40 + nodes.length * 86 + 16;
  return (
    <div style={{
      position: "absolute", left: box.x, top: box.y, width: box.w, height: h,
      border: `1.5px solid ${cluster.color}22`, background: `${cluster.color}07`,
      borderRadius: 16, padding: 0
    }}>
      <div style={{ padding: "10px 14px 0", display: "flex", alignItems: "center", gap: 7 }}>
        <span style={{ width: 9, height: 9, borderRadius: 999, background: cluster.color }} />
        <span style={{ fontSize: 11, fontWeight: 700, color: cluster.color, textTransform: "uppercase", letterSpacing: "0.06em" }}>{cluster.label}</span>
        <span style={{ fontSize: 10, color: "var(--text-subtle)", marginLeft: "auto" }}>{nodes.length} {nodes.length === 1 ? "экран" : "экранов"}</span>
      </div>
    </div>
  );
};

const CanvasNode = ({ node, onClick, selected }) => {
  const pos = POSITIONS[node.id]; if (!pos) return null;
  return (
    <div style={{ position: "absolute", left: pos.x, top: pos.y, width: pos.w, cursor: "pointer" }} onClick={() => onClick?.(node)}>
      {node.ghost ? <NodeGhost node={node} /> :
       (selected ? <div style={{ outline: "2px solid var(--accent)", outlineOffset: 2, borderRadius: 14 }}><NodeRich node={node} withThumb={false} /></div> :
        <NodeStatus node={node} />)}
    </div>
  );
};

const CanvasEdges = ({ selectedId }) => {
  // crude bezier connector between parent-child centers
  return (
    <svg style={{ position: "absolute", inset: 0, pointerEvents: "none", width: "100%", height: "100%" }}>
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#A8A29E"/>
        </marker>
        <marker id="arrow-ghost" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#A8A29E" opacity="0.5"/>
        </marker>
      </defs>
      {D.edges.map((e, i) => {
        const a = POSITIONS[e.from], b = POSITIONS[e.to];
        if (!a || !b) return null;
        const ax = a.x + 200, ay = a.y + 30;
        const bx = b.x, by = b.y + 30;
        const midx = (ax + bx) / 2;
        const isGhost = e.ghost;
        const isActive = selectedId && (e.from === selectedId || e.to === selectedId);
        return <path key={i} d={`M ${ax} ${ay} C ${midx} ${ay}, ${midx} ${by}, ${bx} ${by}`}
          stroke={isActive ? "#C2410C" : "#A8A29E"} strokeWidth={isActive ? 1.8 : 1.2} strokeDasharray={isGhost ? "4 4" : "none"}
          fill="none" opacity={isGhost ? 0.6 : 0.85} markerEnd={isGhost ? "url(#arrow-ghost)" : "url(#arrow)"} />;
      })}
    </svg>
  );
};

const JourneyCanvas = ({ selectedId, onSelect }) => {
  return (
    <div className="canvas-bg scroll-slim" style={{ flex: 1, position: "relative", overflow: "auto", minHeight: 720 }}>
      {/* top overlay: breadcrumb/toolbar */}
      <div style={{ position: "sticky", top: 0, zIndex: 10, background: "rgba(250,249,247,0.92)", backdropFilter: "blur(8px)", borderBottom: "1px solid var(--border-light)", padding: "10px 16px", display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "var(--text-muted)" }}>
          <Icon name="map" size={13} /> <span style={{ fontWeight: 600, color: "var(--text)" }}>Карта путей</span>
          <span style={{ color: "var(--text-subtle)" }}>·</span>
          <span>16 экранов · 3 ghost · 34 пина</span>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          <button className="btn btn--ghost btn--icon" title="Автоукладка"><Icon name="refresh-cw" size={14} /></button>
          <button className="btn btn--ghost btn--icon"><Icon name="zoom-out" size={14} /></button>
          <button className="btn btn--ghost btn--icon"><Icon name="zoom-in" size={14} /></button>
          <button className="btn btn--secondary btn--sm"><Icon name="maximize" size={13} /> На весь экран</button>
          <button className="btn btn--primary btn--sm"><Icon name="plus" size={13} /> Ghost node</button>
        </div>
      </div>
      <div style={{ position: "relative", width: 980, height: 820, margin: "20px" }}>
        {D.clusters.map(c => <ClusterFrame key={c.id} cluster={c} />)}
        <CanvasEdges selectedId={selectedId} />
        {D.nodes.map(n => <CanvasNode key={n.id} node={n} onClick={onSelect} selected={selectedId === n.id} />)}
      </div>
      {/* minimap */}
      <div style={{ position: "absolute", bottom: 14, right: 14, width: 180, height: 120, background: "rgba(255,255,255,0.92)", border: "1px solid var(--border-light)", borderRadius: 8, padding: 8, boxShadow: "var(--shadow-sm)" }}>
        <div className="os-label" style={{ fontSize: 9, marginBottom: 4 }}>Minimap</div>
        <div style={{ position: "relative", width: "100%", height: 82, background: "var(--bg)", borderRadius: 4, overflow: "hidden" }}>
          {D.clusters.map(c => {
            const box = LAYOUT[c.id]; if (!box) return null;
            const s = 0.18;
            return <div key={c.id} style={{ position: "absolute", left: box.x*s, top: box.y*s, width: box.w*s, height: 60*s + D.nodes.filter(n=>n.cluster===c.id).length*86*s, background: c.color, opacity: 0.35, borderRadius: 2 }} />;
          })}
          <div style={{ position: "absolute", inset: "10% 40% 30% 2%", border: "1.5px solid var(--accent)", borderRadius: 3 }} />
        </div>
      </div>
    </div>
  );
};

/* ─── Left sidebar: layers / filters ─────────────────────────── */

const JourneySidebar = () => {
  const [layers, setLayers] = useState({ roles: true, stories: true, impl: true, qa: true, feedback: true, training: false, ghost: true, screenshots: false });
  const toggle = k => setLayers(s => ({ ...s, [k]: !s[k] }));

  const LayerRow = ({ k, icon, label, count }) => (
    <label style={{ display: "flex", alignItems: "center", gap: 9, padding: "7px 10px", borderRadius: 6, cursor: "pointer", background: layers[k] ? "rgba(194,65,12,0.05)" : "transparent", color: layers[k] ? "var(--text)" : "var(--text-muted)" }}>
      <Icon name={icon} size={14} />
      <span style={{ flex: 1, fontSize: 12, fontWeight: 500 }}>{label}</span>
      {count != null && <span style={{ fontSize: 10, color: "var(--text-subtle)", fontVariantNumeric: "tabular-nums" }}>{count}</span>}
      <span style={{
        width: 28, height: 16, borderRadius: 999, background: layers[k] ? "var(--accent)" : "var(--border)",
        position: "relative", transition: "background 0.12s", flexShrink: 0
      }}>
        <span style={{ position: "absolute", top: 2, left: layers[k] ? 14 : 2, width: 12, height: 12, background: "#fff", borderRadius: 999, transition: "left 0.12s" }} />
      </span>
      <input type="checkbox" checked={layers[k]} onChange={() => toggle(k)} style={{ display: "none" }} />
    </label>
  );

  return (
    <aside className="scroll-slim" style={{ width: 240, flexShrink: 0, background: "var(--card)", borderRight: "1px solid var(--border-light)", padding: "14px 12px", overflow: "auto" }}>
      <div className="os-label" style={{ padding: "0 10px 6px", display: "flex", alignItems: "center", gap: 6 }}>
        <Icon name="layers" size={11} /> Слои
      </div>
      <LayerRow k="roles" icon="users" label="Роли" />
      <LayerRow k="stories" icon="list-checks" label="User stories" count={112} />
      <LayerRow k="impl" icon="check-circle" label="Impl status" />
      <LayerRow k="qa" icon="eye" label="QA status" />
      <LayerRow k="feedback" icon="message-square" label="Обратная связь" count={34} />
      <LayerRow k="training" icon="book-open" label="Обучение" count={23} />
      <LayerRow k="ghost" icon="ghost" label="Ghost nodes" count={3} />
      <LayerRow k="screenshots" icon="image" label="Скриншоты" />

      <div className="os-label" style={{ padding: "14px 10px 6px", display: "flex", alignItems: "center", gap: 6 }}>
        <Icon name="filter" size={11} /> Фильтры
      </div>
      <div style={{ padding: "0 6px", display: "flex", flexDirection: "column", gap: 8 }}>
        <label>
          <div style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>Роль</div>
          <select className="os-input" defaultValue="all"><option value="all">Все роли</option>{D.roles.map(r => <option key={r} value={r}>{r}</option>)}</select>
        </label>
        <label>
          <div style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>Impl status</div>
          <select className="os-input" defaultValue="all"><option value="all">Любой</option><option>done</option><option>partial</option><option>missing</option></select>
        </label>
        <label>
          <div style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>QA status</div>
          <select className="os-input" defaultValue="all"><option value="all">Любой</option><option>verified</option><option>broken</option><option>untested</option></select>
        </label>

        <div style={{ position: "relative", marginTop: 4 }}>
          <Icon name="search" size={13} style={{ position: "absolute", left: 9, top: 9, color: "var(--text-subtle)" }} />
          <input className="os-input" placeholder="Поиск по route / title" style={{ paddingLeft: 28 }} />
        </div>

        <div>
          <div style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4, marginTop: 4 }}>Кластеры</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {D.clusters.map(c => (
              <span key={c.id} style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "3px 7px", border: "1px solid var(--border)", borderRadius: 999, fontSize: 11, fontWeight: 500, cursor: "pointer", background: "#fff" }}>
                <span style={{ width: 7, height: 7, borderRadius: 999, background: c.color }} /> {c.label}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Orphans alert */}
      <div style={{ marginTop: 16, padding: 10, background: "#FEF3C7", border: "1px solid #FDE68A", borderRadius: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
          <Icon name="alert-triangle" size={13} style={{ color: "#92400e" }} />
          <span style={{ fontSize: 11, fontWeight: 700, color: "#92400e" }}>2 осиротевших аннотации</span>
        </div>
        <div style={{ fontSize: 11, color: "#78350f", lineHeight: 1.4 }}>Route переименован или удалён. Нужно переназначить.</div>
        <a href="#" onClick={e=>e.preventDefault()} style={{ fontSize: 11, fontWeight: 600, color: "var(--accent)", textDecoration: "none", marginTop: 4, display: "inline-block" }}>Открыть →</a>
      </div>
    </aside>
  );
};

/* ─── Right drawer ───────────────────────────────────────────── */

const Drawer = ({ node, onClose, compact = false }) => {
  if (!node) return null;
  const focus = node;

  const Section = ({ title, icon, children, action }) => (
    <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--border-light)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
        {icon && <Icon name={icon} size={13} style={{ color: "var(--text-muted)" }} />}
        <div className="os-label" style={{ fontSize: 10 }}>{title}</div>
        {action && <div style={{ marginLeft: "auto" }}>{action}</div>}
      </div>
      {children}
    </div>
  );

  return (
    <aside className="scroll-slim" style={{
      width: compact ? 380 : 400, flexShrink: 0, background: "var(--card)",
      borderLeft: "1px solid var(--border-light)", height: "100%", overflow: "auto",
      boxShadow: "-4px 0 16px rgba(28,25,23,0.04)"
    }}>
      {/* Header */}
      <div style={{ padding: "16px 18px", borderBottom: "1px solid var(--border-light)", position: "sticky", top: 0, background: "var(--card)", zIndex: 2 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <ClusterDot cluster={focus.cluster} size={9} />
          <code style={{ fontSize: 12, color: "var(--text-muted)", fontFamily: "'SF Mono', ui-monospace, monospace" }}>{focus.route}</code>
          <button onClick={onClose} className="btn btn--ghost btn--icon" style={{ marginLeft: "auto" }}><Icon name="x" size={14} /></button>
        </div>
        <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.01em" }}>{focus.title}</div>
        <div style={{ fontSize: 11, color: "var(--text-subtle)", marginTop: 4, fontFamily: "'SF Mono', ui-monospace, monospace" }}>node_id: {focus.id}</div>
        <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
          <button className="btn btn--secondary btn--sm"><Icon name="external-link" size={12} /> Открыть страницу</button>
          <button className="btn btn--ghost btn--sm"><Icon name="copy" size={12} /> node_id</button>
          <button className="btn btn--ghost btn--sm" style={{ marginLeft: "auto" }}><Icon name="more-horizontal" size={14} /></button>
        </div>
      </div>

      {/* Status edit */}
      <Section title="Статус" icon="check-circle">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <div>
            <div style={{ fontSize: 10, color: "var(--text-subtle)", marginBottom: 4, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>Реализация</div>
            <div style={{ display: "flex", gap: 0, background: "var(--sidebar)", padding: 2, borderRadius: 6 }}>
              {["done", "partial", "missing"].map(s => (
                <button key={s} style={{
                  flex: 1, padding: "5px 0", border: "none", borderRadius: 4, fontSize: 11, fontWeight: 600,
                  background: focus.impl === s ? "#fff" : "transparent",
                  color: focus.impl === s ? "var(--text)" : "var(--text-muted)",
                  boxShadow: focus.impl === s ? "0 1px 2px rgba(0,0,0,0.06)" : "none", cursor: "pointer",
                  display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 4
                }}><span className={`dot dot--${s}`} />{s}</button>
              ))}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, color: "var(--text-subtle)", marginBottom: 4, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}>QA</div>
            <div style={{ display: "flex", gap: 0, background: "var(--sidebar)", padding: 2, borderRadius: 6 }}>
              {["verified", "broken", "untested"].map(s => (
                <button key={s} style={{
                  flex: 1, padding: "5px 0", border: "none", borderRadius: 4, fontSize: 11, fontWeight: 600,
                  background: focus.qa === s ? "#fff" : "transparent",
                  color: focus.qa === s ? "var(--text)" : "var(--text-muted)",
                  boxShadow: focus.qa === s ? "0 1px 2px rgba(0,0,0,0.06)" : "none", cursor: "pointer",
                  display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 4
                }}><span className={`dot dot--${s}`} />{s.slice(0,4)}</button>
              ))}
            </div>
          </div>
        </div>
        <div style={{ fontSize: 11, color: "var(--text-subtle)", marginTop: 8, display: "flex", alignItems: "center", gap: 5 }}>
          <Icon name="clock" size={11} /> Обновил <strong style={{ color: "var(--text-muted)", fontWeight: 600 }}>quote_controller@</strong> · 2 часа назад
        </div>
      </Section>

      {/* Roles */}
      <Section title={`Роли · ${focus.roles.length}`} icon="users">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {focus.roles.map(r => <span key={r} className={`role-chip ${r === "admin" ? "role-chip--admin" : ""}`} style={{ fontSize: 11, padding: "3px 8px" }}>{r}</span>)}
        </div>
      </Section>

      {/* Stories */}
      <Section title={`User stories · ${D.stories.length}`} icon="list-checks" action={<button className="btn btn--ghost btn--sm" style={{ padding: "3px 6px" }}><Icon name="plus" size={11} /></button>}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {D.stories.map(s => (
            <div key={s.ref} style={{ padding: "8px 10px", background: "var(--bg)", borderRadius: 6, border: "1px solid var(--border-light)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                <code style={{ fontSize: 10, color: "var(--accent)", fontWeight: 700, fontFamily: "'SF Mono', ui-monospace, monospace" }}>{s.ref}</code>
                <span className="role-chip" style={{ fontSize: 10 }}>{s.actor}</span>
              </div>
              <div style={{ fontSize: 12, color: "var(--text)", lineHeight: 1.4 }}>Как <strong style={{ fontWeight: 600 }}>{s.actor}</strong>, я хочу {s.goal}.</div>
            </div>
          ))}
        </div>
      </Section>

      {/* Screenshot + diff */}
      <Section title="Скриншот · nightly" icon="image" action={<label style={{ fontSize: 11, color: "var(--text-muted)", display: "inline-flex", alignItems: "center", gap: 5, cursor: "pointer" }}><input type="checkbox" style={{ accentColor: "var(--accent)" }} /> diff с 21.04</label>}>
        <div style={{ position: "relative", background: "#F5F1EC", border: "1px solid var(--border-light)", borderRadius: 8, aspectRatio: "16/10", overflow: "hidden" }}>
          <div style={{ position: "absolute", inset: 12, background: "#fff", borderRadius: 4, padding: 10, boxShadow: "0 1px 2px rgba(0,0,0,0.08)" }}>
            <div style={{ height: 8, width: "30%", background: "#C2410C", borderRadius: 2, marginBottom: 6 }} />
            <div style={{ height: 5, width: "55%", background: "#D6D3CE", borderRadius: 2, marginBottom: 4 }} />
            <div style={{ height: 5, width: "42%", background: "#E7E5E0", borderRadius: 2, marginBottom: 10 }} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 4 }}>
              <div style={{ height: 30, background: "#FFF7ED", borderRadius: 3 }} />
              <div style={{ height: 30, background: "#F0EDEA", borderRadius: 3 }} />
              <div style={{ height: 30, background: "#F0EDEA", borderRadius: 3 }} />
            </div>
          </div>
          <span style={{ position: "absolute", top: 8, right: 8, background: "rgba(28,25,23,0.76)", color: "#fff", fontSize: 10, padding: "2px 6px", borderRadius: 3, fontWeight: 600 }}>role: quote_controller · 22.04</span>
        </div>
        <div style={{ marginTop: 6, display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-subtle)" }}>
          <span>2 пина перекалибровано</span>
          <span>6 всего · 1 broken</span>
        </div>
      </Section>

      {/* Feedback */}
      <Section title={`Обращения · ${D.feedback.length}`} icon="message-square" action={<a href="#" onClick={e=>e.preventDefault()} style={{ fontSize: 11, color: "var(--accent)", textDecoration: "none", fontWeight: 600 }}>все →</a>}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {D.feedback.slice(0, 3).map(f => (
            <div key={f.id} style={{ padding: "8px 10px", background: "var(--bg)", borderRadius: 6, border: "1px solid var(--border-light)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                <strong style={{ fontSize: 11, fontWeight: 600 }}>{f.author}</strong>
                <span className="role-chip" style={{ fontSize: 10 }}>{f.role}</span>
                <span style={{ fontSize: 10, color: "var(--text-subtle)", marginLeft: "auto" }}>{f.when}</span>
              </div>
              <div style={{ fontSize: 12, lineHeight: 1.4, color: "var(--text)" }}>{f.body}</div>
            </div>
          ))}
        </div>
      </Section>

      {/* Training steps (collapsed header) */}
      <Section title={`Обучение · ${D.training.length} шагов`} icon="book-open" action={<Icon name="chevron-down" size={13} style={{ color: "var(--text-muted)" }} />}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {D.training.slice(0,2).map(t => (
            <div key={t.n} style={{ display: "flex", gap: 10, padding: "6px 0" }}>
              <div style={{ width: 20, height: 20, borderRadius: 999, background: "var(--accent-subtle)", color: "var(--accent)", fontWeight: 700, fontSize: 11, display: "grid", placeItems: "center", flexShrink: 0 }}>{t.n}</div>
              <div>
                <div style={{ fontSize: 12, fontWeight: 600 }}>{t.title}</div>
                <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.4 }}>{t.body.replace(/\*\*/g,"").replace(/_/g,"")}</div>
              </div>
            </div>
          ))}
          <a href="#" onClick={e=>e.preventDefault()} style={{ fontSize: 11, color: "var(--accent)", fontWeight: 600, textDecoration: "none", marginTop: 2 }}>+ ещё {D.training.length - 2} шага</a>
        </div>
      </Section>

      {/* Pins list (QA) */}
      <Section title={`Пины · ${D.pins.length}`} icon="pin" action={<button className="btn btn--ghost btn--sm" style={{ padding: "3px 6px" }}><Icon name="mouse-pointer-click" size={11} /> Pick</button>}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {D.pins.slice(0, 4).map(p => (
            <div key={p.n} style={{ padding: "8px 10px", background: "var(--bg)", borderRadius: 6, border: `1px solid ${p.broken ? "#FCA5A5" : "var(--border-light)"}` }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                <div style={{ width: 22, height: 22, borderRadius: 999, background: p.mode === "training" ? "var(--primary)" : (p.broken ? "var(--error)" : (p.verified ? "var(--success)" : "var(--accent)")), color: "#fff", fontWeight: 700, fontSize: 11, display: "grid", placeItems: "center", flexShrink: 0 }}>{p.n}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <code style={{ fontSize: 10, color: "var(--text-muted)", fontFamily: "'SF Mono', ui-monospace, monospace", wordBreak: "break-all", display: "block", marginBottom: 2 }}>{p.selector}</code>
                  <div style={{ fontSize: 11, lineHeight: 1.4, color: "var(--text)" }}>{p.expected}</div>
                  {p.mode === "qa" && (
                    <div style={{ display: "flex", gap: 4, marginTop: 6 }}>
                      <button className="btn btn--sm" style={{ background: "var(--success-bg)", color: "#065f46", padding: "3px 8px" }}><Icon name="check" size={11} /> OK</button>
                      <button className="btn btn--sm" style={{ background: "var(--error-bg)", color: "#991b1b", padding: "3px 8px" }}><Icon name="alert-triangle" size={11} /> баг</button>
                      <button className="btn btn--ghost btn--sm" style={{ padding: "3px 8px" }}>skip</button>
                    </div>
                  )}
                  {p.mode === "training" && <span className="os-badge os-badge--neutral" style={{ marginTop: 4 }}>training · шаг {p.stepOrder}</span>}
                  {p.broken && <div style={{ fontSize: 10, color: "var(--error)", marginTop: 4, fontWeight: 600 }}>⚠ селектор не найден 3 дня</div>}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Section>

      <div style={{ padding: "16px 18px", fontSize: 11, color: "var(--text-subtle)", textAlign: "center" }}>
        Esc для закрытия · Tab для навигации
      </div>
    </aside>
  );
};

/* ─── Annotated-screen mode ──────────────────────────────────── */

const FakeQuoteScreen = () => (
  <div style={{ position: "absolute", inset: 0, background: "#fff", borderRadius: 8, overflow: "hidden", fontFamily: "inherit" }}>
    {/* top bar */}
    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 16px", borderBottom: "1px solid var(--border-light)", background: "var(--bg)" }}>
      <code style={{ fontSize: 11, color: "var(--text-muted)" }}>/quotes/Q-202604-0087</code>
      <span style={{ fontSize: 14, fontWeight: 700 }}>Q-202604-0087 · ООО "Полимерпласт"</span>
      <span className="os-badge os-badge--warning">pending_quote_control</span>
      <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
        <button className="btn btn--secondary btn--sm">Отклонить</button>
        <button className="btn btn--primary btn--sm">Одобрить</button>
      </div>
    </div>

    <div style={{ display: "flex", height: "calc(100% - 44px)" }}>
      {/* rail */}
      <div style={{ width: 180, borderRight: "1px solid var(--border-light)", padding: 12, background: "var(--bg)" }}>
        <div className="os-label" style={{ fontSize: 10, marginBottom: 8 }}>Шаги</div>
        {[
          ["Продажи", true, true], ["Закупки", true, true], ["Логистика", true, true],
          ["Таможня", true, true], ["Контроль КП", true, false], ["Спецификации", false, false], ["Согласование", false, false]
        ].map(([label, avail, done], i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", marginBottom: 2, borderRadius: 5, background: i===4 ? "var(--accent-subtle)" : "transparent", color: avail ? "var(--text)" : "var(--text-subtle)" }}>
            <span style={{ width: 16, height: 16, borderRadius: 999, background: done ? "var(--success)" : (i===4 ? "var(--accent)" : "var(--border)"), color: "#fff", fontSize: 9, display: "grid", placeItems: "center", fontWeight: 700 }}>{done ? "✓" : i+1}</span>
            <span style={{ fontSize: 12, fontWeight: i===4 ? 600 : 500 }}>{label}</span>
          </div>
        ))}
      </div>
      {/* content */}
      <div style={{ flex: 1, padding: 16 }}>
        <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
          <div style={{ flex: 1, padding: "10px 14px", background: "var(--warning-bg)", border: "1px solid #FDE68A", borderRadius: 8, display: "flex", alignItems: "center", gap: 8 }}>
            <Icon name="clock" size={14} style={{ color: "#92400e" }} />
            <span style={{ fontSize: 12, color: "#92400e", fontWeight: 600 }}>Дедлайн этапа: сегодня 18:00 · осталось 3ч 12м</span>
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12 }}>
          <div className="os-card" style={{ padding: 12 }}>
            <div className="os-label" style={{ fontSize: 10, marginBottom: 8 }}>Позиции · 4</div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead><tr style={{ color: "var(--text-muted)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.05em", textAlign: "left" }}>
                <th style={{ padding: "4px 6px", fontWeight: 600 }}>SKU</th><th style={{ padding: "4px 6px", fontWeight: 600 }}>Бренд</th><th style={{ padding: "4px 6px", fontWeight: 600, textAlign: "right" }}>Кол-во</th><th style={{ padding: "4px 6px", fontWeight: 600, textAlign: "right" }}>Цена, USD</th>
              </tr></thead>
              <tbody>
                {[["PE-LDP-22","Sabic","1200","0.892"],["PP-HOM-14","Braskem","800","1.240"],["PS-GPH-08","Ineos","500","1.105"],["PET-BG-02","Indorama","2100","0.998"]].map((r,i)=>(
                  <tr key={i} style={{ borderTop: "1px solid var(--border-light)" }}>
                    <td style={{ padding: "6px", fontFamily: "ui-monospace, monospace", fontSize: 11 }}>{r[0]}</td>
                    <td style={{ padding: "6px" }}>{r[1]}</td>
                    <td style={{ padding: "6px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{r[2]}</td>
                    <td style={{ padding: "6px", textAlign: "right", fontVariantNumeric: "tabular-nums", fontWeight: 600 }}>{r[3]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="os-card" style={{ padding: 12 }}>
            <div className="os-label" style={{ fontSize: 10, marginBottom: 8 }}>Итого</div>
            <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em" }}>₽ 4 847 210</div>
            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>incl. VAT 20% · фикс ₽/$ 94.50</div>
            <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid var(--border-light)", fontSize: 11 }}>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0" }}><span style={{ color: "var(--text-muted)" }}>Себестоимость</span><span style={{ fontVariantNumeric: "tabular-nums" }}>₽ 3 912 480</span></div>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0" }}><span style={{ color: "var(--text-muted)" }}>Маржа</span><span style={{ fontVariantNumeric: "tabular-nums", color: "var(--success)", fontWeight: 600 }}>19.3%</span></div>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0" }}><span style={{ color: "var(--text-muted)" }}>Менеджер</span><span>А. Петров</span></div>
            </div>
          </div>
        </div>
      </div>
      {/* context panel */}
      <div style={{ width: 220, borderLeft: "1px solid var(--border-light)", padding: 12, background: "var(--bg)" }}>
        <div className="os-label" style={{ fontSize: 10, marginBottom: 8 }}>Контекст</div>
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 3 }}>Клиент</div>
        <a href="#" onClick={e=>e.preventDefault()} className="context-panel__customer-link" style={{ fontSize: 13, fontWeight: 600, color: "var(--accent)", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4 }}>ООО "Полимерпласт" <Icon name="external-link" size={11} /></a>
        <div style={{ marginTop: 10, fontSize: 11, lineHeight: 1.6, color: "var(--text-muted)" }}>
          ИНН 7728923456<br/>FCA Шанхай → DAP Москва<br/>Отсрочка 30 дней<br/>Прежние КП: 12
        </div>
      </div>
    </div>
  </div>
);

const AnnotatedScreen = ({ mode = "qa" }) => {
  const [openPin, setOpenPin] = useState(4);
  const [viewMode, setViewMode] = useState(mode);
  const pinsToShow = D.pins.filter(p => viewMode === "qa" ? p.mode === "qa" : (p.mode === "training" || p.mode === "qa"));

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--bg)" }}>
      {/* toolbar */}
      <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border-light)", background: "var(--card)", display: "flex", alignItems: "center", gap: 10 }}>
        <button className="btn btn--ghost btn--icon"><Icon name="chevron-left" size={14} /></button>
        <code style={{ fontSize: 12, color: "var(--text-muted)" }}>/quotes/[id]</code>
        <span style={{ fontSize: 13, fontWeight: 600 }}>Карточка предложения</span>
        <span className="os-badge os-badge--copper" style={{ marginLeft: 4 }}>annotated view</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 4, padding: 2, background: "var(--sidebar)", borderRadius: 6 }}>
          {[["qa", "pin", "QA"], ["training", "book-open", "Обучение"]].map(([k, icn, lbl]) => (
            <button key={k} onClick={() => setViewMode(k)} className="btn btn--sm" style={{
              background: viewMode === k ? "#fff" : "transparent",
              color: viewMode === k ? "var(--text)" : "var(--text-muted)",
              boxShadow: viewMode === k ? "0 1px 2px rgba(0,0,0,0.06)" : "none", padding: "4px 10px"
            }}><Icon name={icn} size={12} /> {lbl}</button>
          ))}
        </div>
        <button className="btn btn--secondary btn--sm"><Icon name="camera" size={13} /> Пересъёмка</button>
        <button className="btn btn--primary btn--sm"><Icon name="plus" size={13} /> Пин</button>
      </div>

      {/* caption */}
      <div style={{ padding: "8px 16px", background: "var(--accent-subtle)", borderBottom: "1px solid #FDE68A", fontSize: 12, color: "#78350f", display: "flex", alignItems: "center", gap: 8 }}>
        <Icon name="sparkles" size={13} />
        {viewMode === "qa"
          ? <>Кликайте по пронумерованным пинам — откроется карточка с ожидаемым поведением и кнопками <strong>OK / баг / skip</strong>.</>
          : <>Последовательные шаги для обучения — кликните по пину, чтобы увидеть инструкцию.</>}
      </div>

      {/* screenshot area */}
      <div style={{ flex: 1, padding: 20, display: "flex", gap: 16, overflow: "hidden" }}>
        <div style={{ flex: 1, position: "relative", minWidth: 0 }}>
          {/* screenshot meta */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, fontSize: 11, color: "var(--text-muted)" }}>
            <Icon name="camera" size={12} />
            <span>nightly · <strong style={{ color: "var(--text)", fontWeight: 600 }}>quote_controller</strong> · 22.04.2026 · 03:14 UTC</span>
            <span style={{ color: "var(--text-subtle)" }}>·</span>
            <span>1440 × 900</span>
            <span style={{ marginLeft: "auto" }} className="os-badge os-badge--success">bbox свежие</span>
          </div>

          <div style={{ position: "relative", width: "100%", aspectRatio: "16/9.2", background: "#fff", borderRadius: 10, boxShadow: "var(--shadow)", border: "1px solid var(--border-light)", overflow: "hidden" }}>
            <FakeQuoteScreen />

            {/* pins overlay */}
            {pinsToShow.map(p => {
              const color = p.mode === "training" ? "var(--primary)" : (p.broken ? "var(--error)" : (p.verified ? "var(--success)" : "var(--accent)"));
              const isOpen = openPin === p.n;
              return (
                <button key={p.n} onClick={() => setOpenPin(isOpen ? null : p.n)} style={{
                  position: "absolute", left: `${p.x * 100}%`, top: `${p.y * 100}%`,
                  width: 28, height: 28, borderRadius: 999, background: color, color: "#fff",
                  fontWeight: 700, fontSize: 13, border: "3px solid #fff",
                  boxShadow: isOpen ? `0 0 0 4px ${color}33, var(--shadow-md)` : "var(--shadow)",
                  cursor: "pointer", transform: "translate(-50%,-50%)", zIndex: isOpen ? 20 : 10,
                  display: "grid", placeItems: "center",
                  ...(p.broken ? { boxShadow: "0 0 0 3px rgba(220,38,38,0.3), var(--shadow)" } : {})
                }}>{p.n}</button>
              );
            })}
          </div>

          {/* pin legend */}
          <div style={{ display: "flex", gap: 14, marginTop: 10, fontSize: 11, color: "var(--text-muted)", flexWrap: "wrap" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span style={{ width: 10, height: 10, borderRadius: 999, background: "var(--success)" }} /> verified</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span style={{ width: 10, height: 10, borderRadius: 999, background: "var(--accent)" }} /> untested</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span style={{ width: 10, height: 10, borderRadius: 999, background: "var(--error)" }} /> broken</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span style={{ width: 10, height: 10, borderRadius: 999, background: "var(--primary)" }} /> training</span>
            <span style={{ marginLeft: "auto", color: "var(--text-subtle)" }}>{pinsToShow.length} пинов · 1 broken</span>
          </div>
        </div>

        {/* side pin-detail */}
        <div style={{ width: 320, flexShrink: 0, display: "flex", flexDirection: "column", gap: 10, overflow: "auto" }} className="scroll-slim">
          <div className="os-label" style={{ fontSize: 10 }}>{openPin != null ? `Пин #${openPin}` : "Выберите пин"}</div>
          {openPin != null && (() => {
            const p = D.pins.find(x => x.n === openPin);
            if (!p) return null;
            const color = p.mode === "training" ? "var(--primary)" : (p.broken ? "var(--error)" : (p.verified ? "var(--success)" : "var(--accent)"));
            return (
              <div className="os-card" style={{ padding: 14, borderColor: p.broken ? "#FCA5A5" : "var(--border-light)", boxShadow: "var(--shadow)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <div style={{ width: 28, height: 28, borderRadius: 999, background: color, color: "#fff", fontWeight: 700, fontSize: 13, display: "grid", placeItems: "center", border: "2px solid #fff", boxShadow: "0 0 0 1.5px " + color }}>{p.n}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 700 }}>{p.mode === "training" ? "Шаг обучения" : "QA-ожидание"}</div>
                    <div style={{ fontSize: 10, color: "var(--text-subtle)" }}>{p.mode === "training" ? `порядок: ${p.stepOrder}` : "режим: qa"}</div>
                  </div>
                  <button className="btn btn--ghost btn--icon" style={{ padding: 4 }}><Icon name="edit" size={12} /></button>
                </div>
                <div style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 3 }}>Селектор</div>
                <code style={{ display: "block", fontSize: 11, color: "var(--text)", background: "var(--bg)", padding: "6px 8px", borderRadius: 4, wordBreak: "break-all", fontFamily: "ui-monospace, monospace", marginBottom: 10, border: "1px solid var(--border-light)" }}>{p.selector}</code>
                <div style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 3 }}>Ожидаемое поведение</div>
                <div style={{ fontSize: 13, lineHeight: 1.5, color: "var(--text)", marginBottom: 10 }}>{p.expected}</div>
                {p.story && <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--text-muted)", marginBottom: 10 }}><Icon name="list-checks" size={12} /> user story: <code style={{ color: "var(--accent)", fontWeight: 700 }}>{p.story}</code></div>}

                {p.broken && (
                  <div style={{ padding: 8, background: "var(--error-bg)", borderRadius: 5, marginBottom: 10, display: "flex", alignItems: "flex-start", gap: 6 }}>
                    <Icon name="alert-triangle" size={13} style={{ color: "#991b1b", marginTop: 1 }} />
                    <div style={{ fontSize: 11, color: "#991b1b", lineHeight: 1.4 }}><strong>Селектор сломан 3 дня.</strong> Последняя проверка Playwright: 22.04 03:14 UTC — элемент не найден.</div>
                  </div>
                )}

                {p.mode === "qa" && (
                  <div style={{ display: "flex", gap: 5 }}>
                    <button className="btn btn--sm" style={{ flex: 1, background: "var(--success-bg)", color: "#065f46", justifyContent: "center" }}><Icon name="check" size={12} /> Verified</button>
                    <button className="btn btn--sm" style={{ flex: 1, background: "var(--error-bg)", color: "#991b1b", justifyContent: "center" }}><Icon name="alert-triangle" size={12} /> Broken</button>
                    <button className="btn btn--ghost btn--sm" style={{ flex: 1, justifyContent: "center" }}>Skip</button>
                  </div>
                )}
                {p.mode === "training" && (
                  <div style={{ padding: 8, background: "var(--accent-subtle)", borderRadius: 5, fontSize: 11, color: "#78350f", lineHeight: 1.5 }}>
                    <strong>Инструкция:</strong> нажмите кнопку <code style={{ background: "rgba(194,65,12,0.12)", padding: "1px 4px", borderRadius: 3 }}>Одобрить</code> — КП перейдёт на этап «Спецификации».
                  </div>
                )}

                {p.history && (
                  <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid var(--border-light)" }}>
                    <div style={{ fontSize: 10, color: "var(--text-muted)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>История · {p.history.length}</div>
                    {p.history.map((h, i) => (
                      <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 6, fontSize: 11, color: "var(--text-muted)", padding: "3px 0" }}>
                        <span className={`dot dot--${h.result === "verified" ? "verified" : "broken"}`} style={{ marginTop: 5 }} />
                        <div style={{ flex: 1 }}>
                          <div><strong style={{ color: "var(--text)", fontWeight: 600 }}>{h.result}</strong> · {h.when}</div>
                          <div style={{ fontSize: 10, color: "var(--text-subtle)" }}>{h.who}{h.note ? ` — "${h.note}"` : ""}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })()}

          {/* Other pins list */}
          <div className="os-label" style={{ fontSize: 10, marginTop: 4 }}>Все пины</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {pinsToShow.map(p => {
              const color = p.mode === "training" ? "var(--primary)" : (p.broken ? "var(--error)" : (p.verified ? "var(--success)" : "var(--accent)"));
              return (
                <button key={p.n} onClick={() => setOpenPin(p.n)} style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", border: "1px solid " + (openPin === p.n ? "var(--accent)" : "var(--border-light)"),
                  borderRadius: 6, background: openPin === p.n ? "var(--accent-subtle)" : "#fff", cursor: "pointer", textAlign: "left"
                }}>
                  <span style={{ width: 20, height: 20, borderRadius: 999, background: color, color: "#fff", fontSize: 11, fontWeight: 700, display: "grid", placeItems: "center", flexShrink: 0 }}>{p.n}</span>
                  <span style={{ fontSize: 11, flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", color: "var(--text)" }}>{p.expected}</span>
                  {p.broken && <Icon name="alert-triangle" size={12} style={{ color: "var(--error)" }} />}
                  {p.verified && <Icon name="check" size={12} style={{ color: "var(--success)" }} />}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

Object.assign(window, { NodeMin, NodeStatus, NodeRich, NodeGhost, JourneyCanvas, JourneySidebar, Drawer, AnnotatedScreen, ClusterDot, RoleChips, StatusDot });
