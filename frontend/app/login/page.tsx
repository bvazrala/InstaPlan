"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { MapPin } from "lucide-react";
import { supabase } from "@/lib/supabase";
import { PrimaryButton } from "@/components/ui/primitives";

/** Email + password login through Supabase Auth (R20). */
export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const signIn = async () => {
    if (!supabase) return router.push("/");
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) setError(error.message);
    else router.push("/");
  };

  return (
    <main className="flex min-h-dvh items-center justify-center bg-[#f7f7f8] p-4">
      <div className="w-full max-w-sm space-y-4 rounded-3xl border border-line bg-white p-6">
        <div className="flex items-center gap-3">
          <span className="brand-gradient flex h-10 w-10 items-center justify-center rounded-xl text-white"><MapPin size={18} /></span>
          <div className="leading-tight">
            <p className="text-[15px] font-semibold">InstaPlan</p>
            <p className="text-xs text-muted">Plan trips right in the group chat</p>
          </div>
        </div>
        {!supabase && (
          <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800">
            Supabase isn&apos;t configured, so the app runs on demo data. Set the variables in <code>.env.local</code> to enable login.
          </p>
        )}
        <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" placeholder="Email"
          className="w-full rounded-xl bg-surface px-3 py-2.5 text-sm outline-none placeholder:text-muted" />
        <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="Password"
          onKeyDown={(e) => e.key === "Enter" && signIn()}
          className="w-full rounded-xl bg-surface px-3 py-2.5 text-sm outline-none placeholder:text-muted" />
        {error && <p className="text-xs text-red-600">{error}</p>}
        <PrimaryButton onClick={signIn}>{supabase ? "Log in" : "Continue with demo data"}</PrimaryButton>
      </div>
    </main>
  );
}
