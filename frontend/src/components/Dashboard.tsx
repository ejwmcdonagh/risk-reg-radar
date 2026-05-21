"use client";

import { useState } from "react";
import type { ProvocationCard, RiskDomain } from "@/lib/api";
import SwimLanes from "./SwimLanes";
import TeamFilter from "./TeamFilter";
import DomainFilter from "./DomainFilter";

type Props = {
  cards: ProvocationCard[];
  domains: RiskDomain[];
  technologies: string[];
};

export default function Dashboard({ cards, domains, technologies }: Props) {
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const [selectedDomain, setSelectedDomain] = useState<string | null>(null);

  let visibleCards = cards;

  if (selectedTeam) {
    visibleCards = visibleCards.filter((c) => c.affected_teams?.includes(selectedTeam));
  }

  // Filter by all_domains (not just primary) so cross-lane cards are included
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
      <SwimLanes cards={visibleCards} domains={domains} technologies={technologies} simpleMode={simpleMode} />
    </div>
  );
}
