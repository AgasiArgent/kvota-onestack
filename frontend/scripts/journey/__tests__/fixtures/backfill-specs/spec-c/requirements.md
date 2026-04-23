---
related_routes:
  - /quotes/[id]
---

# Spec C — Already has frontmatter

The user opens `/quotes/[id]` — this should NOT generate a patch entry
because `related_routes:` is already present.
