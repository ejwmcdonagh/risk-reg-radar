"use client";

import { useState, useTransition } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function TechProfileForm({ initialTechnologies }: { initialTechnologies: string[] }) {
  const [technologies, setTechnologies] = useState<string[]>(initialTechnologies);
  const [input, setInput] = useState("");
  const [saved, setSaved] = useState(false);
  const [isPending, startTransition] = useTransition();

  const add = () => {
    const value = input.trim();
    if (!value || technologies.includes(value)) return;
    setTechnologies((prev) => [...prev, value].sort());
    setInput("");
    setSaved(false);
  };

  const remove = (tech: string) => {
    setTechnologies((prev) => prev.filter((t) => t !== tech));
    setSaved(false);
  };

  const save = () => {
    startTransition(async () => {
      await fetch(`${API_BASE}/api/profile`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ technologies }),
      });
      setSaved(true);
    });
  };

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-5 flex flex-col gap-4">
      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="e.g. Palo Alto, Cisco IOS, WordPress, Microsoft Exchange"
          className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400"
        />
        <button
          onClick={add}
          disabled={!input.trim()}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-40 transition-colors"
        >
          Add
        </button>
      </div>

      {/* Tag list */}
      {technologies.length === 0 ? (
        <p className="text-sm text-zinc-400">No technologies added yet.</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {technologies.map((tech) => (
            <span
              key={tech}
              className="inline-flex items-center gap-1.5 rounded-full bg-zinc-100 px-3 py-1 text-sm text-zinc-800"
            >
              {tech}
              <button
                onClick={() => remove(tech)}
                className="text-zinc-400 hover:text-zinc-700 transition-colors"
                aria-label={`Remove ${tech}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Save */}
      <div className="flex items-center gap-3 pt-1 border-t border-zinc-100">
        <button
          onClick={save}
          disabled={isPending}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-40 transition-colors"
        >
          {isPending ? "Saving..." : "Save"}
        </button>
        {saved && <span className="text-sm text-green-600">Saved</span>}
      </div>
    </div>
  );
}
