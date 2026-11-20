"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Health = {
  status: string;
  app: string;
  environment: string;
};

type FetchState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: Health };

export default function Home() {
  const [state, setState] = useState<FetchState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
        if (!res.ok) {
          throw new Error(`Backend returned ${res.status}`);
        }
        const data = (await res.json()) as Health;
        if (!cancelled) {
          setState({ kind: "ready", data });
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : "Unknown error";
          setState({ kind: "error", message });
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-6 px-4 py-16">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">ORFlow</h1>
        <p className="text-sm opacity-70">
          Operating room scheduling &amp; utilization. Portfolio project —
          synthetic data only, not a clinical system.
        </p>
      </header>

      <section
        className="rounded-lg border border-black/10 p-4 dark:border-white/15"
        aria-live="polite"
      >
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide opacity-60">
          Backend status
        </h2>
        {state.kind === "loading" && (
          <p className="text-sm opacity-70">Checking backend…</p>
        )}
        {state.kind === "error" && (
          <p className="text-sm text-red-600 dark:text-red-400">
            Could not reach backend: {state.message}
          </p>
        )}
        {state.kind === "ready" && (
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="opacity-60">Status</dt>
            <dd className="font-medium">{state.data.status}</dd>
            <dt className="opacity-60">App</dt>
            <dd className="font-medium">{state.data.app}</dd>
            <dt className="opacity-60">Environment</dt>
            <dd className="font-medium">{state.data.environment}</dd>
          </dl>
        )}
      </section>
    </main>
  );
}
