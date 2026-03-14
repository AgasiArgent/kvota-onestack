import { fetchChangelogEntries } from "@/entities/changelog/queries";
import { ChangelogTimeline } from "@/features/changelog";

export default async function ChangelogPage() {
  const entries = await fetchChangelogEntries();

  return (
    <div className="max-w-[720px]">
      <h1 className="text-2xl font-bold mb-6">Обновления</h1>
      <ChangelogTimeline entries={entries} />
    </div>
  );
}
