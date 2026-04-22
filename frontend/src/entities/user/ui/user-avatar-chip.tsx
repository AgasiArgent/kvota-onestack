import type { ReactNode } from "react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

/**
 * UserAvatarChip — user identity inline chip used in assignment cells,
 * admin routing patterns, unassigned inbox dropdowns, entity notes.
 *
 * Visual strategy:
 *   - If `user.avatarUrl` is set → render the image.
 *   - Else fall back to 2-letter initials on a *warm* palette color,
 *     picked deterministically from user.id hash. No standard blue.
 *
 * Data source: Supabase `auth.users.raw_user_meta_data.avatar_url`
 * (pulled server-side and mapped into `{ id, name, email, avatarUrl }`).
 */

export interface UserAvatarChipUser {
  id: string;
  name: string;
  email?: string;
  avatarUrl?: string | null;
}

interface UserAvatarChipProps {
  user: UserAvatarChipUser;
  size?: "xs" | "sm" | "md" | "lg";
  /** Show email below name. Default false for dense usage. */
  showEmail?: boolean;
  /** Render initials-only (no name/email). Use in table cells with separate name col. */
  initialsOnly?: boolean;
  /** Optional trailing slot (e.g. "редактируется..."). */
  trailing?: ReactNode;
  className?: string;
}

/**
 * 5 warm colors — all drawn from design-system semantic tokens so they
 * respect light/dark mode overrides. The list is intentionally short:
 * avatars should identify, not categorize.
 */
const WARM_AVATAR_CLASSES = [
  "bg-accent text-white", // copper
  "bg-primary text-white", // warm stone
  "bg-success text-white", // green (warm, oklch-tuned in DS)
  "bg-warning text-white", // amber
  "bg-accent-hover text-white", // burnt copper (darker accent)
] as const;

function hashToIndex(input: string, modulo: number): number {
  // Simple FNV-1a 32-bit — stable, deterministic, no deps.
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i++) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return Math.abs(hash) % modulo;
}

function initialsFromName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "—";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

const SIZE: Record<
  NonNullable<UserAvatarChipProps["size"]>,
  { avatar: string; name: string; email: string; gap: string }
> = {
  xs: { avatar: "size-5 text-[9px]", name: "text-xs", email: "text-[10px]", gap: "gap-1.5" },
  sm: { avatar: "size-6 text-[10px]", name: "text-xs", email: "text-[10px]", gap: "gap-2" },
  md: { avatar: "size-7 text-[11px]", name: "text-sm", email: "text-xs", gap: "gap-2" },
  lg: { avatar: "size-9 text-sm", name: "text-sm", email: "text-xs", gap: "gap-3" },
};

export function UserAvatarChip({
  user,
  size = "md",
  showEmail = false,
  initialsOnly = false,
  trailing,
  className,
}: UserAvatarChipProps) {
  const s = SIZE[size];
  const fallbackCls = WARM_AVATAR_CLASSES[hashToIndex(user.id, WARM_AVATAR_CLASSES.length)];

  const avatar = (
    <Avatar className={cn(s.avatar, "flex-shrink-0")}>
      {user.avatarUrl ? (
        <AvatarImage src={user.avatarUrl} alt={user.name} />
      ) : null}
      <AvatarFallback
        className={cn(
          "font-semibold",
          user.avatarUrl ? undefined : fallbackCls,
        )}
      >
        {initialsFromName(user.name)}
      </AvatarFallback>
    </Avatar>
  );

  if (initialsOnly) {
    return <span className={className}>{avatar}</span>;
  }

  return (
    <span className={cn("inline-flex items-center min-w-0", s.gap, className)}>
      {avatar}
      <span className="flex flex-col min-w-0 leading-tight">
        <span className={cn("font-medium text-text truncate", s.name)}>{user.name}</span>
        {showEmail && user.email && (
          <span className={cn("text-text-subtle truncate", s.email)}>{user.email}</span>
        )}
      </span>
      {trailing}
    </span>
  );
}
