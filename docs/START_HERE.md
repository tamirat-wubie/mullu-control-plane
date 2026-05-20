# Start Here

**This is the front door to all Mullu documentation.** You do not need to know
anything about this project to use this page. Find the row that sounds like you,
read the one-line description, and click the link.

Every link below eventually connects to every other document, so you can never
get lost: when you hit a word you don't understand, look it up in the
[Glossary](GLOSSARY.md) — it explains the word in one plain sentence and links
to the deep document if you want more.

---

## 1. Pick the sentence that sounds most like you

| If you would say... | Go to | Time |
| --- | --- | --- |
| "I have no idea what this thing even is. Explain it like I'm not technical." | [Plain-English Overview](explain/PLAIN_ENGLISH.md) | 5 min read |
| "I want to actually run it and see it do something, step by step, holding my hand." | [Tutorial 1: Your First Run](tutorials/01_first_governed_task.md) | 20 min, hands-on |
| "Show me it actually govern something real (refuse an overspend, prove a payment)." | [Tutorial 2: Watch Mullu Govern Real Money](tutorials/02_a_real_governed_task.md) | 25 min, hands-on |
| "I'm a developer. Just get me running fast." | [Quickstart](QUICKSTART.md) | 5 min, hands-on |
| "I keep seeing weird words (governed swarm, witness, 8-guard chain). What do they mean?" | [Glossary](GLOSSARY.md) | look-up |
| "I need to do one specific thing (deploy, set a budget, add a channel)." | [How-To Guides](how-to/) | task-based |
| "I want the full technical truth about how a part works." | [Reference & Architecture](#5-reference--deep-architecture) | deep |
| "I'm deciding whether to use/fund this. Give me the shape, not the code." | [Plain-English Overview](explain/PLAIN_ENGLISH.md) → then [System Boundary Map](../../docs/mullu-system-boundary-map.md) | 15 min |
| "I'm going to contribute code." | [Contributor path](#6-if-you-are-going-to-change-the-code) | deep |

If none fit, start at the [Plain-English Overview](explain/PLAIN_ENGLISH.md). It
assumes zero knowledge and points you everywhere else.

---

## 2. The four kinds of documentation (so you know what you're reading)

This project follows a standard documentation model. Every page is exactly **one
of these four types**, and each type answers a different question. Knowing the
type tells you what to expect:

| Type | It answers | When to read it | Where |
| --- | --- | --- | --- |
| **Explanation** | "What is this and *why*?" | When you're confused about the big picture | [explain/](explain/) |
| **Tutorial** | "Can you teach me by doing?" | When you've never used it and want a guided first run | [tutorials/](tutorials/) |
| **How-to** | "How do I accomplish task X?" | When you know the basics and have a specific goal | [how-to/](how-to/) |
| **Reference** | "What exactly does X do / what are the rules?" | When you need precise, complete facts | [reference/](reference/) and the numbered `NN_*.md` docs |

A common mistake is reading a Reference doc when you actually wanted an
Explanation, then concluding "this is too complicated." It isn't — you were just
in the wrong room. Use the table above to pick the right room.

---

## 3. The "I'm brand new" path (do these in order)

1. **[Plain-English Overview](explain/PLAIN_ENGLISH.md)** — what Mullu is, in
   everyday language, with an analogy. No setup, just reading.
2. **[Tutorial 1: Your First Run](tutorials/01_first_governed_task.md)**
   — you install it and run it safely, every command explained, every term
   linked.
3. **[Tutorial 2: Watch Mullu Govern Real Money](tutorials/02_a_real_governed_task.md)**
   — you watch it *refuse* an over-limit payment and *prove* a valid one. This
   is where the safety stops being a claim and becomes something you've seen.
4. **[Glossary](GLOSSARY.md)** — skim it once so the special words stop being
   scary.
5. Now you can wander into [How-To Guides](how-to/) or the deep
   [Reference](#5-reference--deep-architecture) and it will make sense.

That is the whole on-ramp. About 70 minutes, no prior knowledge assumed.

---

## 4. The "just run it" path (developers)

- [Quickstart](QUICKSTART.md) — install + tests + server in ~5 minutes.
- [README](../README.md) — product summary, runtime flags, swarm surface.
- [Deployment](../DEPLOYMENT.md) and [Runbook](../RUNBOOK.md) — for getting it
  onto real infrastructure.

---

## 5. Reference & deep architecture

The system is described plane by plane in numbered docs. You rarely need all of
them; the [Glossary](GLOSSARY.md) tells you which number to open for a given
concept. Common entry points:

- [00_platform_overview.md](00_platform_overview.md) — the architectural map.
- [01_shared_invariants.md](01_shared_invariants.md) — the rules that are always
  true (the safety guarantees).
- [04_policy_and_verification.md](04_policy_and_verification.md) — how actions
  are checked before they run.
- [03_trace_and_replay.md](03_trace_and_replay.md) — how every action is
  recorded and can be replayed.
- Full architecture index: every `NN_*.md` file in this folder is one subsystem.

Cross-project maps live one level up in
[`../../docs/`](../../docs/): the
[System Boundary Map](../../docs/mullu-system-boundary-map.md) and
[Trust Boundary Map](../../docs/mullu-trust-boundary-map.md) are the best
"where does responsibility start and stop" pictures.

---

## 6. If you are going to change the code

1. Read [`../AGENTS.md`](../../AGENTS.md) — the governance laws every change must
   satisfy.
2. Read [01_shared_invariants.md](01_shared_invariants.md) — what you must never
   break.
3. Use the [page template](_TEMPLATE.md) when you add or update any doc, so the
   docs stay consistent and beginner-safe.

---

## 7. How these docs stay understandable for everyone

Every page in this system should follow three rules. If you write or edit a doc,
keep them:

1. **Plain-language box first.** The top of every page has a short box that
   explains the page in everyday words *before* any jargon appears.
2. **Every special word is a link.** The first time a page uses a term like
   *governed swarm* or *witness*, it links to the [Glossary](GLOSSARY.md).
3. **"Go deeper" at the bottom.** Every page ends with links to the next level
   of detail, so a reader can always go further or stop comfortably.

The reusable [page template](_TEMPLATE.md) enforces all three. Copy it for any
new document.
