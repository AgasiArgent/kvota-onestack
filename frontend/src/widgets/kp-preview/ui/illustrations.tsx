/**
 * KP raster illustrations. Mirror the assets used by the Python renderer
 * (`services/static/kp/*.png`) so preview and PDF show the same image.
 *
 * Served from `frontend/public/static/kp/` — Wave 1 setup copied the
 * source PNGs there alongside the backend static directory.
 */

/* eslint-disable @next/next/no-img-element */
export function HeavyMachineryIllu() {
  return (
    <img
      src="/static/kp/hero-machinery.png"
      alt=""
      style={{
        width: "100%",
        height: "100%",
        objectFit: "contain",
        objectPosition: "right center",
        display: "block",
      }}
    />
  );
}

export function MountainIllu() {
  return (
    <img
      src="/static/kp/mountains.png"
      alt=""
      style={{
        width: "100%",
        height: "100%",
        objectFit: "contain",
        objectPosition: "right bottom",
        display: "block",
      }}
    />
  );
}
