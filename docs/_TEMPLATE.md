<!--
  COPY THIS FILE to create any new doc, then delete these instruction comments.
  This template is what keeps every page understandable at every level.
  It enforces the three rules from START_HERE.md §7:
    1. Plain-language box first
    2. Every special word links to the Glossary on first use
    3. "Go deeper" links at the bottom
  Pick ONE type for the page (Explanation | Tutorial | How-to | Reference)
  and keep the page faithful to that type — do not mix.
-->

# <Page Title — a plain noun phrase, not a code symbol>

<!-- TYPE: one of Explanation / Tutorial / How-to / Reference -->
<!-- AUDIENCE: who is this for? e.g. "non-technical", "new developer", "operator" -->

> **In one box:** <Two or three sentences a non-expert can understand, with NO
> jargon. Say what this page is, who it's for, and what the reader will know or
> have done by the end. If you cannot explain it without jargon here, define the
> jargon in the Glossary first.>
>
> <Optional second line: prerequisites in plain words, or "No prior knowledge
> assumed.">

---

## <First real section>

Write the body for the page's TYPE:

- **Explanation** → answer "what is this and *why*?" Use an analogy. Do not give
  step-by-step instructions here.
- **Tutorial** → numbered steps the reader performs. For every step say: what
  we're doing (plain words), the exact command, what they should see, and what
  to do if it fails. Slow and reassuring.
- **How-to** → numbered steps to achieve one specific goal. Assume the reader
  knows the basics; be concise. State the goal and the finished state up front.
- **Reference** → precise, complete, neutral facts. Tables over prose. No
  teaching, no motivation — just the truth about the thing.

The first time you use any special term (e.g. governed swarm, witness,
invariant), link it: `[term](../GLOSSARY.md#term)`. If the term isn't in the
Glossary yet, add it there first — that is not optional, it is how "any level of
user understands" stays true.

## <More sections as needed>

Keep paragraphs short. Prefer a table or a small diagram to a wall of text. If a
section is only meaningful to advanced readers, label it explicitly, e.g.
`### (Advanced) ...`, so beginners know they may skip it without missing
anything required.

---

## Go deeper / where to go next

<!-- ALWAYS end with this. Give the reader the next step up AND a way back.
     PATH DEPTH: the links below assume this page sits in docs/ root. If you
     copied the template into a subfolder (tutorials/, how-to/, reference/,
     explain/), prefix each link with the right number of `../` so it still
     resolves (e.g. ../GLOSSARY.md from a one-level-deep subfolder). -->

| You now want to... | Go to |
| --- | --- |
| Understand the big picture in plain words | [Plain-English Overview](explain/PLAIN_ENGLISH.md) |
| Look up a confusing word | [Glossary](GLOSSARY.md) |
| See the whole documentation map | [Start Here](START_HERE.md) |
| <The natural next, more detailed doc> | [<title>](<path>.md) |

← Back to [Start Here](START_HERE.md)

<!--
  AUTHOR CHECKLIST before you commit this page — all must be true:
  [ ] The "In one box" summary has zero jargon and is true.
  [ ] Page is exactly ONE type and stays in that type.
  [ ] Every special term links to the Glossary on first use.
  [ ] Every linked Glossary term actually exists in GLOSSARY.md.
  [ ] There is a "Go deeper" table and a link back to Start Here.
  [ ] A person with no prior knowledge could read the box and not feel lost.
-->
