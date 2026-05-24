/**
 * Master Bearing logo — bearing ring + 2-line wordmark.
 *
 * Ports `BearingLogo.jsx` from the design prototype. White stroke so the
 * mark reads on the blue header bar.
 */

import styles from "./kp-preview.module.css";

interface BearingLogoProps {
  size?: number;
}

function BearingLogo({ size = 38 }: BearingLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      xmlns="http://www.w3.org/2000/svg"
    >
      <circle cx="24" cy="24" r="22" fill="none" stroke="#ffffff" strokeWidth="3" />
      <circle cx="24" cy="24" r="13" fill="none" stroke="#ffffff" strokeWidth="2" />
      {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => {
        const r = 17.5;
        const rad = (deg * Math.PI) / 180;
        const cx = 24 + Math.cos(rad) * r;
        const cy = 24 + Math.sin(rad) * r;
        return <circle key={deg} cx={cx} cy={cy} r="2.4" fill="#ffffff" />;
      })}
      <circle cx="24" cy="24" r="3" fill="#ffffff" />
    </svg>
  );
}

export function MasterBearingMark() {
  return (
    <div className={styles.kpLogo}>
      <BearingLogo size={38} />
      <div className={styles.kpLogoText}>
        <span>MASTER</span>
        <span>BEARING</span>
      </div>
    </div>
  );
}
