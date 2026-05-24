"use client";

/**
 * Split-screen composition: form on the left, live preview on the right.
 *
 * `useKpState()` lives at the top so a single source of truth flows into
 * both panes — every keystroke in the form updates the preview within
 * one render cycle (REQ-11.2).
 *
 * Layout: a CSS grid that collapses to a single column below 1024px so
 * the page is usable on mobile (preview falls below the form per the
 * design plan; we do not lock the preview to read-only at narrow widths
 * since the underlying inputs already handle it).
 */

import { AppToaster } from "@/shared/ui/app-toaster";
import { useKpState } from "@/entities/kp-proposal";
import { KpForm } from "@/widgets/kp-form";
import { KpPreview } from "@/widgets/kp-preview";
import { DownloadKpPdfButton } from "@/features/kp-pdf-download";

import styles from "./kp-builder-page.module.css";

export function KpBuilderPage() {
  const { data, setData, clear, loadExample, zoom, setZoom } = useKpState();

  return (
    <div className={styles.root}>
      <div className={styles.formPane}>
        <KpForm
          data={data}
          setData={setData}
          onClear={clear}
          onLoadExample={loadExample}
        />
      </div>
      <div className={styles.previewPane}>
        <KpPreview
          data={data}
          zoom={zoom}
          setZoom={setZoom}
          downloadSlot={<DownloadKpPdfButton data={data} />}
        />
      </div>
      <AppToaster />
    </div>
  );
}
