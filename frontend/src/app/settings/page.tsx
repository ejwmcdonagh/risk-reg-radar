import { fetchProfile, fetchSources, fetchBuiltinSources } from "@/lib/api";
import TechProfileForm from "@/components/TechProfileForm";
import BlockedTechForm from "@/components/BlockedTechForm";
import BuiltinSourcesForm from "@/components/BuiltinSourcesForm";
import CustomSourcesForm from "@/components/CustomSourcesForm";
import Link from "next/link";

export default async function SettingsPage() {
  const [profile, sources, builtinSources] = await Promise.all([
    fetchProfile(),
    fetchSources(),
    fetchBuiltinSources(),
  ]);

  return (
    <div className="min-h-screen bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white px-6 py-4">
        <div className="flex items-baseline justify-between">
          <div>
            <h1 className="text-lg font-semibold text-zinc-900">Pulse</h1>
            <p className="text-xs text-zinc-400 mt-0.5">Control your sources and highlight what matters to you</p>
          </div>
          <Link href="/" className="text-xs text-zinc-400 hover:text-zinc-700 transition-colors">
            Back to dashboard
          </Link>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-8 flex flex-col gap-10">

        {/* Technology stack */}
        <section>
          <div className="mb-4">
            <h2 className="text-base font-semibold text-zinc-900">Your technology stack</h2>
            <p className="text-sm text-zinc-500 mt-1">
              Add the vendors and products your organisation runs. Cards that mention these
              technologies will be highlighted and sorted to the top of each lane.
            </p>
          </div>
          <TechProfileForm initialTechnologies={profile.technologies} />
        </section>

        <div className="border-t border-zinc-200" />

        {/* Blocked technologies */}
        <section>
          <div className="mb-4">
            <h2 className="text-base font-semibold text-zinc-900">Blocked technologies</h2>
            <p className="text-sm text-zinc-500 mt-1">
              Add technologies your organisation does not use. Cards that mention these will be
              hidden from the board entirely.
            </p>
          </div>
          <BlockedTechForm
            initialTechnologies={profile.technologies}
            initialBlocked={profile.blocked_technologies ?? []}
          />
        </section>

        <div className="border-t border-zinc-200" />

        {/* Built-in sources */}
        <section>
          <div className="mb-4">
            <h2 className="text-base font-semibold text-zinc-900">Signal sources</h2>
            <p className="text-sm text-zinc-500 mt-1">
              These sources are built in and run automatically every day. Pause any source
              you do not want to include. Changes take effect on the next scheduled run.
            </p>
          </div>
          <BuiltinSourcesForm initialSources={builtinSources} />
        </section>

        <div className="border-t border-zinc-200" />

        {/* Custom sources */}
        <section>
          <div className="mb-4">
            <h2 className="text-base font-semibold text-zinc-900">Add your own sources</h2>
            <p className="text-sm text-zinc-500 mt-1">
              Add any RSS or Atom feed. Signals from these feeds are ingested daily
              and included in clustering and card generation alongside the built-in sources.
            </p>
          </div>
          <CustomSourcesForm initialSources={sources} />
        </section>

      </main>
    </div>
  );
}
