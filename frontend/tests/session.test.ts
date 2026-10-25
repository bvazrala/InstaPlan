import { afterEach, beforeEach, expect, it, vi } from "vitest";
const { createClient, getSession } = vi.hoisted(() => ({ createClient: vi.fn(), getSession: vi.fn() }));
vi.mock("@supabase/supabase-js", () => ({ createClient }));
beforeEach(() => {
  vi.resetModules();
  createClient.mockReset(); getSession.mockReset();
  createClient.mockReturnValue({ auth: { getSession } });
  getSession.mockResolvedValue({ data: { session: { user: { id: "real-user" }, access_token: "normal-token" } } });
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co");
  vi.stubEnv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "publishable-test");
});
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });
it("uses the fixed local identity without creating a Supabase client", async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ demoMode: true, demoUserId: "demo-you" }) });
  vi.stubGlobal("fetch", fetch);
  const { getClientSession, getAccessToken } = await import("@/lib/supabase");
  expect((await getClientSession())?.user.id).toBe("demo-you");
  expect(await getAccessToken()).toBe("instaplan-local-demo");
  expect(createClient).not.toHaveBeenCalled();
  expect(fetch).toHaveBeenCalledTimes(1);
});
it("preserves normal Supabase sessions when demo mode is disabled", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ demoMode: false }) }));
  const { getClientSession } = await import("@/lib/supabase");
  expect(await getClientSession()).toEqual({ user: { id: "real-user" }, access_token: "normal-token", demoMode: false });
  expect(createClient).toHaveBeenCalledTimes(1);
});
it("never discovers demo sessions from an external frontend", async () => {
  vi.stubGlobal("window", { location: { hostname: "instaplan.example" } });
  const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  const { getClientSession } = await import("@/lib/supabase");
  expect((await getClientSession())?.demoMode).toBe(false);
  expect(fetch).not.toHaveBeenCalled();
});
