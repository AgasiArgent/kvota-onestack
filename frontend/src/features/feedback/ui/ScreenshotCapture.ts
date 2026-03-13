import html2canvas from "html2canvas";
import { compressScreenshot } from "../lib/compressScreenshot";

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
      // Replace oklch() colors that html2canvas can't parse
      const styles = clonedDoc.querySelectorAll("style");
      styles.forEach((s) => {
        if (s.textContent?.includes("oklch")) {
          s.textContent = s.textContent.replace(/oklch\([^)]*\)/g, "#888888");
        }
      });

      const all = clonedDoc.querySelectorAll("*");
      const colorProps = [
        "color",
        "background-color",
        "border-color",
        "border-top-color",
        "border-right-color",
        "border-bottom-color",
        "border-left-color",
      ];
      all.forEach((el) => {
        try {
          const cs = clonedDoc.defaultView?.getComputedStyle(el);
          if (!cs) return;
          colorProps.forEach((prop) => {
            const val = cs.getPropertyValue(prop);
            if (val?.includes("oklch")) {
              (el as HTMLElement).style.setProperty(
                prop,
                "#888888",
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
