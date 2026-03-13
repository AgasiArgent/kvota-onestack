import html2canvas from "html2canvas";
import { compressScreenshot } from "../lib/compressScreenshot";

// CSS color functions unsupported by html2canvas 1.x
const UNSUPPORTED_FN_RE =
  /oklch|oklab|lab|lch|color-mix|light-dark/;

const COLOR_PROPS = [
  "color",
  "background-color",
  "border-color",
  "border-top-color",
  "border-right-color",
  "border-bottom-color",
  "border-left-color",
  "outline-color",
  "text-decoration-color",
];

/**
 * Convert any CSS color string to hex using the canvas 2D context.
 * This works because canvas fillStyle setter normalizes all colors to hex/rgb.
 */
function colorToHex(color: string): string {
  const ctx = document.createElement("canvas").getContext("2d");
  if (!ctx) return "#888888";
  ctx.fillStyle = color;
  return ctx.fillStyle; // returns #rrggbb or rgba(...)
}

/**
 * Replace unsupported color functions in a CSS text string.
 * Uses a regex that handles nested parentheses (e.g., color-mix()).
 */
function patchCssText(css: string): string {
  // Match function-call patterns for unsupported color functions
  // Handles one level of nested parens for color-mix(in oklch, ...)
  return css.replace(
    /(?:oklch|oklab|lab|lch|color-mix|light-dark)\([^)]*(?:\([^)]*\)[^)]*)*\)/g,
    "#888888"
  );
}

export async function captureScreenshot(): Promise<string> {
  const canvas = await html2canvas(document.body, {
    useCORS: true,
    allowTaint: true,
    scale: 0.75,
    ignoreElements: (el) => {
      return (
        el.id === "feedback-modal" ||
        el.classList?.contains("feedback-overlay")
      );
    },
    onclone: (clonedDoc) => {
      // 1. Patch all <style> tags in the cloned document
      const styles = clonedDoc.querySelectorAll("style");
      styles.forEach((s) => {
        if (s.textContent && UNSUPPORTED_FN_RE.test(s.textContent)) {
          s.textContent = patchCssText(s.textContent);
        }
      });

      // 2. Patch linked stylesheets by reading from CSSOM
      try {
        const sheets = Array.from(clonedDoc.styleSheets);
        for (const sheet of sheets) {
          try {
            const rules = Array.from(sheet.cssRules);
            const cssText = rules.map((r) => r.cssText).join("\n");
            if (UNSUPPORTED_FN_RE.test(cssText)) {
              const style = clonedDoc.createElement("style");
              style.textContent = patchCssText(cssText);
              sheet.ownerNode?.parentNode?.replaceChild(
                style,
                sheet.ownerNode
              );
            }
          } catch {
            // CORS — can't access rules
          }
        }
      } catch {
        // Skip CSSOM patching
      }

      // 3. Force all computed colors to safe rgb/hex on each element
      const view = clonedDoc.defaultView;
      if (!view) return;

      const all = clonedDoc.querySelectorAll("*");
      all.forEach((el) => {
        try {
          const cs = view.getComputedStyle(el);
          for (const prop of COLOR_PROPS) {
            const val = cs.getPropertyValue(prop);
            if (val && UNSUPPORTED_FN_RE.test(val)) {
              // Convert using canvas context (always returns hex/rgb)
              const safe = colorToHex(val);
              (el as HTMLElement).style.setProperty(prop, safe, "important");
            }
          }

          // Also check box-shadow which can contain color values
          const shadow = cs.getPropertyValue("box-shadow");
          if (shadow && UNSUPPORTED_FN_RE.test(shadow)) {
            (el as HTMLElement).style.setProperty(
              "box-shadow",
              "none",
              "important"
            );
          }
        } catch {
          // Skip inaccessible elements
        }
      });
    },
  });

  const rawDataUrl = canvas.toDataURL("image/png");
  return compressScreenshot(rawDataUrl);
}
