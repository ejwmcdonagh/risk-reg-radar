"use client";

import { useState } from "react";
import type { ProvocationCard, RiskDomain } from "@/lib/api";
import SwimLanes from "./SwimLanes";
import TeamFilter from "./TeamFilter";

type Props = {
  cards: ProvocationCard[];
  domains: RiskDomain[];
  technologies: string[];
};

export default function Dashboard({ cards, domains, technologies }: Props) {
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);

  const visibleCards = selectedTeam
    ? cards.filter((c) => c.affected_teams?.includes(selectedTeam))
    : cards;

  return (
    <div className="flex flex-col gap-3 h-full">
      <TeamFilter selected={selectedTeam} onChange={setSelectedTeam} />
      <SwimLanes cards={visibleCards} domains={domains} technologies={technologies} />
    </div>
  );
}
