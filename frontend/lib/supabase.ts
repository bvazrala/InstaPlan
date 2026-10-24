// Supabase Auth client (login only). All data access goes through the FastAPI backend, never Supabase directly.
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

/** null until Supabase env vars are set; the app then runs on demo data without login. */
export const supabase: SupabaseClient | null = url && key ? createClient(url, key) : null;

/** The current user's access token, sent to the backend as a Bearer token. */
export async function getAccessToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}
