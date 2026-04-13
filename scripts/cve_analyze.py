#!/usr/bin/env python3
"""
CVE Vulnerability Analysis Tool
Fetches CVE details from NVD/OSV, inspects a repository via GitHub API,
then uses Claude AI to produce a structured security assessment report.
"""

import base64
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
import anthropic

# ── Constants ──────────────────────────────────────────────────────────────────

NVD_API_BASE    = "https://services.nvd.nist.gov/rest/json/cves/2.0"
OSV_API_BASE    = "https://api.osv.dev/v1/vulns"
GITHUB_API_BASE = "https://api.github.com"

MAX_FILE_SIZE_BYTES  = 80_000   # skip files larger than this
MAX_TOTAL_CONTENT_KB = 700      # cap total content sent to Claude
MAX_SOURCE_FILES     = 80       # max source files to include

DEPENDENCY_FILE_NAMES: set[str] = {
    # JavaScript / Node
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    # Python
    "requirements.txt", "requirements-dev.txt", "requirements-test.txt",
    "Pipfile", "Pipfile.lock", "pyproject.toml", "setup.py", "setup.cfg",
    # Go
    "go.mod", "go.sum",
    # Java / Kotlin
    "pom.xml", "build.gradle", "build.gradle.kts", "gradle.properties",
    # Rust
    "Cargo.toml", "Cargo.lock",
    # Ruby
    "Gemfile", "Gemfile.lock",
    # PHP
    "composer.json", "composer.lock",
    # Elixir
    "mix.exs", "mix.lock",
    # Scala
    "build.sbt",
    # Dart / Flutter
    "pubspec.yaml", "pubspec.lock",
    # .NET
    "packages.config", "NuGet.Config", "global.json",
}

SOURCE_EXTENSIONS: set[str] = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs",
    ".go", ".java", ".kt", ".scala", ".groovy",
    ".rb", ".php", ".cs", ".cpp", ".c", ".h", ".hpp",
    ".rs", ".swift", ".dart", ".lua", ".ex", ".exs",
    ".yaml", ".yml", ".json", ".toml", ".xml",
    ".sh", ".bash", ".zsh", ".fish",
    ".tf", ".hcl",
    ".dockerfile",
}

SKIP_DIRS: set[str] = {
    "node_modules", ".git", "vendor", ".venv", "venv", "__pycache__",
    ".gradle", "target", "dist", "build", ".next", ".nuxt",
    "coverage", ".nyc_output", ".cache", "tmp", ".tmp",
    ".tox", ".mypy_cache", ".pytest_cache", "htmlcov",
}


# ── NVD / OSV ──────────────────────────────────────────────────────────────────

def fetch_cve_nvd(cve_id: str) -> dict:
    """Fetch CVE details from NVD API v2."""
    url = f"{NVD_API_BASE}?cveId={cve_id}"
    headers: dict[str, str] = {"User-Agent": "cve-analyzer/1.0"}
    nvd_key = os.environ.get("NVD_API_KEY", "")
    if nvd_key:
        headers["apiKey"] = nvd_key

    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 429:
                wait = 6 * (attempt + 1)
                print(f"[NVD] Rate limited — waiting {wait}s…")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            vulns = resp.json().get("vulnerabilities", [])
            if vulns:
                return vulns[0].get("cve", {})
            print(f"[NVD] {cve_id} not found")
            return {}
        except Exception as exc:
            print(f"[NVD] Attempt {attempt + 1} failed: {exc}")
            if attempt < 2:
                time.sleep(3)
    return {}


