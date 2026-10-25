"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { MapPin } from "lucide-react";
import { supabase } from "@/lib/supabase";
import { PrimaryButton } from "@/components/ui/primitives";

const field = "w-full rounded-lg border border-line bg-surface px-3.5 py-3 text-sm outline-none transition placeholder:text-muted focus:border-neutral-400";

/** Email + password login through Supabase Auth (R20). */
export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const signIn = async () => {
    if (!supabase) return setError("Supabase login is not configured.");
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) setError(error.message);
    else router.push("/");
  };

  return (
    <main className="flex min-h-dvh items-center justify-center bg-white p-4 sm:bg-surface">
      <div className="w-full max-w-[350px] space-y-3 sm:border sm:border-line sm:bg-white sm:p-10">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <span className="flex size-12 items-center justify-center rounded-xl bg-brand text-white"><MapPin size={22} /></span>
          <div>
            <p className="text-2xl font-bold tracking-tight">InstaPlan</p>
            <p className="mt-1 text-sm text-muted">Plan trips right in the group chat.</p>
          </div>
        </div>
        {!supabase && (
          <p className="rounded-lg bg-amber-50 p-3 text-xs leading-snug text-amber-800">
            Supabase isn&apos;t configured. Set the public URL and publishable key in <code>.env.local</code> to enable chat.
          </p>
        )}
        <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" placeholder="Email" autoComplete="email" className={field} />
        <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="Password" autoComplete="current-password"
          onKeyDown={(e) => e.key === "Enter" && signIn()} className={field} />
        {error && <p role="alert" className="text-xs text-red-600">{error}</p>}
        <PrimaryButton onClick={signIn} className="!mt-4">Log in</PrimaryButton>
      </div>
    </main>
  );
}
