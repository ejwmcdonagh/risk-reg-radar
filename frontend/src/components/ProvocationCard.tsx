"use client";

import { useState } from "react";
import type { ProvocationCard } from "@/lib/api";
import CardModal from "./CardModal";

function ScoreBadge({ score }: { score: number }) {
  const colour =
    score >= 70 ? "bg-red-600 text-white"
    : score >= 45 ? "bg-orange-500 text-white"
    : "bg-zinc-400 text-white";
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold tabular-nums ${colour}`}>
      {score}
    </span>
  );
}

export default function ProvocationCardComponent({
  card,
  highlighted = false,
}: {
  card: ProvocationCard;
  highlighted?: boolean;
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <article
        role="button"
        tabIndex={0}
        onClick={() => setOpen(true)}
        onKeyDown={(e) => e.key === "Enter" && setOpen(true)}
        className={`cursor-pointer rounded-lg border bg-white p-4 shadow-sm flex flex-col gap-2 hover:shadow-md transition-all ${
          highlighted
            ? "border-amber-400 ring-1 ring-amber-300"
            : "border-zinc-200 hover:border-zinc-400"
        }`}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <ScoreBadge score={card.score} />
            {highlighted && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                your stack
              </span>
            )}
          </div>
          <span className="text-xs text-zinc-400 tabular-nums shrink-0">
            {new Date(card.generated_at).toLocaleDateString("en-GB", {
              day: "numeric", month: "short",
            })}
          </span>
        </div>
        <p className="text-sm font-semibold leading-snug text-zinc-900">
          {card.signal_headline}
        </p>
        <p className="text-xs text-zinc-500 line-clamp-2">
          {card.metadata.cluster_summary}
        </p>
        <p className="text-xs text-zinc-400 mt-1">Click to open</p>
      </article>

      {open && <CardModal card={card} onClose={() => setOpen(false)} />}
    </>
  );
}
