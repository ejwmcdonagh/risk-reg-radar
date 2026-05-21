"use client";

import type { ProvocationCard, RiskDomain } from "@/lib/api";
import ProvocationCardComponent from "./ProvocationCard";

type Props = {
  cards: ProvocationCard[];
  domains: RiskDomain[];
  technologies: string[];
};

function cardMatchesTech(card: ProvocationCard, technologies: string[]): boolean {
  if (technologies.length === 0) return false;
  const haystack = [
    card.signal_headline,
    card.metadata.cluster_summary,
    ...card.evidence_stack.map((e) => `${e.title} ${e.point}`),
  ]
    .join(" ")
    .toLowerCase();
  return technologies.some((t) => haystack.includes(t.toLowerCase()));
}

export default function SwimLanes({ cards, domains, technologies }: Props) {
  const byDomain = (domainId: string) => {
    const domainCards = cards.filter((c) => c.risk_domain === domainId);
    // Tech-matched cards float to the top within their score tier
    const matched = domainCards.filter((c) => cardMatchesTech(c, technologies)).sort((a, b) => b.score - a.score);
    const unmatched = domainCards.filter((c) => !cardMatchesTech(c, technologies)).sort((a, b) => b.score - a.score);
    return [...matched, ...unmatched];
  };

  const hasTech = technologies.length > 0;

  return (
    <div className="flex gap-4 overflow-x-auto pb-4 min-h-0">
      {domains.map((domain) => {
        const domainCards = byDomain(domain.id);
        const matchCount = hasTech ? domainCards.filter((c) => cardMatchesTech(c, technologies)).length : 0;

        return (
          <div key={domain.id} className="flex flex-col gap-3 min-w-[280px] w-[280px] shrink-0">
            <div className="sticky top-0 z-10 bg-zinc-50 pb-2 pt-1">
              <h2 className="text-sm font-semibold text-zinc-800">{domain.label}</h2>
              <p className="text-xs text-zinc-400">{domain.description}</p>
              <div className="mt-1 flex items-center gap-2">
                <span className="text-xs text-zinc-400">
                  {domainCards.length} {domainCards.length === 1 ? "card" : "cards"}
                </span>
                {matchCount > 0 && (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                    {matchCount} matched
                  </span>
                )}
              </div>
            </div>

            {domainCards.length === 0 ? (
              <div className="rounded-lg border border-dashed border-zinc-200 p-4 text-center">
                <p className="text-xs text-zinc-400">No active cards</p>
              </div>
            ) : (
              domainCards.map((card) => (
                <ProvocationCardComponent
                  key={card.id}
                  card={card}
                  highlighted={hasTech && cardMatchesTech(card, technologies)}
                />
              ))
            )}
          </div>
        );
      })}
    </div>
  );
}
