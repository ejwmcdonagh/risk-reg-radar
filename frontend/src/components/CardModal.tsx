"use client";

import { useEffect, useState } from "react";
import type { ProvocationCard, EvidenceItem } from "@/lib/api";
import { fetchTeamSummary } from "@/lib/api";

type Props = {
  card: ProvocationCard;
  onClose: () => void;
  simpleMode?: boolean;
};

function ScoreBadge({ score }: { score: number }) {
  const { colour, label } =
    score >= 70 ? { colour: "bg-red-600 text-white",    label: "Critical" }
    : score >= 45 ? { colour: "bg-orange-500 text-white", label: "High" }
    : { colour: "bg-zinc-400 text-white", label: "Medium" };
  return (
    <div className="inline-flex items-center gap-2">
      <span className={`inline-flex items-center rounded px-2.5 py-1 text-sm font-bold tabular-nums ${colour}`}>
        {score}
      </span>
      <span className="text-sm font-medium text-zinc-600">{label}</span>
    </div>
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

const EVIDENCE_PREVIEW = 2;

function EvidenceSection({ items }: { items: EvidenceItem[] }) {
  const [expanded, setExpanded] = useState(false);
  const collapsible = items.length > EVIDENCE_PREVIEW;
  const visible = collapsible && !expanded ? items.slice(0, EVIDENCE_PREVIEW) : items;
  const hidden = items.length - EVIDENCE_PREVIEW;

  return (
    <section>
      <h3 className="text-xs font-semibold uppercase tracking-widest text-zinc-400 mb-3">
        Evidence stack
      </h3>
      <ul className="divide-y divide-zinc-100">
        {visible.map((item, i) => (
          <EvidenceRow key={i} item={item} />
        ))}
      </ul>
      {collapsible && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mt-3 w-full rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs font-medium text-zinc-600 hover:bg-zinc-100 hover:border-zinc-300 transition-colors"
        >
          {expanded ? "Show less" : `Show ${hidden} more source${hidden !== 1 ? "s" : ""}`}
        </button>
      )}
    </section>
  );
}

function buildExecSummary(card: ProvocationCard): string {
  const { signal_count, source_count, severity_max, all_domains } = card.metadata;

  // Severity line - graceful fallback when null
  const severityPhrase = severity_max
    ? `The highest confirmed severity is ${severity_max}.`
    : "Severity is unconfirmed across signals but signal volume and source agreement are elevated.";

  // Signal and source context
  const signalCount = signal_count ?? card.evidence_stack.length;
  const sourceCount = source_count ?? new Set(card.evidence_stack.map((e) => e.source)).size;
  const signalPhrase =
    signalCount === 1
      ? `A single high-importance signal triggered this card from ${sourceCount} source.`
      : sourceCount > 1
      ? `${signalCount} signals from ${sourceCount} independent sources are pointing at the same threat.`
      : `${signalCount} signals from ${sourceCount} source are pointing at the same threat.`;

  // Domain span context
  const domains = all_domains ?? [card.risk_domain];
  const domainPhrase =
    domains.length > 1
      ? `This spans ${domains.length} risk domains, which increases its relevance to board-level discussion.`
      : "";

  return [card.metadata.cluster_summary, severityPhrase, signalPhrase, domainPhrase]
    .filter(Boolean)
    .join(" ");
}

function ExecSummary({ card }: { card: ProvocationCard }) {
  return (
    <section className="rounded-lg bg-zinc-50 border border-zinc-200 px-5 py-4">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-zinc-400 mb-2">
        At a glance
      </h3>
      <p className="text-sm text-zinc-700 leading-7">{buildExecSummary(card)}</p>
    </section>
  );
}

function TeamSummarySection({ cardId, team }: { cardId: string; team: string }) {
  const [summary, setSummary] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchTeamSummary(cardId, team)
      .then((s) => setSummary(s))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [cardId, team]);

  return (
    <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-widest text-zinc-400 mb-2">
        Impact on {team}
      </p>
      {loading && (
        <p className="text-xs text-zinc-400 animate-pulse">Generating...</p>
      )}
      {error && (
        <p className="text-xs text-red-500">Could not generate summary.</p>
      )}
      {summary && (
        <p className="text-sm text-zinc-700 leading-relaxed">{summary}</p>
      )}
    </div>
  );
}