def fetch_cve_osv(cve_id: str) -> dict:
    """Fetch package-level details from OSV."""
    try:
        resp = requests.get(f"{OSV_API_BASE}/{cve_id}", timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception as exc:
        print(f"[OSV] Failed: {exc}")
    return {}


def parse_cvss(cve_data: dict) -> tuple[float, str, str]:
    """Return (score, severity, vector) from the highest available CVSS version."""
    metrics = cve_data.get("metrics", {})
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30"):
        entries = metrics.get(key, [])
        if entries:
            cvss = entries[0]["cvssData"]
            return (
                float(cvss.get("baseScore", 0.0)),
                cvss.get("baseSeverity", "UNKNOWN"),
                cvss.get("vectorString", ""),
            )
    for entry in metrics.get("cvssMetricV2", []):
        cvss = entry["cvssData"]
        return (
            float(cvss.get("baseScore", 0.0)),
            entry.get("baseSeverity", "UNKNOWN"),
            cvss.get("vectorString", ""),
        )
    return (0.0, "UNKNOWN", "")


def extract_affected_packages(cve_data: dict, osv_data: dict) -> list[str]:
    """Heuristically extract package/library names from CVE+OSV data."""
    packages: list[str] = []

    # OSV affected packages (most reliable)
    for affected in osv_data.get("affected", []):
        name = affected.get("package", {}).get("name", "")
        if name and name not in packages:
            packages.append(name)

    # Heuristic: parse CVE English description
    desc = next(
        (d["value"] for d in cve_data.get("descriptions", []) if d.get("lang") == "en"),
        "",
    )
    patterns = [
        r"(?:in|via|of|using)\s+([a-zA-Z0-9][\w\-\.]+)\s+(?:before|prior|through|version|\d)",
        r"([a-zA-Z0-9][\w\-\.]+)\s+(?:package|library|module|component|framework|gem|crate)",
    ]
    for pat in patterns:
        for match in re.findall(pat, desc, re.IGNORECASE):
            candidate = match.strip()
            if 2 < len(candidate) < 50 and candidate not in packages:
                packages.append(candidate)

    return packages


# ── GitHub API ─────────────────────────────────────────────────────────────────

def _gh_headers(token: str) -> dict[str, str]:
    h: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def github_get(path: str, token: str) -> Optional[dict | list]:
    url = f"{GITHUB_API_BASE}/{path.lstrip('/')}"
    try:
        resp = requests.get(url, headers=_gh_headers(token), timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as exc:
        print(f"[GitHub] HTTP {exc.response.status_code} for {url}")
        return None
    except Exception as exc:
        print(f"[GitHub] Error: {exc}")
        return None


def fetch_repo_tree(owner: str, repo: str, branch: str, token: str) -> list[dict]:
    """Return flat list of all blob entries in the repository tree."""
    # Resolve branch → SHA (fall back to main/master)
    sha: Optional[str] = None
    for b in [branch, "main", "master"]:
        data = github_get(f"repos/{owner}/{repo}/branches/{b}", token)
        if data and "commit" in data:
            sha = data["commit"]["sha"]
            if b != branch:
                print(f"[GitHub] Branch '{branch}' not found; using '{b}'")
            break

    if not sha:
        print(f"[GitHub] Could not resolve branch for {owner}/{repo}")
        return []

    tree_data = github_get(f"repos/{owner}/{repo}/git/trees/{sha}?recursive=1", token)
    if not tree_data:
        return []

    return [f for f in tree_data.get("tree", []) if f.get("type") == "blob"]


def select_files(
    tree: list[dict],
    affected_packages: list[str],
) -> tuple[list[str], list[str]]:
    """
    Returns (dependency_paths, source_paths).
    Dependency files are always included; source files are capped at MAX_SOURCE_FILES.
    """
    dependency_paths: list[str] = []
    source_paths: list[str] = []

    for item in tree:
        path: str = item.get("path", "")
        fname = path.rsplit("/", 1)[-1]

        if item.get("size", 0) > MAX_FILE_SIZE_BYTES:
            continue

        parts = path.split("/")
        if any(part in SKIP_DIRS for part in parts[:-1]):
            continue

        # ── Dependency files ────────────────────────────────────────────────
        if fname in DEPENDENCY_FILE_NAMES or re.match(r"requirements.*\.txt$", fname):
            dependency_paths.append(path)
            continue

        # ── .NET project files ──────────────────────────────────────────────
        if fname.endswith(".csproj") or fname.endswith(".fsproj"):
            dependency_paths.append(path)
            continue

        # ── Source files ────────────────────────────────────────────────────
        suffix = ("." + fname.rsplit(".", 1)[-1]) if "." in fname else ""
        if suffix.lower() in SOURCE_EXTENSIONS or fname.lower() == "dockerfile":
            source_paths.append(path)

    # Sort: root-level first, then ascending depth, then alphabetically
    source_paths.sort(key=lambda p: (p.count("/"), p))

    # Boost files whose path contains an affected package name
    if affected_packages:
        pkg_set = {p.lower().replace("-", "").replace("_", "") for p in affected_packages}

        def boost(path: str) -> int:
            norm = path.lower().replace("-", "").replace("_", "")
            return 0 if any(pkg in norm for pkg in pkg_set) else 1

        source_paths.sort(key=lambda p: (boost(p), p.count("/"), p))

    return dependency_paths, source_paths[:MAX_SOURCE_FILES]


def fetch_file_content(owner: str, repo: str, path: str, token: str) -> Optional[str]:
    """Fetch and decode a single file from GitHub Contents API."""
    data = github_get(f"repos/{owner}/{repo}/contents/{path}", token)
    if not data or not isinstance(data, dict) or "content" not in data:
        return None
    if data.get("size", 0) > MAX_FILE_SIZE_BYTES:
        return f"[Skipped — file too large: {data['size']} bytes]"
    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    except Exception:
        return None


# ── Prompt ─────────────────────────────────────────────────────────────────────

def load_system_prompt() -> str:
    """Load system prompt from prompts/ directory, or fall back to embedded."""
    candidates = [
        Path(__file__).parent.parent / "prompts" / "cve-security-analyst-system.md",
        Path("prompts/cve-security-analyst-system.md"),
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8")
    # Fallback — should not happen if repo is checked out correctly
    raise FileNotFoundError("System prompt file not found. Expected: prompts/cve-security-analyst-system.md")


def build_user_message(
    cve_id: str,
    cve_data: dict,
    osv_data: dict,
    target_repo: str,
    file_contents: dict[str, str],
    affected_packages: list[str],
) -> str:
    """Compose the user-turn message for the Claude API call."""
    score, severity, vector = parse_cvss(cve_data)
    published = cve_data.get("published", "Unknown")[:10]
    modified  = cve_data.get("lastModified", "Unknown")[:10]

    description = next(
        (d["value"] for d in cve_data.get("descriptions", []) if d.get("lang") == "en"),
        "No English description available.",
    )
    cwes = [
        d["value"]
        for w in cve_data.get("weaknesses", [])
        for d in w.get("description", [])
        if d.get("lang") == "en"
    ]
    references = [r["url"] for r in cve_data.get("references", [])[:8]]
    osv_aliases = osv_data.get("aliases", [])
    osv_summary = osv_data.get("summary", "")

    lines: list[str] = [
        "# Analysis Request",
        "",
        f"**CVE ID**: {cve_id}",
        f"**Target Repository**: `{target_repo}`",
        f"**Analysis Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "---",
        "",
        "## CVE Information",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| CVSS Score | **{score}** ({severity}) |",
        f"| CVSS Vector | `{vector}` |",
        f"| CWE | {', '.join(cwes) if cwes else 'N/A'} |",
        f"| Published | {published} |",
        f"| Last Modified | {modified} |",
        f"| OSV Aliases | {', '.join(osv_aliases) if osv_aliases else 'N/A'} |",
        "",
        "### Description",
        "",
        description,
        "",
    ]

    if osv_summary:
        lines += ["### OSV Summary", "", osv_summary, ""]

    if affected_packages:
        lines += ["### Identified Affected Packages", ""]
        lines += [f"- `{p}`" for p in affected_packages]
        lines += [""]

    # OSV affected ecosystems with version ranges
    if osv_data.get("affected"):
        lines += ["### OSV Affected Ecosystems & Version Ranges", ""]
        for aff in osv_data["affected"][:6]:
            pkg  = aff.get("package", {})
            name = pkg.get("name", "")
            eco  = pkg.get("ecosystem", "")
            fixed_vers = []
            for r in aff.get("ranges", []):
                for ev in r.get("events", []):
                    if "fixed" in ev:
                        fixed_vers.append(ev["fixed"])
            vuln_vers = aff.get("versions", [])[:8]
            lines.append(f"- **{eco}** / `{name}`")
            if fixed_vers:
                lines.append(f"  - Fixed in: {', '.join(f'`{v}`' for v in fixed_vers)}")
            if vuln_vers:
                lines.append(f"  - Example vulnerable versions: {', '.join(f'`{v}`' for v in vuln_vers)}")
        lines += [""]

    if references:
        lines += ["### NVD References", ""]
        lines += [f"- {r}" for r in references]
        lines += [""]

    lines += [
        "---",
        "",
        "## Repository Source Code",
        "",
        f"**Repository**: `{target_repo}`",
        f"**Total files provided**: {len(file_contents)}",
        "",
    ]

    if not file_contents:
        lines += ["*No repository files could be retrieved.*", ""]
    else:
        for path, content in file_contents.items():
            lang = path.rsplit(".", 1)[-1] if "." in path else ""
            lines += [
                f"### `{path}`",
                "",
                f"```{lang}",
                content or "(empty file)",
                "```",
                "",
            ]

    lines += [
        "---",
        "",
        "## Instructions",
        "",
        f"Analyze the repository code above for exposure to **{cve_id}**.",
        "Follow your analysis methodology and produce the full report in the exact Markdown structure specified in your system instructions.",
        "Cite actual file paths and relevant code snippets as evidence for every claim.",
        "If the vulnerable package is not found in the dependency files, state that clearly and assess whether the vulnerability could still apply.",
    ]

    return "\n".join(lines)


# ── Claude API ─────────────────────────────────────────────────────────────────

def run_claude_analysis(system_prompt: str, user_message: str) -> str:
    """Call Claude via Vertex AI and return the generated analysis text.

    Authentication uses Application Default Credentials (ADC).
    Required env vars:
      ANTHROPIC_VERTEX_PROJECT_ID  — GCP project ID
      ANTHROPIC_VERTEX_REGION      — e.g. us-east5 (default: us-east5)
    """
    project_id = os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID", "")
    region     = os.environ.get("ANTHROPIC_VERTEX_REGION", "us-east5")

    if not project_id:
        raise ValueError(
            "ANTHROPIC_VERTEX_PROJECT_ID environment variable is required for Vertex AI"
        )

    client = anthropic.AnthropicVertex(project_id=project_id, region=region)
    print(f"[Claude] Sending analysis request via Vertex AI "
          f"(project={project_id}, region={region})…")

    message = client.messages.create(
        model="claude-sonnet-4-6@20251001",
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


# ── Report Wrapping ────────────────────────────────────────────────────────────

def wrap_report(
    analysis: str,
    cve_id: str,
    target_repo: str,
    files_analyzed: list[str],
    cve_data: dict,
) -> str:
    """Prepend a metadata banner to the Claude-generated analysis."""
    score, severity, _ = parse_cvss(cve_data)

    banner = (
        "<!-- cve-analysis-report -->\n"
        "> **Generated by**: CVE Vulnerability Analysis Workflow (Claude AI)  \n"
        f"> **CVE**: `{cve_id}`  \n"
        f"> **Repository**: `{target_repo}`  \n"
        f"> **CVSS**: {score} ({severity})  \n"
        f"> **Analysis Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  \n"
        f"> **Files Analyzed**: {len(files_analyzed)}  \n"
        "\n---\n\n"
    )
    return banner + analysis


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    cve_id        = os.environ.get("CVE_ID", "").strip().upper()
    target_repo   = os.environ.get("TARGET_REPO", "").strip()
    target_branch = os.environ.get("TARGET_BRANCH", "main").strip()
    github_token  = os.environ.get("GITHUB_TOKEN", "").strip()
    output_file   = os.environ.get("OUTPUT_FILE", "cve-report.md")

    # ── Validation ──────────────────────────────────────────────────────────
    errors: list[str] = []
    if not cve_id:
        errors.append("CVE_ID is required")
    elif not re.match(r"^CVE-\d{4}-\d+$", cve_id):
        errors.append(f"Invalid CVE ID format: '{cve_id}' (expected CVE-YYYY-NNNN...)")
    if not target_repo or "/" not in target_repo:
        errors.append("TARGET_REPO must be 'owner/repo'")
    if not os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID", ""):
        errors.append("ANTHROPIC_VERTEX_PROJECT_ID is required (Vertex AI project ID)")
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    owner, repo = target_repo.split("/", 1)

    print(f"\n{'='*60}")
    print(f"  CVE Vulnerability Analysis")
    print(f"  CVE        : {cve_id}")
    print(f"  Repository : {target_repo}  (branch: {target_branch})")
    print(f"{'='*60}\n")

    # ── 1. Fetch CVE data ───────────────────────────────────────────────────
    print("[1/5] Fetching CVE data…")
    cve_data = fetch_cve_nvd(cve_id)
    osv_data = fetch_cve_osv(cve_id)

    affected_packages = extract_affected_packages(cve_data, osv_data)
    if affected_packages:
        print(f"       Affected packages detected: {', '.join(affected_packages[:8])}")

    # ── 2. Fetch repository file tree ───────────────────────────────────────
    print(f"[2/5] Fetching repository tree for {target_repo}…")
    tree = fetch_repo_tree(owner, repo, target_branch, github_token)
    print(f"       {len(tree)} files found in tree")

    # ── 3. Select files ─────────────────────────────────────────────────────
    print("[3/5] Selecting files for analysis…")
    dep_paths, src_paths = select_files(tree, affected_packages)
    print(f"       Dependency files: {len(dep_paths)},  Source files: {len(src_paths)}")

    # ── 4. Fetch file contents ───────────────────────────────────────────────
    print("[4/5] Fetching file contents…")
    file_contents: dict[str, str] = {}
    total_bytes = 0
    limit_bytes = MAX_TOTAL_CONTENT_KB * 1024

    for path in dep_paths + src_paths:
        if total_bytes >= limit_bytes:
            print(f"       Content cap reached ({MAX_TOTAL_CONTENT_KB} KB) — "
                  f"stopping at {len(file_contents)} files")
            break
        content = fetch_file_content(owner, repo, path, github_token)
        if content is not None:
            file_contents[path] = content
            total_bytes += len(content.encode("utf-8"))
        time.sleep(0.05)  # gentle rate limiting

    print(f"       Fetched {len(file_contents)} files "
          f"({total_bytes // 1024} KB total)")

    # ── 5. Run Claude analysis ───────────────────────────────────────────────
    print("[5/5] Running Claude AI security analysis…")
    system_prompt = load_system_prompt()
    user_message  = build_user_message(
        cve_id, cve_data, osv_data, target_repo, file_contents, affected_packages
    )
    analysis = run_claude_analysis(system_prompt, user_message)

    # ── Write report ─────────────────────────────────────────────────────────
    report = wrap_report(analysis, cve_id, target_repo, list(file_contents.keys()), cve_data)
    Path(output_file).write_text(report, encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"  Report saved: {output_file}")
    print(f"{'='*60}\n")

    # Extract and export risk level for GitHub Actions
    risk_match = re.search(
        r"\b(CRITICAL|HIGH|MEDIUM|LOW|SAFE)\b",
        analysis,
        re.IGNORECASE,
    )
    risk_level = risk_match.group(0).upper() if risk_match else "UNKNOWN"
    print(f"  RISK LEVEL: {risk_level}")

    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"risk_level={risk_level}\n")


if __name__ == "__main__":
    main()
