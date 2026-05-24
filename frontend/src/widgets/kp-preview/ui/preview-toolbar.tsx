"use client";

/**
 * Preview-pane toolbar: page-count label, zoom decrement/value/increment/reset,
 * and a `downloadSlot` for the download CTA (kept slot-based so the feature
 * slice owns its own button styling — REQ-13.1 / REQ-12).
 */

import type { ReactNode } from "react";

import styles from "./kp-preview.module.css";

const MIN_ZOOM = 0.3;
const MAX_ZOOM = 1.2;
const ZOOM_STEP = 0.1;
const DEFAULT_ZOOM = 0.7;

function roundZoom(z: number): number {
  return Math.round(z * 100) / 100;
}

interface PreviewToolbarProps {
  zoom: number;
  setZoom: React.Dispatch<React.SetStateAction<number>>;
  downloadSlot?: ReactNode;
}

export function PreviewToolbar({ zoom, setZoom, downloadSlot }: PreviewToolbarProps) {
  const handleDecrement = () => {
    setZoom((z) => Math.max(MIN_ZOOM, roundZoom(z - ZOOM_STEP)));
  };
  const handleIncrement = () => {
    setZoom((z) => Math.min(MAX_ZOOM, roundZoom(z + ZOOM_STEP)));
  };
  const handleReset = () => setZoom(DEFAULT_ZOOM);

  const percent = Math.round(zoom * 100);
  const atMin = zoom <= MIN_ZOOM + 0.001;
  const atMax = zoom >= MAX_ZOOM - 0.001;

  return (
    <div className={styles.previewToolbar}>
      <div className={styles.previewToolbarTitle}>
        Предпросмотр · A4 · 2 страницы
      </div>
      <div className={styles.previewToolbarRight}>
        <div className={styles.previewZoom}>
          <button
            type="button"
            onClick={handleDecrement}
            disabled={atMin}
            aria-label="Уменьшить масштаб"
            title="Уменьшить масштаб"
          >
            −
          </button>
          <div className={styles.previewZoomVal}>{percent}%</div>
          <button
            type="button"
            onClick={handleIncrement}
            disabled={atMax}
            aria-label="Увеличить масштаб"
            title="Увеличить масштаб"
          >
            +
          </button>
          <button
            type="button"
            onClick={handleReset}
            aria-label="Сбросить масштаб"
            title="Сбросить масштаб"
          >
            ↺
          </button>
        </div>
        {downloadSlot}
      </div>
    </div>
  );
}
