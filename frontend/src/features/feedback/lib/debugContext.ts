interface ConsoleEntry {
  type: "error" | "warn" | "exception";
  message: string;
  time: string;
}

interface DebugContext {
  url: string;
  title: string;
  userAgent: string;
  screenSize: string;
  consoleErrors: ConsoleEntry[];
  collectedAt: string;
}

const consoleErrors: ConsoleEntry[] = [];
let interceptorsInstalled = false;

function pushError(entry: ConsoleEntry) {
  consoleErrors.push(entry);
  if (consoleErrors.length > 10) consoleErrors.shift();
}

export function installErrorInterceptors() {
  if (interceptorsInstalled) return;
  interceptorsInstalled = true;

  const origError = console.error;
  console.error = (...args: unknown[]) => {
    pushError({
      type: "error",
      message: args.map(String).join(" "),
      time: new Date().toISOString(),
    });
    origError.apply(console, args);
  };

  const origWarn = console.warn;
  console.warn = (...args: unknown[]) => {
    pushError({
      type: "warn",
      message: args.map(String).join(" "),
      time: new Date().toISOString(),
    });
    origWarn.apply(console, args);
  };

  window.addEventListener("error", (e) => {
    pushError({
      type: "exception",
      message: `${e.message} at ${e.filename}:${e.lineno}`,
      time: new Date().toISOString(),
    });
  });
}

export function collectDebugContext(): DebugContext {
  return {
    url: window.location.href,
    title: document.title,
    userAgent: navigator.userAgent,
    screenSize: `${window.innerWidth}x${window.innerHeight}`,
    consoleErrors: consoleErrors.slice(-5),
    collectedAt: new Date().toISOString(),
  };
}
