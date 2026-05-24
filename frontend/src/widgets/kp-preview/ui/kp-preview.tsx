"use client";

/**
 * Right-pane composition: toolbar + scaled А4 preview pages.
 *
 * Scaling strategy: each page is rendered at its native 794×1123 CSS-pixel
 * footprint, then wrapped in a div with `transform: scale(zoom)` and an
 * explicit scaled width/height so the surrounding flex layout doesn't
 * reflow as the user zooms. `transform-origin: top left` keeps the
 * scaled page anchored to the corner of its slot.
 */

import { CSSProperties, ReactNode } from "react";

import { BRANDING } from "@/entities/kp-proposal";
import type { KpProposal } from "@/entities/kp-proposal";

import { KpPage1 } from "./kp-page-1";
import { KpPage2 } from "./kp-page-2";
import styles from "./kp-preview.module.css";
import { PreviewToolbar } from "./preview-toolbar";

const PAGE_WIDTH = 794;
const PAGE_HEIGHT = 1123;

interface KpPreviewProps {
  data: KpProposal;
  zoom: number;
  setZoom: React.Dispatch<React.SetStateAction<number>>;
  downloadSlot?: ReactNode;
}

export function KpPreview({ data, zoom, setZoom, downloadSlot }: KpPreviewProps) {
  // CSS custom properties consumed by every .kpPage rule and section
  // header — keeps brand colors out of the CSS module so a future brand
  // swap is one prop change away.
  const brandVars: CSSProperties = {
    ["--kp-primary-blue" as string]: BRANDING.primaryBlue,
    ["--kp-primary-red" as string]: BRANDING.primaryRed,
    ["--kp-accent-cream" as string]: BRANDING.accentCream,
  };

  const wrapStyle: CSSProperties = {
    transform: `scale(${zoom})`,
    width: `${PAGE_WIDTH * zoom}px`,
    height: `${PAGE_HEIGHT * zoom}px`,
  };

  // The inner wrapper keeps the actual page at its native size (so the
  // browser does the transform once at the GPU layer) while the outer
  // wrapper takes the scaled footprint that the surrounding layout sees.
  const innerWrap: CSSProperties = {
    width: `${PAGE_WIDTH}px`,
    height: `${PAGE_HEIGHT}px`,
    transformOrigin: "top left",
  };

  return (
    <div className={styles.previewRoot} style={brandVars}>
      <PreviewToolbar zoom={zoom} setZoom={setZoom} downloadSlot={downloadSlot} />
      <div className={styles.previewStage}>
        <div className={styles.previewWrap} style={wrapStyle}>
          <div style={innerWrap}>
            <KpPage1 data={data} />
          </div>
        </div>
        <div className={styles.previewWrap} style={wrapStyle}>
          <div style={innerWrap}>
            <KpPage2 data={data} />
          </div>
        </div>
      </div>
    </div>
  );
}
