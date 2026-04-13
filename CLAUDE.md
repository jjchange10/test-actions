# CVE Vulnerability Analysis — Project Context

This repository contains an AI-powered CVE triage automation built on **Claude Code**.

## Purpose

Given a CVE ID and a target GitHub repository, the system:
1. Fetches vulnerability details from NVD (CVSS, CWE, description) and OSV (package ecosystem, version ranges)
2. Inspects the target repository's dependency manifests and source code via GitHub API
3. Determines whether the codebase is critically exposed to the vulnerability
4. Produces a structured Markdown security report with risk level and actionable remediation

## Available Skills

### `/cve-analyze <CVE_ID> <owner/repo> [branch]`

Runs a full security analysis and writes `cve-report-<CVE_ID>.md` to the current directory.

```
/cve-analyze CVE-2021-44228 apache/logging-log4j2
/cve-analyze CVE-2023-44487 nginx/nginx main
/cve-analyze CVE-2024-3094 owner/myapp develop
```

## Risk Level Scale

| Level | Meaning |
|-------|---------|
| 🔴 CRITICAL | Vulnerable version in use + vulnerable feature actively called + reachable from untrusted input |
| 🟠 HIGH | Vulnerable version + feature called, but indirect exposure or partial mitigations |
| 🟡 MEDIUM | Vulnerable version declared + package used, but specific vulnerable path unclear |
| 🟢 LOW | Vulnerable package declared but vulnerable feature not detected in code |
| ✅ SAFE | Not affected, version outside range, or fix already applied |

## Running via GitHub Actions

Trigger `.github/workflows/cve-vulnerability-analysis.yml` manually from the Actions tab.

**Required secret**: `ANTHROPIC_API_KEY`

The workflow installs Claude Code CLI, runs `/cve-analyze` non-interactively, and uploads the report as a build artifact. Optionally creates a GitHub Issue.

## Behaviour Guidelines

When performing CVE analysis in this project:
- Always read `prompts/cve-security-analyst-system.md` for the full security specialist persona and report structure
- Cite specific file paths and code snippets for every finding — no unsubstantiated claims
- If data is unavailable or truncated, state the confidence impact explicitly
- When in doubt about risk level, lean toward raising it and explaining why
- All remediation steps must be immediately actionable with exact version numbers and commands
