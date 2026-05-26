/**
 * Master Bearing wordmark — full brand PNG (bearing icon + "MASTER BEARING"
 * text together), white-on-blue via CSS filter.
 *
 * Must stay visually in sync with the Python PDF renderer's logo:
 * `services/kp_branding.py:_load_logo()` base64-inlines the same PNG and
 * `.kp-logo__img` in `services/kp_export.py` applies the same filter.
 * If the on-screen preview drifts from the downloaded PDF, the user notices.
 */

import styles from "./kp-preview.module.css";

export function MasterBearingMark() {
  return (
    <div className={styles.kpLogo}>
      <img
        className={styles.kpLogoImg}
        src="/static/kp/master-bearing-logo.png"
        alt="Master Bearing"
      />
    </div>
  );
}
