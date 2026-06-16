# Trusted Capture Evidence Packet Contract

Purpose: define a digest-only trusted capture evidence packet before any browser, screen, video, audio, sensor, or reality-capture authority is considered.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `docs/FOUNDATION_MODE.md`, `docs/82_cross_repo_opportunity_map.md`, `schemas/trusted_capture_evidence_packet.schema.json`, `schemas/capture_policy_decision_ledger.schema.json`, `schemas/evidence_classification_manifest.schema.json`, `schemas/browser_observation_receipt.schema.json`, `schemas/universal_action_orchestration.schema.json`, `schemas/life_meaning_judgment.schema.json`.
Invariants: trusted capture evidence stores no raw surface, raw media, raw audio, raw sensor payload, raw source body, or raw secret; trusted capture evidence grants no live capture, media recording, screen recording, camera, microphone, sensor, file-write, connector, external-write, publication, terminal-closure, or success authority.

## Boundary

`TrustedCaptureEvidencePacket` is an evidence packet, not a capture adapter.

It may bind:

1. Hashed source-surface evidence.
2. Surface, frame, media, transcript, sensor, and artifact-manifest digest refs.
3. Capture policy, evidence classification, browser observation, UAO, and LifeMeaningJudgment refs.
4. Consent scope and tenant scope.
5. Privacy guards and authority-denial flags.

It must not bind:

1. Raw browser, screen, video, audio, or sensor payloads.
2. Raw source bodies or raw secret values.
3. Live capture, recording, camera, microphone, or sensor authority.
4. File writes, connector calls, or external writes.
5. Publication, terminal closure, or success claims.

## Foundation Example

The Foundation Mode example is:

```text
examples/trusted_capture_evidence_packet.foundation.json
```

The validator is:

```powershell
python scripts\validate_trusted_capture_evidence_packet.py
```

Expected result:

```text
[PASS] trusted_capture_evidence_packet
```

## Authority Denials

The Foundation example requires these fields to remain `false`:

| Field | Denial |
| --- | --- |
| `live_capture_performed` | no live capture authority |
| `media_recording_performed` | no media recording authority |
| `screen_recording_performed` | no screen recording authority |
| `microphone_capture_performed` | no microphone capture authority |
| `camera_capture_performed` | no camera capture authority |
| `sensor_read_performed` | no sensor read authority |
| `file_write_performed` | no file write authority |
| `connector_call_performed` | no connector call authority |
| `external_write_performed` | no external write authority |
| `raw_media_stored` | no raw media retention |
| `raw_source_body_stored` | no raw source-body retention |
| `raw_secret_value_stored` | no raw secret retention |
| `publication_allowed` | no external publication |
| `terminal_closure_allowed` | no terminal closure |
| `success_claim_allowed` | no success claim |

## Privacy Guards

The Foundation example requires raw storage fields to remain `false` and review guards to remain `true`:

| Field | Required value |
| --- | --- |
| `raw_surface_stored` | `false` |
| `raw_media_stored` | `false` |
| `raw_audio_stored` | `false` |
| `raw_sensor_payload_stored` | `false` |
| `raw_secret_value_stored` | `false` |
| `private_payload_redacted` | `true` |
| `operator_review_required` | `true` |

## Verification

Run:

```powershell
python scripts\validate_trusted_capture_evidence_packet.py
python -m pytest tests\test_validate_trusted_capture_evidence_packet.py -q
python scripts\validate_protocol_manifest.py
python scripts\proof_coverage_matrix.py --check
python scripts\validate_sdlc_artifact.py
python scripts\validate_sdlc_security_review.py --review examples\sdlc\security_review_trusted_capture_evidence_packet_20260616.json --strict
```

STATUS:
  Completeness: 100%
  Invariants verified: digest-only capture evidence, no raw surface, no raw media, no raw audio, no raw sensor payload, no raw source body, no raw secret, no live capture authority, no connector authority, no publication, no terminal closure
  Open issues: none
  Next action: use TrustedCaptureEvidencePacket before any future capture-evidence promotion gate
