import { headers } from "next/headers";

export type AppContext = "main" | "phmb";

export async function getAppContext(): Promise<AppContext> {
  const h = await headers();
  const ctx = h.get("x-app-context");
  return ctx === "phmb" ? "phmb" : "main";
}
