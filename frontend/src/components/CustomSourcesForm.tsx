"use client";

import { useState, useTransition } from "react";
import type { CustomSource } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function CustomSourcesForm({ initialSources }: { initialSources: CustomSource[] }) {
  const [sources, setSources] = useState<CustomSource[]>(initialSources);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const add = () => {
    if (!name.trim() || !url.trim()) return;
    setError(null);
    startTransition(async () => {
      const res = await fetch(`${API_BASE}/api/profile/sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), url: url.trim() }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail ?? "Failed to add source");
        return;
      }
      const newSource: CustomSource = await res.json();
      setSources((prev) => [...prev, newSource]);
      setName("");
      setUrl("");
    });
  };

  const remove = (id: string) => {
    startTransition(async () => {
      await fetch(`${API_BASE}/api/profile/sources/${id}`, { method: "DELETE" });
      setSources((prev) => prev.filter((s) => s.id !== id));
    });
  };

  const toggle = (id: string) => {
    startTransition(async () => {
      const res = await fetch(`${API_BASE}/api/profile/sources/${id}/toggle`, { method: "PATCH" });
      const data = await res.json();
      setSources((prev) => prev.map((s) => (s.id === id ? { ...s, enabled: data.enabled } : s)));
    });
  };

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5 flex flex-col gap-5">
      {/* Add form */}
      <div className="flex flex-col gap-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Source name (e.g. SANS ISC)"
            className="w-40 rounded-md border border-zinc-300 px-3 py-2 text-sm placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400"
          />
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
            placeholder="RSS feed URL"
            className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400"
          />
          <button
            onClick={add}
            disabled={isPending || !name.trim() || !url.trim()}
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-40 transition-colors"
          >
            Add
          </button>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>

      {/* Source list */}
      {sources.length === 0 ? (
        <p className="text-sm text-zinc-400">No custom sources added yet.</p>
      ) : (
        <ul className="flex flex-col divide-y divide-zinc-100">
          {sources.map((source) => (
            <li key={source.id} className="flex items-center justify-between gap-3 py-3">
              <div className="flex flex-col min-w-0">
                <span className={`text-sm font-medium ${source.enabled ? "text-zinc-900" : "text-zinc-400"}`}>
                  {source.name}
                </span>
                <span className="text-xs text-zinc-400 truncate">{source.url}</span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => toggle(source.id)}
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${
                    source.enabled
                      ? "bg-green-100 text-green-800 hover:bg-green-200"
                      : "bg-zinc-100 text-zinc-500 hover:bg-zinc-200"
                  }`}
                >
                  {source.enabled ? "Active" : "Paused"}
                </button>
                <button
                  onClick={() => remove(source.id)}
                  className="text-xs text-zinc-400 hover:text-red-600 transition-colors"
                >
                  Remove
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
