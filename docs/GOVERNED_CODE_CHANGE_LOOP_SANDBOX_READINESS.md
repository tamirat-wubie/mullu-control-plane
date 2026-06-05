# Governed Code-Change Loop Sandbox Readiness

Purpose: define the operator handoff for collecting strict governed code-change loop sandbox execution evidence.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: Linux execution lane, Docker CLI, reachable Docker daemon, `mullu-agent-runner:latest`, probe script, probe validator, and workspace governance preflight.
Invariants: sandbox execution remains Linux-only; blocked evidence is valid but not strict readiness; probe receipts are not terminal closure; public deployment claims remain out of scope.

## Boundary

The governed code-change loop can be part of the long-term plan only as a foundation-stage proof thread until strict sandbox evidence passes on a Linux execution lane. A Windows host with Docker available remains `AwaitingEvidence` because `gateway/sandbox_runner.py` admits sandbox execution only when `platform.system()` reports Linux.

Do not bypass the Linux-only runner by treating Windows Docker Desktop as a strict readiness witness. That would weaken the execution-environment invariant and collapse blocked evidence into an unearned closure claim.

## Windows Local Path

First assess the Windows host without making a strict-readiness claim:

```powershell
python scripts/assess_windows_governed_code_change_loop_readiness.py --json
```

If WSL is not installed, use Windows-local mode to keep local governance work
moving without probing WSL or Docker:

```powershell
python scripts/assess_windows_governed_code_change_loop_readiness.py --local-only --json
```

Windows-local mode returns `local_only_ready` only for the local proof lane. It
skips WSL and Docker checks, leaves strict Linux sandbox evidence as
`AwaitingEvidence`, and points the next action to the workspace governance
preflight instead of the WSL strict probe.

Use strict mode when automation should fail closed until Docker Desktop and WSL prerequisites are available:

```powershell
python scripts/assess_windows_governed_code_change_loop_readiness.py --strict --json
```

Inspect the strict WSL command without probing Docker or WSL:

```powershell
python scripts/assess_windows_governed_code_change_loop_readiness.py --print-command --json
```

The Windows readiness assessor reports `AwaitingEvidence` by design. It only proves whether the Windows host is ready to launch the WSL strict probe; it does not replace the Linux strict sandbox receipt.

Use WSL2 Ubuntu as the local Linux execution lane. This does not require a separate Linux computer, but the probe command must run inside Ubuntu so Python reports `Linux`.

Preferred one-command launcher from Windows PowerShell:

```powershell
python scripts/run_wsl_governed_code_change_loop_sandbox_probe.py --distro Ubuntu --user root --strict --json
```

The launcher prepares Docker Desktop's native WSL CLI fallback when available, builds `mullu-agent-runner:latest`, runs the strict probe inside Ubuntu, validates the strict probe artifact, and validates the strict code-change loop receipt. Add `--with-preflight` only when you want the same WSL pass to run the full workspace governance receipt lane.

Inspect the generated WSL command without executing it:

```powershell
python scripts/run_wsl_governed_code_change_loop_sandbox_probe.py --print-command --json
```

Required workstation state:

| Requirement | Check |
| --- | --- |
| WSL2 Ubuntu exists | `wsl -l -v` |
| Ubuntu starts | `wsl -d Ubuntu -- uname -a` |
| Python exists in Ubuntu | `wsl -d Ubuntu -- python3 --version` |
| Docker CLI is available in Ubuntu | `wsl -d Ubuntu -- docker --version` |
| Docker daemon is reachable from Ubuntu | `wsl -d Ubuntu -- docker info --format '{{json .SecurityOptions}}'` |

If Docker is missing inside Ubuntu, enable Docker Desktop WSL integration for the Ubuntu distro, then restart Ubuntu:

```powershell
wsl --shutdown
wsl -d Ubuntu -- docker --version
```

If Docker Desktop WSL integration is not enabled in Ubuntu, use Docker Desktop's native WSL CLI and socket as a local fallback. This still runs the probe inside Ubuntu so `platform.system()` reports `Linux`; the sandboxed container still runs as the profile user `nonroot`.

The sandbox runner preserves this boundary by translating Docker Desktop WSL bind mount sources from `/mnt/c/...` to daemon-visible `/mnt/host/c/...` while leaving the seccomp profile path as the Ubuntu-readable `/mnt/c/...` path. The seccomp profile is read by the Docker CLI client; the bind mount source is resolved by the Docker daemon.

Prepare a repo-local Docker CLI shim:

```powershell
wsl -d Ubuntu -u root -- bash -lc "cd '/mnt/c/Users/tmrtl/Projects/Agentic framwork and computer uses inteligence' && mkdir -p .tmp/wsl-docker-native-bin && printf '%s\n' '#!/usr/bin/env sh' 'export DOCKER_HOST=unix:///mnt/wsl/docker-desktop/shared-sockets/guest-services/docker.proxy.sock' 'exec /mnt/wsl/docker-desktop/cli-tools/usr/bin/docker \"$@\"' > .tmp/wsl-docker-native-bin/docker && chmod +x .tmp/wsl-docker-native-bin/docker"
```

Build the governed local runner image:

```powershell
wsl -d Ubuntu -u root -- bash -lc "cd '/mnt/c/Users/tmrtl/Projects/Agentic framwork and computer uses inteligence' && PATH=\"$PWD/.tmp/wsl-docker-native-bin:$PATH\" docker build -f docker/governed-code-change-loop-runner.Dockerfile -t mullu-agent-runner:latest docker"
```

Then run strict evidence through that shim:

```powershell
wsl -d Ubuntu -u root -- bash -lc "cd '/mnt/c/Users/tmrtl/Projects/Agentic framwork and computer uses inteligence' && PATH=\"$PWD/.tmp/wsl-docker-native-bin:$PATH\" python3 scripts/probe_governed_code_change_loop_sandbox.py --output .change_assurance/governed_code_change_loop_sandbox_probe.json --receipt-output .change_assurance/governed_code_change_loop_probe_receipt.json --probe-workspace .tmp/governed-code-change-loop-probe-workspace --sandbox-image mullu-agent-runner:latest --strict --json"
```

Run strict evidence from WSL using the repository path mounted under `/mnt/c/...`:

```powershell
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/tmrtl/Projects/Agentic framwork and computer uses inteligence' && python3 scripts/probe_governed_code_change_loop_sandbox.py --output .change_assurance/governed_code_change_loop_sandbox_probe.json --receipt-output .change_assurance/governed_code_change_loop_probe_receipt.json --probe-workspace .tmp/governed-code-change-loop-probe-workspace --strict --json"
```

Then validate strict readiness from WSL:

```powershell
wsl -d Ubuntu -- bash -lc "cd '/mnt/c/Users/tmrtl/Projects/Agentic framwork and computer uses inteligence' && python3 scripts/validate_governed_code_change_loop_sandbox_probe.py --probe .change_assurance/governed_code_change_loop_sandbox_probe.json --require-strict-sandbox-ready --json"
```

## Evidence Command

Run this inside the Linux execution lane with Docker available and the `mullu-agent-runner:latest` image present:

```powershell
python scripts/probe_governed_code_change_loop_sandbox.py --output .change_assurance/governed_code_change_loop_sandbox_probe.json --receipt-output .change_assurance/governed_code_change_loop_probe_receipt.json --probe-workspace .tmp/governed-code-change-loop-probe-workspace --strict --json
```

Then validate strict readiness:

```powershell
python scripts/validate_governed_code_change_loop_sandbox_probe.py --probe .change_assurance/governed_code_change_loop_sandbox_probe.json --require-strict-sandbox-ready --json
```

Then run the workspace governance receipt lane:

```powershell
python scripts/run_workspace_governance_checks.py --json --receipt-path .tmp/workspace-governance-preflight-receipt.json
python scripts/validate_workspace_governance_preflight_receipt.py --receipt .tmp/workspace-governance-preflight-receipt.json
```

## Required Passing Shape

The strict probe is ready only when the probe artifact has:

| Field | Required value |
| --- | --- |
| `status` | `passed` |
| `platform_system` | `Linux` |
| `docker_cli_status` | `available` |
| `docker_daemon_status` | `reachable` |
| `normal_receipt_valid` | `true` |
| `strict_sandbox_valid` | `true` |
| `solver_outcome` | `SolvedVerified` |
| `closure_allowed` | `true` |
| `blockers` | `[]` |
| `receipt_is_not_terminal_closure` | `true` |
| `terminal_closure_required` | `true` |

## Blocked Evidence Shape

Blocked probe evidence remains valid when blockers are explicit. Expected blockers include:

| Blocker | Meaning |
| --- | --- |
| `windows_host_required` | The Windows readiness assessor was invoked from a non-Windows host. |
| `windows_docker_cli_missing` | Docker CLI is unavailable from Windows PowerShell. |
| `windows_docker_cli_failed` | Docker CLI launched but failed its version probe. |
| `windows_docker_cli_timeout` | Docker CLI version probe timed out. |
| `windows_docker_daemon_unreachable` | Docker CLI exists but the Docker daemon is not reachable. |
| `windows_docker_daemon_timeout` | Docker daemon probe timed out. |
| `windows_wsl_cli_missing` | WSL CLI is unavailable from Windows PowerShell. |
| `windows_wsl_status_failed` | WSL exists but status probing failed. |
| `windows_wsl_status_timeout` | WSL status probe timed out. |
| `windows_wsl_distro_unavailable` | The target WSL distro does not launch. |
| `windows_wsl_distro_timeout` | The target WSL distro launch probe timed out. |
| `windows_readiness_assessor_invalid_input` | The Windows assessor received invalid arguments. |
| `wsl_cli_missing` | Windows cannot launch WSL. |
| `wsl_workspace_path_invalid` | The launcher cannot translate the workspace path into `/mnt/<drive>/...`. |
| `wsl_strict_probe_timeout` | The WSL strict probe exceeded the launcher timeout. |
| `wsl_strict_probe_command_failed` | WSL launched, but build, probe, or strict validation failed. |
| `sandbox_runner_linux_only` | Host is not Linux. |
| `docker_cli_missing` | Docker CLI is unavailable. |
| `docker_daemon_unreachable` | Docker daemon is not reachable. |
| `governed_code_change_loop_strict_sandbox_invalid` | Receipt exists but does not prove strict sandbox execution. |
| `solver_outcome_GovernanceBlocked` | The code-change loop correctly blocked closure. |
| `code_worker_sandbox_runner_linux_only` | The worker receipt confirms Linux-only sandbox admission denial. |
| `sandbox_verification_not_passed` | Strict receipt verification did not pass. |

## Claim Boundary

Until strict validation passes, report the long-term plan state as `AwaitingEvidence`. If strict validation passes but full governance preflight does not, report `GovernanceBlocked`. Only report `SolvedVerified` after strict probe validation and saved preflight receipt validation both pass.

STATUS:
  Completeness: 100%
  Invariants verified: Linux-only sandbox boundary, no terminal closure from probe evidence, explicit blocker taxonomy
  Open issues: strict readiness requires a Linux execution lane
  Next action: run the strict probe on Linux and validate the saved governance receipt
