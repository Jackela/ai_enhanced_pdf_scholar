## Why
- OpenSpec has been initialized but lacks concrete project context beyond the new project overview. Without a governance change, assistants do not know which specs exist, how to file deltas, or how to coordinate simultaneous refactors.
- The backend/frontend refactor introduced a new API envelope, cache stack, and metrics system; the authoritative behavior must be captured in specs to prevent drift.
- Future proposals (schema migrations, dependency decisions, new features) need a defined review path, owners, and success criteria so the team can gate implementation cleanly.

## What Changes
- Establish an "OpenSpec Governance" change that inventories existing capabilities, decides whether to create new capability specs, and defines approval workflows for future changes.
- Author scope notes describing current backend API contract, cache/metrics subsystems, and documentation expectations so assistants know which spec to modify.
- Produce guidance for how to request proposals, when to require delta specs vs documentation-only updates, and how to archive completed changes.
- Identify any immediate spec gaps (e.g., missing API capability specs, cache specs) and queue follow-up changes.

## Impact
- Provides a single source of truth for how OpenSpec is used in this repo, enabling faster proposal authoring and review.
- Reduces risk of assistants implementing changes without approved proposals by clarifying triggers and approval checklists.
- Surfaces missing capabilities early, so domain knowledge (API envelope, caching, RAG flows) can be spec'd before further refactors.
