import { fetchCards, fetchProfile, DOMAINS, type ProvocationCard } from "@/lib/api";
import SwimLanes from "@/components/SwimLanes";
import Link from "next/link";

export default async function Home() {
  let cards: ProvocationCard[] = [];
  let technologies: string[] = [];
  let error: string | null = null;

  try {
    [cards, { technologies }] = await Promise.all([fetchCards(), fetchProfile()]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load cards";
  }

  const totalCards = cards.length;
  const activeCards = cards.filter((c) => c.status === "active").length;

  return (
    <div className="flex flex-col h-full min-h-screen bg-zinc-50">
      {/* Header */}
      <header className="border-b border-zinc-200 bg-white px-6 py-4 shrink-0">
        <div className="flex items-baseline justify-between">
          <div>
            <h1 className="text-lg font-semibold text-zinc-900">Regulatory Radar</h1>
            <p className="text-xs text-zinc-400 mt-0.5">
              Multi-signal threat intelligence for CISOs
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs text-zinc-500">
            <span>{activeCards} active {activeCards === 1 ? "card" : "cards"}</span>
            <span>{DOMAINS.length} domains</span>
            <Link
              href="/settings"
              className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:border-zinc-400 hover:bg-zinc-50 transition-colors"
            >
              Customize your feed
            </Link>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 overflow-hidden px-6 py-4">
        {error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Could not connect to the API: {error}. Make sure the backend is running on{" "}
            <code className="font-mono text-xs">http://localhost:8000</code>.
          </div>
        ) : totalCards === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 gap-2">
            <p className="text-sm text-zinc-500">No provocation cards yet.</p>
            <p className="text-xs text-zinc-400">
              Run{" "}
              <code className="font-mono bg-zinc-100 px-1 rounded">
                POST /api/cards/run
              </code>{" "}
              to generate cards from existing clusters.
            </p>
          </div>
        ) : (
          <SwimLanes cards={cards} domains={DOMAINS} technologies={technologies} />
        )}
      </main>
    </div>
  );
}
