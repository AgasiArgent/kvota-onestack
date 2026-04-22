/**
 * _stale-check-runner.ts — thin CLI wrapper around writeManifest() used only
 * by `test_ci_stale_check.sh`. Not part of the public journey script surface.
 *
 * Usage:
 *   npx tsx _stale-check-runner.ts \
 *     <appRoot> <specsRoot> <accessControlPath> <repoRoot> <outputPath>
 */
import { writeManifest } from "../build-manifest";

async function main(): Promise<void> {
  const [appRoot, specsRoot, accessControlPath, repoRoot, outputPath] =
    process.argv.slice(2);
  if (!appRoot || !specsRoot || !accessControlPath || !repoRoot || !outputPath) {
    console.error(
      "Usage: _stale-check-runner.ts <appRoot> <specsRoot> <accessControlPath> <repoRoot> <outputPath>",
    );
    process.exit(2);
  }
  await writeManifest({
    appRoot,
    specsRoot,
    accessControlPath,
    repoRoot,
    outputPath,
    commit: "0000000000000000000000000000000000000000",
    generatedAt: "2026-04-22T00:00:00.000Z",
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
