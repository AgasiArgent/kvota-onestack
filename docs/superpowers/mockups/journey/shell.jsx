/* global React */

const Icon = ({ name, size = 16, stroke = 1.75, className = "", style = {} }) => {
  const paths = {
    "play-circle": <><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></>,
    "message-circle": <><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></>,
    "newspaper": <><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/><path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/></>,
    "bar-chart-3": <><path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></>,
    "plus-circle": <><circle cx="12" cy="12" r="10"/><path d="M8 12h8"/><path d="M12 8v8"/></>,
    "users": <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>,
    "file-text": <><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><polyline points="14 2 14 8 20 8"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></>,
    "building-2": <><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/></>,
    "clipboard-list": <><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/></>,
    "map-pin": <><path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/></>,
    "calendar": <><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/></>,
    "user": <><circle cx="12" cy="8" r="4"/><path d="M6 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2"/></>,
    "message-square": <><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z"/></>,
    "git-branch": <><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></>,
    "percent": <><line x1="19" y1="5" x2="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/></>,
    "settings": <><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></>,
    "split-square-horizontal": <><path d="M8 19H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h3"/><path d="M16 5h3a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-3"/><line x1="12" y1="4" x2="12" y2="20"/></>,
    "layout-grid": <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></>,
    "trash-2": <><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></>,
    "map": <><path d="M9 3 3 6v15l6-3 6 3 6-3V3l-6 3Z"/><path d="M9 3v15"/><path d="M15 6v15"/></>,
    "clock": <><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></>,
    "search": <><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></>,
    "chevron-right": <><polyline points="9 18 15 12 9 6"/></>,
    "chevron-down": <><polyline points="6 9 12 15 18 9"/></>,
    "chevron-left": <><polyline points="15 18 9 12 15 6"/></>,
    "x": <><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>,
    "check": <><polyline points="20 6 9 17 4 12"/></>,
    "check-circle": <><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></>,
    "alert-triangle": <><path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></>,
    "sparkles": <><path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/></>,
    "ghost": <><path d="M9 10h.01"/><path d="M15 10h.01"/><path d="M12 2a8 8 0 0 0-8 8v12l3-3 2.5 2.5L12 19l2.5 2.5L17 19l3 3V10a8 8 0 0 0-8-8z"/></>,
    "layers": <><path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.91a1 1 0 0 0 0-1.83Z"/><path d="M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12"/><path d="M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17"/></>,
    "filter": <><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></>,
    "eye": <><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></>,
    "image": <><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></>,
    "edit": <><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></>,
    "external-link": <><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></>,
    "book-open": <><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2Z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7Z"/></>,
    "plus": <><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></>,
    "mouse-pointer-click": <><path d="m9 9 5 12 1.774-5.226L21 14 9 9z"/><path d="M16.071 16.071 18.9 18.9"/><path d="M7.188 2.239 8.71 6.308"/><path d="M2.24 7.188 6.31 8.71"/><path d="m3.29 3.29 3.18 3.18"/></>,
    "refresh-cw": <><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></>,
    "more-horizontal": <><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></>,
    "pin": <><path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/></>,
    "camera": <><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></>,
    "copy": <><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></>,
    "zoom-in": <><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></>,
    "zoom-out": <><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/></>,
    "maximize": <><path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></>,
    "arrow-right": <><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></>,
    "rocket": <><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></>,
    "list-checks": <><path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/></>,
  };
  const inner = paths[name] || paths["file-text"];
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
      {inner}
    </svg>
  );
};

