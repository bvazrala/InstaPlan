// Auth discovery: explicit local demo sessions, otherwise normal Supabase login.
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { API_URL } from "./config";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
let client: SupabaseClient | null = null;
export const supabaseConfigured = !!(url && key && /^https?:\/\/[^\s/\[\]]+/.test(url));
export function getSupabaseClient(): SupabaseClient | null {
  if (!client && supabaseConfigured) client = createClient(url!, key!);
  return client;
}
export type ClientSession = { user: { id: string }; access_token: string; demoMode: boolean };
let discovery: Promise<ClientSession | null> | null = null;
const localHost = (hostname: string) => ["localhost", "127.0.0.1", "[::1]", "::1"].includes(hostname);
async function discoverDemo(): Promise<ClientSession | null> {
  if (typeof window === "undefined" || !localHost(window.location.hostname) || !localHost(new URL(API_URL).hostname)) return null;
  try {
    const response = await fetch(`${API_URL}/health`, { cache: "no-store" });
    if (!response.ok) return null;
    const state = await response.json();
    if (state.demoMode === true && state.demoUserId === "demo-you") {
      return { user: { id: "demo-you" }, access_token: "instaplan-local-demo", demoMode: true };
    }
  } catch { /* Normal authentication handles an unavailable demo backend. */ }
  return null;
}
export async function getClientSession(): Promise<ClientSession | null> {
  discovery ??= discoverDemo();
  const demo = await discovery;
  if (demo) return demo;
  const auth = getSupabaseClient();
  if (!auth) return null;
  const { data } = await auth.auth.getSession();
  return data.session ? { user: { id: data.session.user.id }, access_token: data.session.access_token, demoMode: false } : null;
}
export async function getAccessToken(): Promise<string | null> {
  return (await getClientSession())?.access_token ?? null;
}
