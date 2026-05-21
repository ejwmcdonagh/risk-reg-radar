"use client";

import { TEAM_LABELS } from "@/lib/api";

type Props = {
  selected: string | null;
  onChange: (team: string | null) => void;
};

export default function TeamFilter({ selected, onChange }: Props) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-xs text-zinc-400 shrink-0">Filter by team</span>
      <div className="flex gap-1.5 flex-wrap">
        <button
          onClick={() => onChange(null)}
          className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
            selected === null
              ? "bg-zinc-800 text-white"
              : "border border-zinc-300 text-zinc-600 hover:border-zinc-400 hover:bg-zinc-50"
          }`}
        >
          All
        </button>
        {TEAM_LABELS.map((team) => (
          <button
            key={team}
            onClick={() => onChange(selected === team ? null : team)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              selected === team
                ? "bg-zinc-800 text-white"
                : "border border-zinc-300 text-zinc-600 hover:border-zinc-400 hover:bg-zinc-50"
            }`}
          >
            {team}
          </button>
        ))}
      </div>
    </div>
  );
}