const OS_MENU = [
  { title: "Главное", items: [
    { icon: "play-circle", label: "Обучение", href: "/training" },
    { icon: "message-circle", label: "Сообщения", href: "/messages" },
    { icon: "newspaper", label: "Обновления", href: "/changelog", badge: 3 },
    { icon: "bar-chart-3", label: "Обзор", href: "/dashboard" },
    { icon: "split-square-horizontal", label: "Распределение", href: "/procurement/distribution", badge: 12 },
    { icon: "layout-grid", label: "Канбан закупок", href: "/procurement/kanban" },
    { icon: "map", label: "Карта путей", href: "/journey", active: true, isNew: true },
  ]},
  { title: "Реестры", items: [
    { icon: "users", label: "Клиенты", href: "/customers" },
    { icon: "file-text", label: "Коммерческие предложения", href: "/quotes" },
    { icon: "building-2", label: "Поставщики", href: "/suppliers" },
    { icon: "clipboard-list", label: "Позиции", href: "/positions" },
    { icon: "map-pin", label: "Локации", href: "/locations" },
  ]},
  { title: "Финансы", items: [
    { icon: "file-text", label: "Контроль платежей", href: "/finance" },
    { icon: "calendar", label: "Календарь", href: "/payments/calendar" },
  ]},
  { title: "Администрирование", items: [
    { icon: "user", label: "Пользователи", href: "/admin/users" },
    { icon: "message-square", label: "Обращения", href: "/admin/feedback" },
    { icon: "git-branch", label: "Маршруты закупок", href: "/admin/routing" },
    { icon: "trash-2", label: "Корзина", href: "/quotes/trash" },
    { icon: "settings", label: "Настройки", href: "/settings" },
  ]},
];

const Sidebar = ({ activeHref = "/journey" }) => {
  return (
    <aside style={{
      width: 240, flexShrink: 0, background: "var(--sidebar)", borderRight: "1px solid var(--border-light)",
      display: "flex", flexDirection: "column", height: "100%", overflow: "hidden"
    }}>
      <div style={{ padding: "18px 20px 14px", display: "flex", alignItems: "center", gap: 10, borderBottom: "1px solid var(--border-light)" }}>
        <div style={{ width: 28, height: 28, borderRadius: 8, background: "var(--primary)", color: "#fff", display: "grid", placeItems: "center", fontWeight: 700, fontSize: 13, letterSpacing: "-0.02em" }}>k</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: "var(--primary)", letterSpacing: "-0.02em" }}>kvotaflow</div>
      </div>
      <nav className="scroll-slim" style={{ flex: 1, overflowY: "auto", padding: "12px 10px" }}>
        {OS_MENU.map((section, i) => (
          <div key={i} style={{ marginBottom: 14 }}>
            <div className="os-label" style={{ padding: "4px 10px 6px", fontSize: 10 }}>{section.title}</div>
            {section.items.map((item, j) => {
              const isActive = item.href === activeHref || item.active;
              return (
                <a key={j} href="#" style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "7px 10px", borderRadius: 6,
                  fontSize: 13, fontWeight: isActive ? 600 : 500,
                  color: isActive ? "var(--text)" : "var(--text-muted)",
                  background: isActive ? "rgba(87,83,78,0.09)" : "transparent",
                  textDecoration: "none", marginBottom: 1, position: "relative"
                }} onClick={e => e.preventDefault()}>
                  <Icon name={item.icon} size={15} />
                  <span style={{ flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.label}</span>
                  {item.badge && <span style={{ background: "var(--accent)", color: "#fff", fontSize: 10, fontWeight: 700, padding: "1px 6px", borderRadius: 10, minWidth: 18, textAlign: "center" }}>{item.badge}</span>}
                  {item.isNew && <span style={{ background: "var(--accent-subtle)", color: "var(--accent)", fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 3, letterSpacing: "0.04em" }}>NEW</span>}
                </a>
              );
            })}
          </div>
        ))}
      </nav>
      <div style={{ padding: "10px 14px", borderTop: "1px solid var(--border-light)", display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ width: 28, height: 28, borderRadius: "50%", background: "linear-gradient(135deg, #C2410C, #9A3412)", color: "#fff", display: "grid", placeItems: "center", fontSize: 12, fontWeight: 700 }}>АБ</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>Агаси Б.</div>
          <div style={{ fontSize: 10, color: "var(--text-muted)" }}>admin · top_manager</div>
        </div>
      </div>
    </aside>
  );
};

Object.assign(window, { Icon, Sidebar });
