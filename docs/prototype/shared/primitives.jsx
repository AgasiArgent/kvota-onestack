/* global React */
/**
 * prototype/shared/primitives.jsx
 * Mirrors: shared/ui/* + entities/location/ui/location-chip.tsx + entities/user/ui/user-avatar-chip.tsx
 */
const { useEffect: pmUseEffect, useRef: pmUseRef, useState: pmUseState } = React;

// ---------- cn ----------
function cn(...args) { return args.filter(Boolean).join(" "); }

// ---------- Icon (Lucide-style SVGs, stroke-based) ----------
const ICONS = {
  chevronRight: "M9 18l6-6-6-6",
  chevronLeft:  "M15 18l-6-6 6-6",
  chevronDown:  "M6 9l6 6 6-6",
  chevronUp:    "M18 15l-6-6-6 6",
  arrowUp:      "M12 19V5 M5 12l7-7 7 7",
  arrowDown:    "M12 5v14 M19 12l-7 7-7-7",
  plus:         "M12 5v14 M5 12h14",
  x:            "M18 6L6 18 M6 6l12 12",
  factory:      "M2 20h20 M17 20V8l-5 3V8l-5 3V4H4v16",
  warehouse:    "M22 8.35V20a2 2 0 01-2 2H4a2 2 0 01-2-2V8.35a2 2 0 011.26-1.86l8-3.2a2 2 0 011.48 0l8 3.2A2 2 0 0122 8.35Z M6 18h12 M6 14h12",
  shield:       "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z M9 12l2 2 4-4",
  building:     "M3 21h18 M5 21V7l8-4v18 M13 9h4v12 M9 9v.01 M9 13v.01 M9 17v.01",
  user:         "M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2 M12 11a4 4 0 100-8 4 4 0 000 8z",
  globe:        "M12 22a10 10 0 100-20 10 10 0 000 20z M2 12h20 M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z",
  message:      "M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z",
  alert:        "M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z M12 9v4 M12 17h.01",
  check:        "M20 6L9 17l-5-5",
  clock:        "M12 22a10 10 0 100-20 10 10 0 000 20z M12 6v6l4 2",
  sparkles:     "M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5z M19 13l.9 2.7L22 17l-2.1.9L19 21l-.9-2.7L16 17l2.1-.9z",
  pencil:       "M12 20h9 M16.5 3.5a2.121 2.121 0 113 3L7 19l-4 1 1-4z",
  trash:        "M3 6h18 M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2 M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6",
  search:       "M21 21l-4.35-4.35 M11 19a8 8 0 100-16 8 8 0 000 16z",
  truck:        "M1 3h15v13H1z M16 8h4l3 3v5h-7 M5.5 21a2.5 2.5 0 100-5 2.5 2.5 0 000 5z M18.5 21a2.5 2.5 0 100-5 2.5 2.5 0 000 5z",
  shieldCheck:  "M20 12V5l-8-3-8 3v7c0 5 4 8 8 9 4-1 8-4 8-9z M9 12l2 2 4-4",
  settings:     "M12 15a3 3 0 100-6 3 3 0 000 6z M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9c.36.15.67.4.9.74.23.34.35.74.35 1.16 0 .42-.12.82-.35 1.16-.23.34-.54.59-.9.74z",
  home:         "M3 12l9-9 9 9 M5 10v10h14V10",
  grid:         "M3 3h7v7H3z M14 3h7v7h-7z M14 14h7v7h-7z M3 14h7v7H3z",
  mapPin:       "M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z M12 10a3 3 0 100-6 3 3 0 000 6z",
  refresh:      "M23 4v6h-6 M1 20v-6h6 M3.51 9a9 9 0 0114.85-3.36L23 10 M20.49 15A9 9 0 015.64 18.36L1 14",
};

function Icon({ name, size = 16, className, strokeWidth = 2, ...rest }) {
  const d = ICONS[name];
  if (!d) return null;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true" {...rest}>
      {d.split(" M").map((p, i) => (<path key={i} d={i === 0 ? p : "M" + p} />))}
    </svg>
  );
}

// ---------- CountryFlag ----------
const FLAG_OFFSET = 127397;
function CountryFlag({ iso2, size = 14 }) {
  if (!iso2) return null;
  const u = iso2.toUpperCase();
  if (u.length !== 2) return null;
  const flag = String.fromCodePoint(u.charCodeAt(0) + FLAG_OFFSET, u.charCodeAt(1) + FLAG_OFFSET);
  return <span style={{ fontSize: size, lineHeight: 1 }} aria-hidden>{flag}</span>;
}

// ---------- LocationChip ----------
const TYPE_ICON = { supplier: "factory", hub: "warehouse", customs: "shield", own_warehouse: "building", client: "user" };

function LocationChip({ location, variant = "solid", size = "md", label, className }) {
  const isWildcard = variant === "wildcard";
  const isGhost = variant === "ghost";

  const resolvedLabel = label ?? (location ? (location.city && location.country ? `${location.country} · ${location.city}` : (location.name ?? location.country ?? "—")) : "—");

  const variantCls = isWildcard
    ? "chip chip--wildcard"
    : isGhost ? "chip chip--ghost" : "chip chip--solid";
  const sizeCls = size === "sm" ? "chip--sm" : "";

  let leading = null;
  if (!isWildcard && location) {
    if (location.iso2) leading = <CountryFlag iso2={location.iso2} size={size === "sm" ? 12 : 14} />;
    else if (location.type) leading = <Icon name={TYPE_ICON[location.type] ?? "mapPin"} size={size === "sm" ? 11 : 13} />;
    else leading = <Icon name="globe" size={size === "sm" ? 11 : 13} />;
  }

  return (
    <span className={cn(variantCls, sizeCls, className)}>
      {leading}
      <span>{resolvedLabel}</span>
    </span>
  );
}

