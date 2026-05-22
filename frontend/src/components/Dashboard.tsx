"use client";

import { useState } from "react";
import type { ProvocationCard, RiskDomain } from "@/lib/api";
import { fetchCards } from "@/lib/api";
import SwimLanes from "./SwimLanes";
import TeamFilter from "./TeamFilter";
import DomainFilter from "./DomainFilter";

type Props = {
  cards: ProvocationCard[];
  domains: RiskDomain[];
  technologies: string[];
  blockedTechnologies: string[];
};

const PAGE_SIZE = 50;

export default function Dashboard({ cards: initialCards, domains, technologies, blockedTechnologies }: Props) {
  const [cards, setCards] = useState(initialCards);
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);
  // offset tracks how many cards have been fetched so far for load more
  const [offset, setOffset] = useState(initialCards.length);
  // only show the button when the last fetch returned a full page
  const [hasMore, setHasMore] = useState(initialCards.length === PAGE_SIZE);
  const [loadingMore, setLoadingMore] = useState(false);

  function handleDismiss(id: string) {
    setCards((prev) => prev.filter((c) => c.id !== id));
  }

  async function handleLoadMore() {
    setLoadingMore(true);
    try {
      const more = await fetchCards(PAGE_SIZE, offset);
      setCards((prev) => [...prev, ...more]);
      setOffset((o) => o + more.length);
      setHasMore(more.length === PAGE_SIZE);
    } finally {
      setLoadingMore(false);
    }
  }

  // Same haystack logic as tech-stack highlighting in SwimLanes - check headline,
  // cluster summary, and evidence titles/points for any blocked technology mention.
  const isBlocked = (card: ProvocationCard) => {
    if (blockedTechnologies.length === 0) return false;
    const haystack = [
      card.signal_headline,
      card.metadata.cluster_summary,
      ...card.evidence_stack.map((e) => `${e.title} ${e.point}`),
    ].join(" ").toLowerCase();
    return blockedTechnologies.some((t) => haystack.includes(t.toLowerCase()));
  };

  let visibleCards = cards.filter((c) => !isBlocked(c));

  if (selectedTeam) {
    visibleCards = visibleCards.filter((c) => c.affected_teams?.includes(selectedTeam));
  }

  // Check all_domains not just primary risk_domain - a supply chain card can also
  // appear in vulnerability_patch, and the domain filter should catch both.
  if (selectedDomain) {
    visibleCards = visibleCards.filter((c) =>
      (c.metadata.all_domains ?? [c.risk_domain]).includes(selectedDomain)
    );
  }

  const [simpleMode, setSimpleMode] = useState(false);

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <DomainFilter selected={selectedDomain} onChange={setSelectedDomain} />
        <button
          onClick={() => setSimpleMode((v) => !v)}
          className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium border transition-colors ${
            simpleMode
              ? "bg-zinc-800 text-white border-zinc-800"
              : "border-zinc-300 text-zinc-600 hover:border-zinc-400 hover:bg-zinc-50"
          }`}
        >
          {simpleMode ? "Simple mode on" : "Simple mode"}
        </button>
      </div>
      <TeamFilter selected={selectedTeam} onChange={setSelectedTeam} />
      <SwimLanes cards={visibleCards} domains={domains} technologies={technologies} simpleMode={simpleMode} onDismiss={handleDismiss} />
      {hasMore && (
        <div className="flex justify-center py-4">
          <button
            onClick={handleLoadMore}
            disabled={loadingMore}
            className="rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-600 hover:border-zinc-400 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
          >
            {loadingMore ? "Loading..." : "Load more"}
          </button>
        </div>
      )}
    </div>
  );
}
