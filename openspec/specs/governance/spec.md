# governance Specification

## Purpose
TBD - created by archiving change update-openspec-governance. Update Purpose after archive.
## Requirements
### Requirement: OpenSpec Capability Inventory
The project MUST maintain a living inventory of capabilities/specs so contributors know what is covered and what needs proposals.

#### Scenario: Document current coverage and gaps
- **GIVEN** this governance change is applied
- **WHEN** assistants check the OpenSpec inventory
- **THEN** they see that `openspec/specs/` currently has no published capability specs
- **AND** they see the explicitly tracked follow-up change IDs `add-documents-file-type-column` (schema/API) and `update-cache-ml-dependency` (dependency policy) that will create the first capability specs

### Requirement: Proposal vs Documentation Decision Tree
Contributors MUST follow a clear decision tree to determine whether a change requires an OpenSpec proposal or is documentation-only.

#### Scenario: Determine need for proposal
- **GIVEN** a contributor plans a change
- **WHEN** the change affects behavior (API contract, schema, caching, metrics, dependency posture, or performance characteristics)
- **THEN** they MUST scaffold an OpenSpec change proposal with spec deltas before implementation
- **AND** ONLY changes that touch documentation or tests without altering behavior may skip proposals
- **AND** urgent fixes that temporarily skip the process MUST backfill a proposal within the same working session

### Requirement: Review & Approval Workflow
Every OpenSpec change MUST document its review path and artifacts before implementation starts.

#### Scenario: Approving a change
- **GIVEN** a proposal exists
- **WHEN** the author completes `proposal.md` and `tasks.md` (and `design.md` if architecture decisions are made)
- **THEN** they MUST run `openspec validate <id> --strict` and share the rendered spec deltas for review
- **AND** an approver (any maintainer on `v2.0-refactor`) MUST confirm that triggers were satisfied, documentation updates are planned, and follow-up change IDs are logged for any new capability gaps
