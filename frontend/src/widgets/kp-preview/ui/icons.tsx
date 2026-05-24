/**
 * KP-local SVG icon set, ported from the design prototype's `Icons.jsx`.
 *
 * These are intentionally separate from the app-wide lucide-react set:
 * - They stay inside the preview widget so a future brand swap can change
 *   the visual language without touching the rest of the app.
 * - Stroke is currentColor so each icon picks up its container's `color`
 *   (the section header sets `color: white` on a blue chip).
 *
 * Style notes:
 * - viewBox is 24×24 unless otherwise stated.
 * - All icons render at the size their CSS container dictates (kpFieldIco,
 *   iconSq, .ico, etc.) — they take no width/height props of their own.
 */

import type { SVGProps } from "react";

type IcoProps = SVGProps<SVGSVGElement>;

function Ico({ children, ...props }: IcoProps & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {children}
    </svg>
  );
}

export function UserBadge(props: IcoProps) {
  return (
    <Ico {...props}>
      <circle cx="12" cy="9" r="3" />
      <path d="M6 20a6 6 0 0 1 12 0" />
    </Ico>
  );
}

export function Doc(props: IcoProps) {
  return (
    <Ico {...props}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </Ico>
  );
}

export function UserTie(props: IcoProps) {
  return (
    <Ico {...props}>
      <circle cx="12" cy="8" r="3" />
      <path d="M6 20c0-3 3-5 6-5s6 2 6 5" />
      <path d="M11 13l1 2 1-2" />
    </Ico>
  );
}

export function Cal(props: IcoProps) {
  return (
    <Ico {...props}>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 3v4M16 3v4" />
    </Ico>
  );
}

export function Phone(props: IcoProps) {
  return (
    <Ico {...props}>
      <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
    </Ico>
  );
}

export function Clock(props: IcoProps) {
  return (
    <Ico {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </Ico>
  );
}

export function Mail(props: IcoProps) {
  return (
    <Ico {...props}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </Ico>
  );
}

export function Ruble(props: IcoProps) {
  return (
    <Ico {...props}>
      <path d="M8 4h6a4 4 0 0 1 0 8H8" />
      <path d="M8 4v16M5 12h9M5 16h6" />
    </Ico>
  );
}

export function Pin(props: IcoProps) {
  return (
    <Ico {...props}>
      <path d="M12 22s7-7.5 7-13a7 7 0 0 0-14 0c0 5.5 7 13 7 13z" />
      <circle cx="12" cy="9" r="2.5" />
    </Ico>
  );
}

export function Pkg(props: IcoProps) {
  return (
    <Ico {...props}>
      <path d="m3 7 9-4 9 4-9 4-9-4z" />
      <path d="M3 7v10l9 4 9-4V7" />
      <path d="M12 11v10" />
    </Ico>
  );
}

export function Truck(props: IcoProps) {
  return (
    <Ico {...props}>
      <path d="M3 7h11v9H3z" />
      <path d="M14 10h4l3 3v3h-7z" />
      <circle cx="7" cy="18" r="1.8" />
      <circle cx="17" cy="18" r="1.8" />
    </Ico>
  );
}

export function List(props: IcoProps) {
  return (
    <Ico {...props}>
      <path d="M8 6h13M8 12h13M8 18h13" />
      <circle cx="3.5" cy="6" r="1" />
      <circle cx="3.5" cy="12" r="1" />
      <circle cx="3.5" cy="18" r="1" />
    </Ico>
  );
}

export function Settings(props: IcoProps) {
  return (
    <Ico {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1" />
    </Ico>
  );
}

export function Gear(props: IcoProps) {
  return (
    <Ico {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.6 1.6 0 0 0 .3 1.7l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.7-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.7.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.7 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.7l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.7.3 1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.7-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.7 1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z" />
    </Ico>
  );
}

export function Tools(props: IcoProps) {
  return (
    <Ico {...props}>
      <path d="M14.7 6.3 4 17v3h3l10.7-10.7" />
      <path d="m14 7 3 3" />
    </Ico>
  );
}

export function Wrench(props: IcoProps) {
  return (
    <Ico {...props}>
      <path d="m14.7 6.3 4 4-9.5 9.5a2.8 2.8 0 1 1-4-4z" />
    </Ico>
  );
}

export function Globe(props: IcoProps) {
  return (
    <Ico {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a13 13 0 0 1 0 18M12 3a13 13 0 0 0 0 18" />
    </Ico>
  );
}

export function Shield(props: IcoProps) {
  return (
    <Ico {...props}>
      <path d="M12 2 4 5v6c0 5 4 9 8 11 4-2 8-6 8-11V5l-8-3z" />
    </Ico>
  );
}

export function ShieldCheck(props: IcoProps) {
  return (
    <Ico {...props}>
      <path d="M12 2 4 5v6c0 5 4 9 8 11 4-2 8-6 8-11V5l-8-3z" />
      <path d="m9 12 2 2 4-4" />
    </Ico>
  );
}

export function ShieldDoc(props: IcoProps) {
  return (
    <Ico {...props}>
      <path d="M12 2 4 5v6c0 5 4 9 8 11 4-2 8-6 8-11V5l-8-3z" />
      <path d="M9 11h6M9 14h4" />
    </Ico>
  );
}

export function Cog(props: IcoProps) {
  return (
    <Ico {...props}>
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 4v2M12 18v2M4 12h2M18 12h2M6.4 6.4l1.4 1.4M16.2 16.2l1.4 1.4M6.4 17.6l1.4-1.4M16.2 7.8l1.4-1.4" />
    </Ico>
  );
}

export function Handshake(props: IcoProps) {
  return (
    <Ico {...props}>
      <path d="m11 17 2 2 4-4" />
      <path d="M3 12 8 7l4 4 4-4 5 5-5 5-4-4-4 4z" />
    </Ico>
  );
}

export function Mtn(props: IcoProps) {
  return (
    <Ico {...props}>
      <path d="m3 19 6-9 4 6 3-4 5 7z" />
    </Ico>
  );
}
