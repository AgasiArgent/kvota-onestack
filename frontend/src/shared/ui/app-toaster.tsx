"use client";

import { Toaster } from "sonner";

/**
 * Standard Toaster surface used across the app — one element per page.
 *
 * Defaults:
 * - `position="top-right"` — where toasts have always lived in OneStack
 * - `richColors` — coloured backgrounds for success / error / warning
 * - `duration: 6000` — 50% longer than Sonner's 4s default. Picked because
 *   QA and manual testers missed short-lived blocking-error toasts (3-4s)
 *   after validation fails. Long enough to read "Заполните обязательные
 *   поля: Клиент, Инкотермс, Способ доставки", short enough to not stack
 *   when users trigger several in a row.
 *
 * Extracted to one component to stop every new page copy-pasting its own
 * Toaster with slightly-different settings.
 */
export function AppToaster() {
  return <Toaster position="top-right" richColors toastOptions={{ duration: 6000 }} />;
}
