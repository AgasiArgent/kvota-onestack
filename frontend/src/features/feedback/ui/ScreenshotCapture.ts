import html2canvas from "html2canvas";
import { compressScreenshot } from "../lib/compressScreenshot";

// CSS color functions unsupported by html2canvas 1.x
const UNSUPPORTED_COLOR_RE =
  /(?:oklch|oklab|lab|lch|color-mix|light-dark)\([^)]*(?:\([^)]*\)[^)]*)*\)/g;
const FALLBACK_COLOR = "#888888";

function replaceUnsupportedColors(css: string): string {
  return css.replace(UNSUPPORTED_COLOR_RE, FALLBACK_COLOR);
}

function inlineLinkedStylesheets(clonedDoc: Document): void {
  // Convert <link> stylesheets to inline <style> with colors patched
  const links = clonedDoc.querySelectorAll('link[rel="stylesheet"]');
  links.forEach((link) => {
    try {
      // Find the matching CSSStyleSheet
      const href = link.getAttribute("href");
      if (!href) return;

      // Read CSS rules from the CSSOM
      const sheets = Array.from(clonedDoc.styleSheets);
      const sheet = sheets.find(
        (s) => s.href?.endsWith(href.split("?")[0]) || s.ownerNode === link
      );
      if (!sheet) return;

      let cssText = "";
      try {
        const rules = Array.from(sheet.cssRules);
        cssText = rules.map((r) => r.cssText).join("\n");
      } catch {
        // CORS — can't read rules, skip
        return;
      }

      if (!cssText) return;

      // Replace the <link> with an inline <style>
      const style = clonedDoc.createElement("style");
      style.textContent = replaceUnsupportedColors(cssText);
      link.replaceWith(style);
    } catch {
      // Skip this stylesheet
    }
  });
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
      // 1. Inline linked stylesheets with colors patched
      inlineLinkedStylesheets(clonedDoc);

      // 2. Patch remaining <style> tags
      const styles = clonedDoc.querySelectorAll("style");
      styles.forEach((s) => {
        if (s.textContent) {
          s.textContent = replaceUnsupportedColors(s.textContent);
        }
      });

      // 3. Patch inline styles with unsupported computed colors
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
                replaceUnsupportedColors(val),
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
