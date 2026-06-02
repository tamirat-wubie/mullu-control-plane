<!--
Purpose: define the Foundation Mode market-research and comparison boundary before any customer research, survey, waitlist, market-validation, product-market-fit, pricing, investor, publication, money-movement, or deployment claim.
Governance scope: problem hypothesis, target-user questions, market-category questions, competitor inventory questions, differentiation questions, pricing assumptions, validation-plan questions, public-claim review, risk obligations, evidence-promotion questions, personal-data blocking, customer-access blocking, money-movement blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md, docs/FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md, docs/FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md, examples/foundation_market_research_witness.awaiting_evidence.json, scripts/validate_foundation_market_research_boundary.py.
Invariants: no market-validation claim, no product-market-fit claim, no customer-research execution, no survey publication, no waitlist opening, no outreach, no competitor-superiority claim, no pricing-readiness claim, no public offer, no paid research, no investor material, no personal-data collection, no customer access, no money movement, no external publication, and no deployment claim.
-->

# Foundation Market Research Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** market-research preparation means organizing local questions
> about the problem, possible users, similar platforms, differentiation, and
> pricing assumptions. It does not mean customers have been researched, demand
> has been validated, a waitlist is open, a survey is live, the market is proven,
> or Mullu Govern is ready to sell or deploy.

Witness packet: [`../examples/foundation_market_research_witness.awaiting_evidence.json`](../examples/foundation_market_research_witness.awaiting_evidence.json)

Rule: Market-research preparation is a local planning boundary, not customer research, product-market validation, competitor superiority, pricing readiness, public offer, investor material, or deployment evidence.

No customer research, survey publication, waitlist opening, outreach, market
validation, product-market-fit, market-size, competitor-superiority,
public-benchmark, pricing-readiness, public-offer, paid-research,
investor-material, personal-data collection, customer-access, money-movement,
external-publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

The project needs a way to compare similar platforms and sharpen positioning
without pretending that real users, buyers, investors, or the market have
validated anything.

This boundary separates local research preparation from external evidence:

1. Similar-platform categories can be listed as questions.
2. Differentiation assumptions can be named without superiority claims.
3. Pricing and buyer assumptions can be drafted without public offers.
4. Future validation plans can be prepared without surveys, outreach, waitlists,
   personal data, or customer access.
5. Public wording can remain cautious until later evidence promotes one exact
   claim.

## Current State

```text
market_research_boundary_state=AwaitingEvidence
customer_research_allowed=false
survey_publication_allowed=false
waitlist_allowed=false
outreach_allowed=false
market_validation_claimed=false
product_market_fit_claimed=false
market_category_claimed=false
market_size_claimed=false
competitor_superiority_claimed=false
public_benchmark_claimed=false
pricing_claim_allowed=false
public_offer_allowed=false
paid_research_allowed=false
investor_material_allowed=false
personal_data_collection_allowed=false
customer_access_allowed=false
money_movement_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Research Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Problem hypothesis | Draft the pain, job, and risk questions. | Do not claim the problem is market-proven. |
| Target-user questions | Name possible user groups as hypotheses. | Do not contact people, store personal data, or claim customer evidence. |
| Market category questions | Compare possible categories locally. | Do not claim the category is settled or market-sized. |
| Competitor inventory questions | Draft what a similar-platform inventory should capture. | Do not record private profiles, scrape private data, or claim superiority. |
| Differentiation questions | State what could be different about the governed approach. | Do not claim benchmark victory, moat, legal protection, or market leadership. |
| Pricing assumptions | Draft pricing and packaging questions. | Do not publish prices, offers, checkout, payment links, or paid access. |
| Validation plan | Draft future evidence gates and stop rules. | Do not run surveys, interviews, waitlists, beta access, or outreach. |
| Public-claim review | Keep website and docs wording Foundation-stage. | Do not publish market, customer, investor, or launch claims. |
| Risk obligations | List privacy, support, legal, and cost duties that would arise later. | Do not treat those duties as already satisfied. |
| Evidence promotion | Define what later evidence would be needed to promote one claim. | Do not promote any claim from local notes alone. |

## Operator Procedure

1. Keep market research as local questions unless a later explicit request names
   one external action and its evidence boundary.
2. Do not collect names, emails, survey responses, private links, account IDs,
   prices, customer facts, investor facts, or outreach targets in the witness.
3. Mark all market, customer, pricing, comparison, investor, and deployment
   conclusions as `AwaitingEvidence`.
4. If a later step needs real-world research, create a separate witness for the
   exact action before any outreach, survey, data collection, publication, or
   customer access.
5. Keep the selected product learning lane separate from market validation.

## Validation

Run:

```powershell
python scripts/validate_foundation_market_research_boundary.py
```

The validator checks that the market-research witness:

1. keeps every research surface in `AwaitingEvidence`;
2. keeps customer research, surveys, waitlists, outreach, market validation,
   product-market-fit, category, market-size, competitor-superiority,
   benchmark, pricing, public-offer, paid-research, investor-material,
   personal-data, customer-access, money-movement, publication, and deployment
   claims blocked;
3. rejects URL, email, private path, person, account, survey, pricing,
   competitor, customer, investor, payment, or secret-shaped values; and
4. rejects promotion phrases that turn local questions into market proof.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Keep product scope narrow without restricting the platform | [Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md) |
| Organize research notes safely | [Foundation Research Notebook Boundary](FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md) |
| Keep customer access closed | [Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: customer research blocked, surveys blocked, waitlists blocked, outreach blocked, market validation not claimed, product-market fit not claimed, competitor superiority not claimed, pricing/public-offer claims blocked, investor materials blocked, personal-data collection blocked, customer access blocked, money movement blocked, publication blocked, deployment blocked
  Open issues: problem evidence, target-user evidence, category evidence, competitor evidence, differentiation evidence, pricing evidence, validation evidence, public-claim review evidence, risk-obligation evidence, and evidence-promotion evidence remain AwaitingEvidence
  Next action: run the market-research boundary validator before any future market, customer, pricing, investor, publication, or deployment claim