// ---------- Badge ----------
function Badge({ children, tone = "neutral", size = "md", className }) {
  return <span className={cn("badge", `badge--${tone}`, size === "sm" && "badge--sm", className)}>{children}</span>;
}

// ---------- Button ----------
function Button({ children, variant = "secondary", size = "md", icon, onClick, disabled, type = "button", className, ...rest }) {
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={cn("btn", `btn--${variant}`, size === "sm" && "btn--sm", className)} {...rest}>
      {icon && <Icon name={icon} size={size === "sm" ? 13 : 15} />}
      {children}
    </button>
  );
}

// ---------- Card ----------
function Card({ children, className, padded = true }) {
  return <section className={cn("card", padded && "card--padded", className)}>{children}</section>;
}

// ---------- Avatar ----------
function avatarColor(seed) {
  // 5 stable warm hashes — no cold blue (design-system: "Warm, not cold")
  const colors = [
    "oklch(0.72 0.12 35)",
    "oklch(0.72 0.12 75)",
    "oklch(0.68 0.13 150)",
    "oklch(0.70 0.12 20)",
    "oklch(0.70 0.10 110)",
  ];
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0;
  return colors[Math.abs(h) % colors.length];
}

function UserAvatarChip({ user, size = "md", showEmail = false, className }) {
  if (!user) return <span className="user-chip user-chip--empty">Не назначен</span>;
  const initials = user.name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  const bg = avatarColor(user.id ?? user.name);
  return (
    <span className={cn("user-chip", size === "sm" && "user-chip--sm", className)}>
      <span className="user-chip__avatar" style={{ background: bg }}>{initials}</span>
      <span className="user-chip__meta">
        <span className="user-chip__name">{user.name}</span>
        {showEmail && <span className="user-chip__email">{user.email}</span>}
      </span>
    </span>
  );
}

// ---------- SLA Timer ----------
function formatRemaining(ms) {
  const overdue = ms < 0;
  const abs = Math.abs(ms);
  const h = Math.floor(abs / 3_600_000);
  const m = Math.floor((abs % 3_600_000) / 60_000);
  const s = Math.floor((abs % 60_000) / 1_000);
  if (overdue) return `-${h}ч ${m}м`;
  if (h < 1) return `${m}:${String(s).padStart(2, "0")}`;
  if (h < 24) return `${h}ч ${m}м`;
  const d = Math.floor(h / 24);
  return `${d}д ${h % 24}ч`;
}

function useTicker(intervalMs = 1000) {
  const [, set] = pmUseState(0);
  pmUseEffect(() => {
    const id = setInterval(() => set((x) => x + 1), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
}

function SlaTimerBadge({ assignedAt, deadlineAt, completedAt, size = "md" }) {
  useTicker(1000);
  if (!assignedAt) return <Badge tone="neutral" size={size}>—</Badge>;
  if (completedAt) return <Badge tone="success" size={size}>Готово</Badge>;
  const remaining = new Date(deadlineAt).getTime() - Date.now();
  const tone = remaining < 0 ? "error" : remaining < 24 * 3_600_000 ? "warning" : "success";
  const label = remaining < 0 ? "Просрочено" : remaining < 3_600_000 ? "Критично" : remaining < 24 * 3_600_000 ? "Горит" : "В норме";
  return (
    <span className={cn("sla", `sla--${tone}`)} title={`Крайний срок: ${new Date(deadlineAt).toLocaleString("ru-RU")}`}>
      <Icon name="clock" size={12} />
      <span className="sla__time tabular">{formatRemaining(remaining)}</span>
      <span className="sla__label">{label}</span>
    </span>
  );
}

// ---------- Tabs ----------
function Tabs({ tabs, active, onChange, className }) {
  return (
    <div className={cn("tabs", className)} role="tablist">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={active === t.key}
          onClick={() => onChange(t.key)}
          className={cn("tabs__trigger", active === t.key && "tabs__trigger--active")}
          disabled={t.disabled}
        >
          <span>{t.label}</span>
          {t.count != null && <span className="tabs__count tabular">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

// ---------- Input / Select / Textarea ----------
function Input({ label, hint, ...rest }) {
  return (
    <label className="field">
      {label && <span className="field__label">{label}</span>}
      <input {...rest} className={cn("field__input", rest.className)} />
      {hint && <span className="field__hint">{hint}</span>}
    </label>
  );
}

function Select({ label, options, value, onChange, className }) {
  return (
    <label className={cn("field", className)}>
      {label && <span className="field__label">{label}</span>}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="field__input field__input--select">
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}

// ---------- Dropdown menu (controlled) ----------
function Dropdown({ trigger, children, open, onOpenChange, align = "start" }) {
  const ref = pmUseRef(null);
  pmUseEffect(() => {
    if (!open) return;
    const close = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onOpenChange(false);
    };
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [open, onOpenChange]);
  return (
    <span className="dropdown" ref={ref}>
      {trigger}
      {open && <div className={cn("dropdown__menu", `dropdown__menu--${align}`)}>{children}</div>}
    </span>
  );
}

// ---------- Kbd ----------
function Kbd({ children }) { return <kbd className="kbd">{children}</kbd>; }

// ---------- Format helpers ----------
const rub = (n) => n == null ? "—" : new Intl.NumberFormat("ru-RU").format(Math.round(n)) + " ₽";
const num = (n) => n == null ? "—" : new Intl.NumberFormat("ru-RU").format(n);

// ---------- Export to window ----------
Object.assign(window, {
  cn, Icon, CountryFlag, LocationChip, Badge, Button, Card,
  UserAvatarChip, SlaTimerBadge, Tabs, Input, Select, Dropdown, Kbd,
  rub, num,
});
