<!--
Purpose: define the Foundation Mode accessibility and language boundary before any accessibility-compliance, translation-readiness, localization-readiness, Mfidel-support, Amharic-support, external user-testing, public accessibility statement, customer-access, publication, or deployment claim.
Governance scope: reading-level questions, glossary-access questions, keyboard-navigation questions, screen-reader questions, contrast/layout questions, mobile-responsiveness questions, translation-scope questions, localization-claim questions, Mfidel-atomicity questions, public-accessibility-statement questions, evidence-promotion questions, personal-data blocking, customer-access blocking, publication blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md, docs/FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md, examples/foundation_accessibility_language_witness.awaiting_evidence.json, scripts/validate_foundation_accessibility_language_boundary.py.
Invariants: no accessibility-compliance claim, no WCAG-conformance claim, no screen-reader verification, no keyboard-navigation verification, no mobile-accessibility verification, no contrast-compliance claim, no translation-readiness claim, no localization-readiness claim, no Mfidel-support claim, no Amharic-support claim, no public accessibility statement, no external user testing, no personal-data collection, no customer access, no external publication, and no deployment claim.
-->

# Foundation Accessibility Language Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** accessibility/language preparation means drafting local
> questions so the project can become easier to read, navigate, translate, and
> audit later. It does not mean accessibility is certified, screen readers were
> tested, translations are ready, Amharic/Mfidel support is complete, users were
> tested, or the website is ready to publish.

Witness packet: [`../examples/foundation_accessibility_language_witness.awaiting_evidence.json`](../examples/foundation_accessibility_language_witness.awaiting_evidence.json)

Rule: Accessibility/language preparation is a local planning boundary, not an accessibility-compliance, translation-readiness, localization-readiness, language-support, user-testing, publication, or deployment certificate.

No accessibility compliance, WCAG conformance, screen-reader verification,
keyboard-navigation verification, mobile-accessibility verification,
contrast-compliance, translation-readiness, localization-readiness,
Mfidel-support, Amharic-support, public accessibility statement, external user
testing, personal-data collection, customer access, external publication, or
deployment claim is permitted by this boundary.

## What This Boundary Solves

Foundation Mode needs the website and docs to become easier to use without
pretending that formal accessibility or language support has already been
verified.

This boundary separates preparation from proof:

1. Plain-language and glossary questions can be drafted locally.
2. Keyboard, screen-reader, contrast, and mobile checks can be planned without
   claiming verification.
3. Translation and localization scope can be named without publishing localized
   docs or claiming language readiness.
4. Mfidel atomicity questions can be kept explicit without claiming a complete
   Amharic or Mfidel implementation.
5. Future user-testing and accessibility statements remain blocked until later
   evidence promotes one exact claim.

## Current State

```text
accessibility_language_boundary_state=AwaitingEvidence
accessibility_compliance_claimed=false
wcag_conformance_claimed=false
screen_reader_verified=false
keyboard_navigation_verified=false
mobile_accessibility_verified=false
contrast_compliance_claimed=false
translation_readiness_claimed=false
localization_readiness_claimed=false
mfidel_support_claimed=false
amharic_support_claimed=false
public_accessibility_statement_allowed=false
external_user_testing_allowed=false
personal_data_collection_allowed=false
customer_access_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Preparation Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Reading-level questions | Draft what must be understandable to a non-technical reader. | Do not claim comprehension proof or canonical docs. |
| Glossary-access questions | List confusing words and routing gaps. | Do not claim glossary completeness. |
| Keyboard-navigation questions | Draft tab order, focus, and control questions. | Do not claim keyboard verification. |
| Screen-reader questions | Draft labels, headings, and structure questions. | Do not claim screen-reader testing or compatibility. |
| Contrast/layout questions | Draft contrast, spacing, and overflow questions. | Do not claim contrast or WCAG conformance. |
| Mobile-responsiveness questions | Draft small-screen and touch-target questions. | Do not claim mobile accessibility verification. |
| Translation-scope questions | Draft what would need translation later. | Do not publish translations or claim translation readiness. |
| Localization-claim questions | Draft language-support claim rules. | Do not claim localization readiness or public language support. |
| Mfidel-atomicity questions | Draft rules for preserving Mfidel atomicity in future support. | Do not decompose fidel or claim complete Mfidel/Amharic support. |
| Public-statement questions | Draft what evidence a public accessibility statement would need. | Do not publish statements, invite users, collect data, or deploy. |

## Operator Procedure

1. Keep accessibility/language preparation as local questions unless a later
   signed witness promotes one exact verification step.
2. Do not store user names, test participants, assistive-device details, private
   paths, provider accounts, URLs, emails, translations, or secret values in the
   witness.
3. Keep Mfidel atomicity as a hard rule: do not decompose shape, sound, or
   Unicode codepoints when future Ethiopian-script support is planned.
4. Treat any accessibility, language, translation, localization, Amharic,
   Mfidel, user-testing, publication, customer, or deployment conclusion as
   `AwaitingEvidence`.
5. If a future task needs real accessibility testing or localization, create a
   separate witness for the exact action before external testing, data
   collection, publication, or deployment.

## Validation

Run:

```powershell
python scripts/validate_foundation_accessibility_language_boundary.py
```

The validator checks that the accessibility/language witness:

1. keeps every preparation surface in `AwaitingEvidence`;
2. keeps accessibility compliance, WCAG conformance, screen-reader,
   keyboard-navigation, mobile-accessibility, contrast, translation,
   localization, Mfidel, Amharic, public-statement, user-testing, personal-data,
   customer-access, publication, and deployment claims blocked;
3. rejects URL, email, private path, user-test, assistive-device, translation,
   localization, account, secret, or provider-shaped values; and
4. rejects promotion phrases that turn local questions into compliance or
   language-readiness proof.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare plain-language status safely | [Foundation Plain-Language Status Boundary](FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md) |
| Prepare website posture safely | [Foundation Website Posture Boundary](FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md) |
| Keep customer access closed | [Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: accessibility compliance not claimed, WCAG conformance not claimed, screen-reader verification blocked, keyboard verification blocked, mobile verification blocked, contrast compliance not claimed, translation readiness not claimed, localization readiness not claimed, Mfidel support not claimed, Amharic support not claimed, public accessibility statement blocked, external user testing blocked, personal-data collection blocked, customer access blocked, publication blocked, deployment blocked
  Open issues: reading-level evidence, glossary-access evidence, keyboard-navigation evidence, screen-reader evidence, contrast/layout evidence, mobile-responsiveness evidence, translation-scope evidence, localization-claim evidence, Mfidel-atomicity evidence, public-statement evidence, and evidence-promotion evidence remain AwaitingEvidence
  Next action: run the accessibility/language boundary validator before any future accessibility, language-support, localization, publication, customer, or deployment claim
