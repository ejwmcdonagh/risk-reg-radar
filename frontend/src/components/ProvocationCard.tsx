"use client";

import { useState } from "react";
import type { ProvocationCard } from "@/lib/api";
import CardModal from "./CardModal";

const DOMAIN_SHORT_LABELS: Record<string, string> = {
  identity_credential:  "Identity",
  vulnerability_patch:  "Vuln",
  supply_chain:         "Supply Chain",
  detection_response:   "Detection",
  data_exposure:        "Data",
  ransomware_extortion: "Ransomware",
};

const SCORE_TIERS = [
  { min: 70, label: "Critical", colour: "bg-red-600 text-white" },
  { min: 45, label: "High",     colour: "bg-orange-500 text-white" },
  { min: 0,  label: "Medium",   colour: "bg-zinc-400 text-white" },
];

function getTier(score: number) {
  return SCORE_TIERS.find((t) => score >= t.min) ?? SCORE_TIERS[2];
}

const SCORE_TOOLTIP = `Risk score — how urgent this card is.

How it is calculated:
- +2 per signal in the cluster
- +10 per Critical severity signal, +5 High, +2 Medium
- +3 per signal published in the last 7 days
- +5 per unique source (cross-source = stronger signal)
- +10 if the cluster spans multiple risk domains

Thresholds:
- 70+ Critical (red)
- 45-69 High (orange)
- Below 45 Medium (grey)`;

function ScoreBadge({ score }: { score: number }) {
  const [showTooltip, setShowTooltip] = useState(false);
  const tier = getTier(score);

  return (
    <div className="relative inline-flex items-center gap-1.5">
      <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold tabular-nums ${tier.colour}`}>
        {score}
      </span>
      <span className="text-xs font-medium text-zinc-600">{tier.label}</span>
      <button
        className="text-zinc-400 hover:text-zinc-600 transition-colors leading-none"
        onClick={(e) => { e.stopPropagation(); setShowTooltip((v) => !v); }}
        aria-label="How scores are calculated"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <circle cx="12" cy="12" r="10" />
          <circle cx="12" cy="8" r="0.5" fill="currentColor" stroke="none" />
          <line x1="12" y1="11" x2="12" y2="17" />
        </svg>
      </button>
      {showTooltip && (
        <div
          className="absolute left-0 top-7 z-20 w-72 rounded-lg border border-zinc-200 bg-white p-3 shadow-lg text-xs text-zinc-600 leading-relaxed whitespace-pre-line"
          onClick={(e) => e.stopPropagation()}
        >
          {SCORE_TOOLTIP}
        </div>
      )}
    </div>
  );
}

export default function ProvocationCardComponent({
  card,
  highlighted = false,
  simpleMode = false,
}: {
  card: ProvocationCard;
  highlighted?: boolean;
  simpleMode?: boolean;
}) {
  const [open, setOpen] = useState(false);

  const secondaryDomains = (card.metadata.all_domains ?? [])
    .filter((d) => d !== card.risk_domain);

  return (
    <>
      <article
        role="button"
        tabIndex={0}
        onClick={() => setOpen(true)}
        onKeyDown={(e) => e.key === "Enter" && setOpen(true)}
        className={`cursor-pointer rounded-lg border bg-white p-4 shadow-sm flex flex-col h-72 hover:shadow-md transition-all ${
          highlighted
            ? "border-amber-400 ring-1 ring-amber-300"
            : "border-zinc-200 hover:border-zinc-400"
        }`}
      >
        <div className="flex flex-col gap-2 flex-1 min-h-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-1.5 flex-wrap">
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
          {/* overflow-hidden only on the text block so the score tooltip is never clipped */}
          <div className="flex flex-col gap-2 overflow-hidden">
            <p className="text-sm font-semibold leading-snug text-zinc-900 line-clamp-3">
              {simpleMode
                ? (card.simple_headline ?? card.board_talking_point.split(/(?<=[.!?])\s+/)[0])
                : card.signal_headline}
            </p>
            <p className="text-xs text-zinc-500 line-clamp-1">
              {simpleMode
                ? card.board_talking_point.split(/(?<=[.!?])\s+/).slice(0, 2).join(" ")
                : card.metadata.cluster_summary}
            </p>
          </div>
        </div>
        <div className="flex flex-col gap-1 mt-2">
          {secondaryDomains.length > 0 && (
            <div className="rounded-md bg-zinc-50 border border-zinc-100 px-2 py-1 flex items-center gap-2">
              <span className="text-[10px] font-medium text-zinc-400 uppercase tracking-wide shrink-0">Also in</span>
              <div className="flex gap-1 flex-wrap">
                {secondaryDomains.map((d) => (
                  <span key={d} className="rounded-full border border-zinc-300 px-2 py-0.5 text-xs text-zinc-500">
                    {DOMAIN_SHORT_LABELS[d] ?? d}
                  </span>
                ))}
              </div>
            </div>
          )}
          {card.affected_teams?.length > 0 && (
            <div className="rounded-md bg-zinc-50 border border-zinc-100 px-2 py-1 flex items-center gap-2">
              <span className="text-[10px] font-medium text-zinc-400 uppercase tracking-wide shrink-0">Teams</span>
              <div className="flex gap-1 flex-wrap">
                {[...new Set(card.affected_teams)].map((team) => (
                  <span key={team} className="rounded-full bg-zinc-200 px-2 py-0.5 text-xs text-zinc-600">
                    {team}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </article>

      {open && <CardModal card={card} onClose={() => setOpen(false)} simpleMode={simpleMode} />}
    </>
  );
}
