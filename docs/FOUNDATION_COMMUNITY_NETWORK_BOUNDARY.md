<!--
Purpose: define the Foundation Mode community/network boundary before any community outreach, social post publication, forum post publication, direct message, collaborator recruitment, partnership outreach, mentor request, public feedback request, event participation, contact-list recording, personal-data collection, external-account use, customer access, external publication, or deployment claim.
Governance scope: solo-operator community posture, public-safe local questions, outreach blocking, social/forum blocking, message blocking, collaborator/partner blocking, mentor-request blocking, public-feedback blocking, event blocking, contact-list blocking, personal-data blocking, external-account blocking, customer-access blocking, publication restraint, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_OPERATOR_READINESS_BOUNDARY.md, docs/FOUNDATION_LEARNING_PATH_BOUNDARY.md, docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md, docs/FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md, examples/foundation_community_network_witness.awaiting_evidence.json, scripts/validate_foundation_community_network_boundary.py.
Invariants: no community outreach, no social post publication, no forum post publication, no direct messaging, no collaborator recruitment, no partnership outreach, no mentor request, no public feedback request, no event participation, no contact-list recording, no personal-data collection, no external-account use, no customer access, no external publication, and no deployment claim.
-->

# Foundation Community Network Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** community/network preparation means drafting local questions
> about where outside help, feedback, collaborators, public posts, events, or
> introductions might eventually fit. It does not post publicly, contact
> people, send messages, ask for feedback, recruit collaborators, approach
> partners, request mentors, register for events, store contact lists, collect
> personal data, use external accounts, open customer access, publish
> externally, or deploy anything.

Witness packet: [`../examples/foundation_community_network_witness.awaiting_evidence.json`](../examples/foundation_community_network_witness.awaiting_evidence.json)

Rule: Community/network preparation is a local planning boundary, not outreach, recruiting, public feedback, partnership, or publication.

No community outreach, social post publication, forum post publication, direct
message, collaborator recruitment, partnership outreach, mentor request, public
feedback request, event participation, contact-list recording, personal-data
collection, external-account use, customer access, external publication, or
deployment claim is permitted by this boundary.

## What This Boundary Solves

A solo founder with no team or network needs a way to prepare relationship
questions without creating social pressure, public claims, privacy exposure, or
support duties. Even a harmless-looking forum post, message, collaborator ask,
feedback request, or event registration can create expectations before the
project has stable evidence.

This boundary keeps that work local:

1. Draft community, forum, social, collaborator, partner, mentor, feedback,
   event, and introduction questions locally.
2. Keep every outside person, public post, message, profile, account, and
   personal-data action closed.
3. Promote only one exact external step later, after a separate witness proves
   purpose, wording, risk, privacy, support, and rollback boundaries.

## Current State

```text
community_network_boundary_state=AwaitingEvidence
community_outreach_allowed=false
social_post_publication_allowed=false
forum_post_publication_allowed=false
direct_message_allowed=false
collaborator_recruitment_allowed=false
partnership_outreach_allowed=false
mentor_request_allowed=false
public_feedback_request_allowed=false
event_participation_allowed=false
contact_list_recorded=false
personal_data_collection_allowed=false
external_account_use_allowed=false
public_profile_claimed=false
customer_access_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Public-Safe Preparation Surfaces

| Surface | Public-safe record here | Do not claim here |
| --- | --- | --- |
| Personal network questions | Local relationship-readiness questions only. | Existing network, contact list, or introduction path. |
| Community channel questions | Draft community-fit questions only. | Joined community, outreach, or account readiness. |
| Help-request draft questions | Local help wording questions only. | Sent request, assigned helper, or private detail exposure. |
| Forum post questions | Draft forum-post questions only. | Published forum post, thread, or reply. |
| Social post questions | Draft social-copy questions only. | Published social post, public profile, or engagement. |
| Collaborator boundary questions | Local collaborator-risk questions only. | Collaborator recruitment or commitment. |
| Partnership boundary questions | Local partner-fit questions only. | Partnership outreach or agreement. |
| Mentor request questions | Local mentor-boundary questions only. | Mentor request, assignment, or commitment. |
| Public feedback questions | Draft feedback-scope questions only. | Public feedback request, survey, or beta signal. |
| Event/referral questions | Local event and introduction questions only. | Event registration, attendance, referral, or introduction. |

## Operator Procedure

1. Keep every community/network artifact local and category-level.
2. Do not record names, handles, emails, profile links, private messages,
   communities, event registrations, contact lists, or personal data.
3. Do not post, message, publish, ask for feedback, recruit, partner, request a
   mentor, register for an event, open a public profile, or use external
   accounts.
4. Treat every community/network surface as `AwaitingEvidence` until a later
   witness promotes one bounded external action with wording, privacy, support,
   and rollback evidence.

## Validation

Run:

```powershell
python scripts/validate_foundation_community_network_boundary.py
```

The validator checks that the witness packet:

1. keeps every community/network surface in `AwaitingEvidence`;
2. keeps outreach, posting, messaging, recruiting, partnerships, mentor
   requests, public feedback, events, contact lists, personal-data collection,
   external accounts, customer access, publication, and deployment blocked;
3. rejects URL, email, handle, private path, contact, post, message, community,
   partner, collaborator, mentor, event, account, personal-data, customer,
   secret, or credential shaped values; and
4. rejects community/network promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare operator readiness safely | [Foundation Operator Readiness Boundary](FOUNDATION_OPERATOR_READINESS_BOUNDARY.md) |
| Prepare learning loops safely | [Foundation Learning Path Boundary](FOUNDATION_LEARNING_PATH_BOUNDARY.md) |
| Prepare privacy/data safely | [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) |
| Prepare customer access without opening access | [Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: community outreach blocked, social post publication blocked, forum post publication blocked, direct messaging blocked, collaborator recruitment blocked, partnership outreach blocked, mentor request blocked, public feedback request blocked, event participation blocked, contact-list recording blocked, personal-data collection blocked, external-account use blocked, customer access blocked, external publication blocked, deployment blocked
  Open issues: personal network evidence, community channel evidence, help-request draft evidence, forum post evidence, social post evidence, collaborator boundary evidence, partnership boundary evidence, mentor request evidence, public feedback evidence, event/referral evidence, privacy review, and community/network witness remain AwaitingEvidence
  Next action: run the community/network boundary validator, then keep outside contact and public posting closed until evidence promotes one bounded step
