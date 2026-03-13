import html2canvas from "html2canvas";
import { compressScreenshot } from "../lib/compressScreenshot";

export async function captureScreenshot(): Promise<string> {
  console.log("[FeedbackWidget] Starting html2canvas capture...");

  const canvas = await html2canvas(document.body, {
    useCORS: true,
    allowTaint: true,
    scale: 0.75,
    logging: true,
    ignoreElements: (el) => {
      return (
        el.id === "feedback-modal" ||
        el.classList?.contains("feedback-overlay")
      );
    },
    onclone: (clonedDoc) => {
      console.log("[FeedbackWidget] onclone called, fixing oklch colors...");

      // Replace oklch() in <style> tags
      const styles = clonedDoc.querySelectorAll("style");
      styles.forEach((s) => {
        if (s.textContent?.includes("oklch")) {
          s.textContent = s.textContent.replace(/oklch\([^)]*\)/g, "#888888");
        }
      });

      // Replace oklch() in computed styles
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

      console.log("[FeedbackWidget] oklch fix complete");
    },
  });

  console.log("[FeedbackWidget] html2canvas done, canvas size:", canvas.width, "x", canvas.height);

  const rawDataUrl = canvas.toDataURL("image/png");
  console.log("[FeedbackWidget] rawDataUrl length:", rawDataUrl.length);

  const compressed = await compressScreenshot(rawDataUrl);
  console.log("[FeedbackWidget] compressed length:", compressed.length);

  return compressed;
}