export default function CardModal({ card, onClose, simpleMode = false }: Props) {
  const [activeTeam, setActiveTeam] = useState<string | null>(null);

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
      {/* Modal panel - stop clicks inside from closing */}
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
            {card.affected_teams?.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <p className="text-xs text-zinc-400">
                  Teams affected — click for impact summary
                </p>
                <div className="flex gap-1.5 flex-wrap">
                  {[...new Set(card.affected_teams)].map((team) => (
                    <button
                      key={team}
                      onClick={() => setActiveTeam(activeTeam === team ? null : team)}
                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
                        activeTeam === team
                          ? "bg-zinc-800 text-white"
                          : "border border-zinc-300 text-zinc-600 hover:border-zinc-500 hover:bg-zinc-50"
                      }`}
                    >
                      {activeTeam !== team && (
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="opacity-50">
                          <circle cx="12" cy="12" r="10" />
                          <line x1="12" y1="8" x2="12" y2="12" />
                          <line x1="12" y1="16" x2="12.01" y2="16" />
                        </svg>
                      )}
                      {team}
                    </button>
                  ))}
                </div>
              </div>
            )}
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

          {simpleMode ? (
            <>
              {/* Simple mode: board talking point first, no technical layers */}
              <section className="rounded-lg bg-slate-50 border border-slate-200 px-5 py-5">
                <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-4">
                  What is happening
                </h3>
                <ul className="flex flex-col gap-3">
                  {card.board_talking_point
                    .split(/(?<=[.!?])\s+/)
                    .filter((s) => s.trim().length > 0)
                    .map((sentence, i) => (
                      <li key={i} className="flex gap-3 items-start">
                        <span className="mt-[0.4rem] h-1.5 w-1.5 rounded-full bg-slate-400 shrink-0" />
                        <span className="text-sm text-slate-700 leading-7">{sentence.trim()}</span>
                      </li>
                    ))}
                </ul>
              </section>

              <section>
                <h3 className="text-xs font-semibold uppercase tracking-widest text-zinc-400 mb-3">
                  Question to ask your team
                </h3>
                <blockquote className="rounded-lg border-l-4 border-zinc-300 bg-zinc-50 px-5 py-4">
                  <p className="text-base text-zinc-800 font-medium leading-7 italic">
                    {card.contextual_question}
                  </p>
                </blockquote>
              </section>

              {activeTeam && (
                <TeamSummarySection key={activeTeam} cardId={card.id} team={activeTeam} />
              )}
            </>
          ) : (
            <>
              <ExecSummary card={card} />

              {activeTeam && (
                <TeamSummarySection key={activeTeam} cardId={card.id} team={activeTeam} />
              )}

              <EvidenceSection items={card.evidence_stack} />

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

              <section>
                <h3 className="text-xs font-semibold uppercase tracking-widest text-zinc-400 mb-3">
                  Regulatory exposure
                </h3>
                <p className="text-sm text-zinc-700 leading-7">{card.compliance_gap}</p>
              </section>

              <section>
                <h3 className="text-xs font-semibold uppercase tracking-widest text-zinc-400 mb-3">
                  Board talking point
                </h3>
                <div className="rounded-lg bg-slate-50 border border-slate-200 px-5 py-5">
                  <ul className="flex flex-col gap-3">
                    {card.board_talking_point
                      .split(/(?<=[.!?])\s+/)
                      .filter((s) => s.trim().length > 0)
                      .map((sentence, i) => (
                        <li key={i} className="flex gap-3 items-start">
                          <span className="mt-[0.4rem] h-1.5 w-1.5 rounded-full bg-slate-400 shrink-0" />
                          <span className="text-sm text-slate-700 leading-6">{sentence.trim()}</span>
                        </li>
                      ))}
                  </ul>
                </div>
              </section>
            </>
          )}

        </div>
      </div>
    </div>
  );
}
