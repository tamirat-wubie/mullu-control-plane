# Tutorial 1 — Your First Run, Step by Step

> **In one box:** By the end of this page you will have Mullu installed and
> running on your own computer, and you'll have seen its safety machinery with
> your own eyes. Every command is explained in plain words: what it does, what
> you should see, and what to do if it goes wrong. **No prior experience with
> this project is assumed.** Basic comfort opening a terminal is enough.
>
> This is a **tutorial** (learning by doing). It is intentionally slow and
> explanatory. If you just want fast setup with no explanations, use the
> [Quickstart](../QUICKSTART.md) instead.

If a word here confuses you (e.g. *control plane*, *MCOI*), it is one click away
in the [Glossary](../GLOSSARY.md). You will not get stuck.

---

## What you need first

| You need | Why | How to check |
| --- | --- | --- |
| Python 3.12 or newer | Mullu is written in Python | run `python --version` |
| `pip` | installs Mullu's code | run `pip --version` |
| A terminal | to type the commands below | PowerShell (Windows) or Terminal (Mac/Linux) |

If `python --version` shows something older than 3.12, install a newer Python
from python.org first, then come back. Everything else is optional for this
tutorial.

---

## Step 1 — Get into the project folder

**What we're doing:** moving the terminal's "current location" into the part of
the project you install.

PowerShell (Windows):
```powershell
cd "C:\Users\tmrtl\Projects\Agentic framwork and computer uses inteligence\mullu-control-plane"
```

Mac/Linux:
```bash
cd mullu-control-plane
```

**What you should see:** the prompt now shows you are inside
`mullu-control-plane`. Nothing else happens — `cd` just moves you.

---

## Step 2 — Install Mullu

**What we're doing:** installing the core engine (its package name is `mcoi` —
see [MCOI in the Glossary](../GLOSSARY.md#mcoi)) in "editable" mode, which means
Python uses the code right here in the folder.

```bash
pip install -e ./mcoi
```

**What you should see:** a stream of "Collecting…", "Installing…", ending with
something like `Successfully installed mcoi`. This can take a minute.

**If it fails:**
- "command not found: pip" → your Python install is incomplete; reinstall
  Python and tick "add to PATH".
- Permission errors → add `--user` to the command, or use a virtual
  environment (see [Quickstart](../QUICKSTART.md)).

---

## Step 3 — Prove the install actually works (run the tests)

**What we're doing:** running the project's own test suite. This is the fastest
honest way to confirm your machine can run Mullu correctly — if thousands of its
own checks pass, your setup is sound.

```bash
cd mcoi
python -m pytest tests/ -q
```

**What you should see:** a long run ending in a line like `46000 passed`. (The
exact number grows over time — see the [Quickstart](../QUICKSTART.md) for the
current expected count.) A few skipped tests are normal.

**If it fails:** note the first failing test name and check
[KNOWN_LIMITATIONS_v0.1.md](../../KNOWN_LIMITATIONS_v0.1.md) — environment-only
failures (missing optional credentials) are expected and safe to ignore for this
tutorial; a flood of failures means the install in Step 2 didn't complete.

This step is optional if you're impatient, but running it once means every later
problem is *not* an install problem — which saves you hours.

---

## Step 4 — Start the server

**What we're doing:** starting Mullu's [control plane](../GLOSSARY.md#control-plane)
in the safest possible mode — local, in-memory, no AI provider, no real money or
external calls possible. Perfect for a first look.

PowerShell (Windows) — note the env var is set on its own line:
```powershell
$env:MULLU_ENV = "local_dev"
uvicorn mcoi_runtime.app.server:app --port 8000
```

Mac/Linux:
```bash
MULLU_ENV=local_dev uvicorn mcoi_runtime.app.server:app --port 8000
```

**What you should see:** lines ending with
`Uvicorn running on http://127.0.0.1:8000`. The terminal then *stays open and
busy* — that's correct, the server is running. Leave this window alone.

**If it fails:**
- "Address already in use" → something else is on port 8000; change `--port
  8000` to `--port 8010`.
- "No module named uvicorn" → run `pip install uvicorn`, then retry.

---

## Step 5 — See it with your own eyes

**What we're doing:** opening the server's built-in interactive page in a
browser. This proves the server is alive and shows you every action the system
exposes.

Open this address in your browser:

```
http://localhost:8000/docs
```

(If you changed the port in Step 4, change `8000` here to match.)

**What you should see:** an interactive API page listing the operations Mullu
exposes. You don't need to understand every line — the point is: **it's running,
and every capability it has is listed and explicit.** That visibility is not an
accident; "nothing hidden" is one of the system's [invariants](../GLOSSARY.md#invariant).

> ⚠️ In `local_dev` mode, the powerful surfaces (real payments, the
> [governed swarm](../GLOSSARY.md#governed-swarm)) are **disabled by default**.
> That is intentional and correct: Mullu does not expose consequential power
> until it is explicitly configured to. You just witnessed rule #1 of the
> [Plain-English Overview](../explain/PLAIN_ENGLISH.md) in action.

---

## Step 6 — Stop cleanly

Go back to the server terminal and press `Ctrl + C`. The server shuts down.
Nothing was persisted, nothing external happened — by design.

---

## What you just learned

- How to install and run Mullu safely on your own machine.
- That its safety isn't a promise — consequential power is *off until explicitly
  turned on*, and you saw that yourself in Step 5.
- The vocabulary is no longer scary, because every term linked to one plain
  sentence.

## Where to go next

| You now want to... | Go to |
| --- | --- |
| Understand *why* it's built this way | [Plain-English Overview](../explain/PLAIN_ENGLISH.md) |
| Do a specific real task (deploy, set a budget) | [How-To Guides](../how-to/) |
| Watch it govern something real, step by step | [Tutorial 2: Watch Mullu Govern Real Money](02_a_real_governed_task.md) |
| See the full doc map | [Start Here](../START_HERE.md) |
| Go deep on the safety rules | [01_shared_invariants.md](../01_shared_invariants.md) |

If any step here didn't behave as written, that's a documentation bug — the
promise of this tutorial is that following it exactly *works*. Compare against
the authoritative [Quickstart](../QUICKSTART.md) and report the difference.
