import html2canvas from "html2canvas-pro";
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
  });

  const rawDataUrl = canvas.toDataURL("image/png");
  return compressScreenshot(rawDataUrl);
}
