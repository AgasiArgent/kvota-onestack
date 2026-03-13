export const config = {
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL!,
  supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  pythonApiUrl: process.env.PYTHON_API_URL || "http://localhost:5001",
  appBaseUrl: process.env.NEXT_PUBLIC_APP_BASE_URL || "http://localhost:3000",
  legacyAppUrl: process.env.NEXT_PUBLIC_LEGACY_APP_URL || "https://kvotaflow.ru",
} as const;
