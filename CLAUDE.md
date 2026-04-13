# CVE Vulnerability Analysis — Project Context

This repository contains an AI-powered CVE triage automation built on **Claude Code**.

## Purpose

Given a CVE ID and a target GitHub repository, the system:
1. Fetches vulnerability details from **NVD** (CVSS, CWE, description), **OSV** (package ecosystem, version ranges), and **GitHub Security Advisories** (patched versions, ecosystem-specific detail)
2. Inspects the target repository's dependency manifests and source code via GitHub API
3. Determines whether the codebase is critically exposed to the vulnerability
4. Produces a structured Markdown security report with risk level and actionable remediation

## Architecture

```
.claude/
  skills/cve-analyze/          ← authoritative skill (see SKILL.md)
    SKILL.md                   · execution steps + YAML frontmatter
    REPORT_TEMPLATE.md         · Markdown report skeleton
    RISK_LEVELS.md             · risk-level rubric
    scripts/                   · vetted helpers (NVD, OSV, GHSA, GitHub API)
  commands/cve-analyze.md      ← thin slash-command wrapper that loads the skill

prompts/
  cve-security-analyst-system.md  · system-prompt persona (senior appsec analyst)

.github/workflows/
  cve-vulnerability-analysis.yml  · manual-dispatch CI runner
```

The **skill** at `.claude/skills/cve-analyze/SKILL.md` is the single source of
truth for analysis logic. The slash command and the workflow both delegate to
it.

## Available Skills

### `/cve-analyze <CVE_ID> <owner/repo> [branch]`

Runs a full security analysis and writes `cve-report-<CVE_ID>.md` to the current directory.

```
/cve-analyze CVE-2021-44228 apache/logging-log4j2
/cve-analyze CVE-2023-44487 nginx/nginx main
/cve-analyze CVE-2024-3094  owner/myapp develop
```

Helper scripts live under `.claude/skills/cve-analyze/scripts/` and should be
preferred over raw `curl` in the skill body — they handle retries, rate
limits, and 404 fallbacks.

## Risk Level Scale

| Level | Meaning |
|-------|---------|
| 🔴 CRITICAL | Vulnerable version in use + vulnerable feature actively called + reachable from untrusted input |
| 🟠 HIGH | Vulnerable version + feature called, but indirect exposure or partial mitigations |
| 🟡 MEDIUM | Vulnerable version declared + package used, but specific vulnerable path unclear |
| 🟢 LOW | Vulnerable package declared but vulnerable feature not detected in code |
| ✅ SAFE | Not affected, version outside range, or fix already applied |

Full rubric: `.claude/skills/cve-analyze/RISK_LEVELS.md`.

## Running via GitHub Actions

Trigger `.github/workflows/cve-vulnerability-analysis.yml` manually from the Actions tab.

**Required secrets (Vertex AI via Workload Identity Federation):**
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`
- `GCP_PROJECT_ID`

The workflow:
1. Validates the `cve_id`, `target_repo`, and `target_branch` inputs (fails fast on shell-injection-shaped values).
2. Installs the Claude Code CLI.
3. Injects `prompts/cve-security-analyst-system.md` via `--append-system-prompt` so the analyst persona is guaranteed.
4. Runs the `/cve-analyze` skill in non-interactive mode.
5. Uploads the report as a build artifact and posts it to the job summary.
6. Optionally creates a GitHub Issue — but only if no open issue for the same CVE + target repo already exists.

## Behaviour Guidelines

When performing CVE analysis in this project:
- Follow `prompts/cve-security-analyst-system.md` for the full security-specialist persona and report structure.
- Cite specific file paths and code snippets for every finding — no unsubstantiated claims.
- If data is unavailable or truncated, state the confidence impact explicitly.
- When in doubt about risk level, lean toward raising it and explaining why.
- All remediation steps must be immediately actionable with exact version numbers and commands.
- Prefer the skill's helper scripts over raw `curl` — they already implement retries, rate-limit handling, and 404 fallbacks.
