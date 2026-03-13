import { redirect } from "next/navigation";
import { createClient } from "@/shared/lib/supabase/server";
import { LoginForm } from "@/features/auth/login-form";

export default async function LoginPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (user) {
    redirect("/dashboard");
  }

  return <LoginForm />;
}
