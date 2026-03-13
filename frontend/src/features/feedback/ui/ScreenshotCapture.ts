import html2canvas from "html2canvas";
import { compressScreenshot } from "../lib/compressScreenshot";

// CSS color functions unsupported by html2canvas 1.x
const UNSUPPORTED_COLOR_RE = /(?:oklch|oklab|lab|lch)\([^)]*\)/g;
const FALLBACK_COLOR = "#888888";

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
      // Replace unsupported color functions in <style> tags
      const styles = clonedDoc.querySelectorAll("style");
      styles.forEach((s) => {
        if (s.textContent && UNSUPPORTED_COLOR_RE.test(s.textContent)) {
          s.textContent = s.textContent.replace(
            UNSUPPORTED_COLOR_RE,
            FALLBACK_COLOR
          );
        }
      });

      // Replace unsupported color functions in computed styles
      const all = clonedDoc.querySelectorAll("*");
      const colorProps = [
        "color",
        "background-color",
        "border-color",
        "border-top-color",
        "border-right-color",
        "border-bottom-color",
        "border-left-color",
        "outline-color",
        "text-decoration-color",
        "box-shadow",
      ];
      all.forEach((el) => {
        try {
          const cs = clonedDoc.defaultView?.getComputedStyle(el);
          if (!cs) return;
          colorProps.forEach((prop) => {
            const val = cs.getPropertyValue(prop);
            if (val && UNSUPPORTED_COLOR_RE.test(val)) {
              (el as HTMLElement).style.setProperty(
                prop,
                val.replace(UNSUPPORTED_COLOR_RE, FALLBACK_COLOR),
                "important"
              );
            }
          });
        } catch {
          // Skip inaccessible elements
        }
      });
    },
  });

  const rawDataUrl = canvas.toDataURL("image/png");
  return compressScreenshot(rawDataUrl);
}
