import { fetchProfile, fetchSources } from "@/lib/api";
import TechProfileForm from "@/components/TechProfileForm";
import CustomSourcesForm from "@/components/CustomSourcesForm";
import Link from "next/link";

export default async function SettingsPage() {
  const [profile, sources] = await Promise.all([fetchProfile(), fetchSources()]);

  return (
    <div className="min-h-screen bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white px-6 py-4">
        <div className="flex items-baseline justify-between">
          <div>
            <h1 className="text-lg font-semibold text-zinc-900">Settings</h1>
            <p className="text-xs text-zinc-400 mt-0.5">Org profile and signal sources</p>
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
            <h2 className="text-base font-semibold text-zinc-900">Technology stack</h2>
            <p className="text-sm text-zinc-500 mt-1">
              Add the vendors and products your organisation runs. Cards that mention these
              technologies will be highlighted and sorted to the top of each lane.
            </p>
          </div>
          <TechProfileForm initialTechnologies={profile.technologies} />
        </section>

        <div className="border-t border-zinc-200" />

        {/* Custom signal sources */}
        <section>
          <div className="mb-4">
            <h2 className="text-base font-semibold text-zinc-900">Custom signal sources</h2>
            <p className="text-sm text-zinc-500 mt-1">
              Add RSS or Atom feeds beyond the built-in sources. Signals from these feeds
              are ingested daily and included in clustering and card generation.
            </p>
          </div>
          <CustomSourcesForm initialSources={sources} />
        </section>

      </main>
    </div>
  );
}
