# 26 Knowledge Ingestion

## Purpose

Extract procedures, methods, best practices, and failure patterns from
operational artifacts and turn them into reusable knowledge.  The ingestion
pipeline converts raw operational evidence into structured, verifiable
knowledge records that can later be promoted into procedural and semantic
memory for use by the skill system, goal reasoner, and workflow runtime.

## Knowledge Sources

| Source type       | Description                                              |
|-------------------|----------------------------------------------------------|
| document          | Uploaded or referenced documents (runbooks, guides, SOPs)|
| runbook           | Existing runbook definitions already in the platform     |
| skill_run         | Completed skill execution records with outcomes          |
| workflow_run      | Completed workflow execution records with stage results  |
| incident          | Incident reports and post-mortems                        |
| email_thread      | Threaded email conversations containing operational info |
| code_review       | Code review comments and discussions                     |
| operator_note     | Free-form notes entered by human operators               |

Every knowledge artifact MUST carry an explicit `source_id` linking back to
the originating artifact.  Provenance is non-negotiable.

## Owned Artifacts

The knowledge ingestion subsystem defines the following contract types:

- **KnowledgeSource** -- identity and metadata for an ingestion source.
- **ProcedureCandidate** -- a procedure extracted from a source, with steps,
  preconditions, postconditions, and explicitly marked missing parts.
- **ProcedureStep** -- one atomic step within a procedure candidate.
- **MethodPattern** -- a reusable method pattern extracted across one or more
  sources.
- **BestPracticeRecord** -- a best practice with conditions and
  recommendations.
- **FailurePattern** -- a failure mode with trigger conditions and
  recommended response.
- **LessonRecord** -- a single lesson learned from a source with context,
  action, outcome, and lesson text.
- **KnowledgeVerificationResult** -- the outcome of verifying a piece of
  extracted knowledge.
- **KnowledgePromotionDecision** -- the decision to promote knowledge from
  one lifecycle stage to another.
- **ConfidenceLevel** -- a typed confidence value with reason and assessment
  timestamp.

## Knowledge Lifecycle

All extracted knowledge follows the platform-standard six-stage lifecycle:

```
candidate --> provisional --> verified --> trusted --> deprecated --> blocked
```

| Stage        | Meaning                                                     |
|--------------|-------------------------------------------------------------|
| candidate    | Freshly extracted, not yet reviewed                         |
| provisional  | Initial review passed, awaiting deeper verification         |
| verified     | Verification completed with positive result                 |
| trusted      | Approved for use in procedural/semantic memory              |
| deprecated   | Superseded or no longer applicable                          |
| blocked      | Explicitly excluded from use; MUST NOT enter memory         |

Lifecycle values use the `KnowledgeLifecycle` StrEnum and match the
`SkillLifecycle` convention used elsewhere in the platform.

## Knowledge Scope

Each knowledge artifact carries a scope that determines its visibility:

- **local** -- visible only within the originating context.
- **team** -- visible to the team that owns the source.
- **organization** -- visible across the entire organization.

## Extraction Rules

1. **Never fabricate missing steps.**  If a source does not contain a
   complete procedure, the missing parts MUST be recorded in the
   `missing_parts` tuple of the `ProcedureCandidate`.
2. **Mark incomplete parts explicitly.**  Every gap, ambiguity, or
   assumption MUST be surfaced as a missing-part entry or as reduced
   confidence.
3. **Lower confidence on ambiguity.**  When source material is ambiguous,
   the `ConfidenceLevel.value` MUST be reduced and the reason field MUST
   explain the ambiguity.
4. **Preserve source provenance.**  Every extracted artifact MUST reference
   the `source_id` of the `KnowledgeSource` it was derived from.
5. **No silent inference.**  Extracted steps and patterns MUST reflect what
   the source actually says, not what the extractor infers.

## Promotion Rules

1. Only knowledge with lifecycle `verified` or higher may be promoted to
   `trusted`.
2. Only `trusted` knowledge enters procedural or semantic memory.
3. Promotion requires a `KnowledgePromotionDecision` with explicit reason
   and decider identity.
4. Promotion from `candidate` directly to `trusted` is prohibited; the
   `provisional` and `verified` stages MUST NOT be skipped.
5. The `KnowledgeVerificationResult` MUST exist and show `verified=True`
   before promotion to `trusted` is allowed.

## Prohibitions

- **No unverified knowledge treated as trusted.**  Knowledge at `candidate`
  or `provisional` lifecycle MUST NOT be used as if it were trusted.
- **No extraction without source provenance.**  Every extracted artifact
  MUST have a valid `source_id` pointing to a `KnowledgeSource`.
- **No silent confidence inflation.**  Confidence values MUST NOT be
  increased without an explicit verification step and a recorded reason.
- **No blocked knowledge re-promotion.**  Knowledge at `blocked` lifecycle
  MUST NOT be promoted back to any active stage without a new extraction
  from the original source.
- **No fabrication.**  Extracted procedures, patterns, and practices MUST
  reflect the source material faithfully.
