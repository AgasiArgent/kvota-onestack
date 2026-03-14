export interface ChangelogEntry {
  slug: string;
  title: string;
  date: string;
  category: "feature" | "fix" | "update" | "improvement";
  version: string | null;
  body_html: string;
}
