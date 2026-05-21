"use client";

import { useEffect } from "react";
import type { ProvocationCard, EvidenceItem } from "@/lib/api";

type Props = {
  card: ProvocationCard;
  onClose: () => void;
};

function ScoreBadge({ score }: { score: number }) {
  const colour =
    score >= 70 ? "bg-red-600 text-white"
    : score >= 45 ? "bg-orange-500 text-white"
    : "bg-zinc-400 text-white";
  return (
    <span className={`inline-flex items-center rounded px-2.5 py-1 text-sm font-bold tabular-nums ${colour}`}>
      {score}
    </span>
  );
}

function EvidenceRow({ item }: { item: EvidenceItem }) {
  return (
    <li className="flex flex-col gap-1 py-3 border-b border-zinc-100 last:border-0">
      <div className="flex items-center gap-2">
        <span className="shrink-0 rounded bg-zinc-100 px-1.5 py-0.5 text-xs font-semibold text-zinc-600">
          {item.source}
        </span>
        {item.url && item.url !== "<UNKNOWN>" ? (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:underline leading-snug"
          >
            {item.title}
          </a>
        ) : (
          <span className="text-sm text-zinc-800 leading-snug">{item.title}</span>
        )}
      </div>
      <p className="text-sm text-zinc-500 leading-relaxed pl-0">{item.point}</p>
    </li>
  );
}

export default function CardModal({ card, onClose }: Props) {
  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    // Prevent body scroll while modal is open
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      {/* Modal panel — stop clicks inside from closing */}
      <div
        className="relative flex flex-col w-full max-w-3xl max-h-[92vh] rounded-xl bg-white shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Sticky header */}
        <div className="flex items-start justify-between gap-4 px-6 py-5 border-b border-zinc-200 shrink-0">
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <ScoreBadge score={card.score} />
              <span className="text-xs text-zinc-400 capitalize">
                {card.risk_domain.replace(/_/g, " ")}
              </span>
              <span className="text-xs text-zinc-300">·</span>
              <span className="text-xs text-zinc-400">
                {new Date(card.generated_at).toLocaleDateString("en-GB", {
                  day: "numeric", month: "short", year: "numeric",
                })}
              </span>
            </div>
            <h2 className="text-lg font-semibold text-zinc-900 leading-snug">
              {card.signal_headline}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded-md p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 transition-colors"
            aria-label="Close"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto flex-1 px-6 py-6 flex flex-col gap-8">

          {/* Layer 2: Evidence */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-widest text-zinc-400 mb-3">
              Evidence stack
            </h3>
            <ul className="divide-y divide-zinc-100">
              {card.evidence_stack.map((item, i) => (
                <EvidenceRow key={i} item={item} />
              ))}
            </ul>
          </section>

          {/* Layer 3: Compliance gap */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-widest text-zinc-400 mb-3">
              Compliance gap
            </h3>
            <p className="text-sm text-zinc-700 leading-7">{card.compliance_gap}</p>
          </section>

          {/* Layer 4: Contextual question */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-widest text-zinc-400 mb-3">
              Question for your team
            </h3>
            <blockquote className="rounded-lg border-l-4 border-zinc-300 bg-zinc-50 px-5 py-4">
              <p className="text-base text-zinc-800 font-medium leading-7 italic">
                {card.contextual_question}
              </p>
            </blockquote>
          </section>

          {/* Layer 5: Board talking point */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-widest text-zinc-400 mb-3">
              Board talking point
            </h3>
            <div className="rounded-lg bg-zinc-900 px-5 py-5">
              <p className="text-sm text-zinc-100 leading-7">{card.board_talking_point}</p>
            </div>
          </section>

        </div>
      </div>
    </div>
  );
}
