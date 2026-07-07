#!/usr/bin/env python3
"""Read-only audit for the current FreeGrasp paper submission package.

The script checks the current draft for package-level regressions:

- required manuscript/source/figure files exist;
- cite keys and manual bibitems match;
- main PDF and figure PDFs do not expose author/title/subject/keyword fields;
- PDF XMP metadata has no identity/path hints;
- PDFs do not use Type 3 fonts;
- manuscript source and selected reproducibility scripts do not contain obvious
  identity, absolute-path, repository, email, or API-key-like strings.

It does not modify files, rebuild LaTeX, call models, or read experiment data.
Run the failure-result audit separately with ``scripts/audit_failure_outcomes.py``.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


REQUIRED_FILES = [
    "paper/main.tex",
    "paper/sections/introduction.tex",
    "paper/sections/related_work.tex",
    "paper/sections/method.tex",
    "paper/sections/experiments.tex",
    "paper/sections/conclusion.tex",
    "paper/main.pdf",
    "paper/figures/system_overview.pdf",
    "paper/figures/eghc_architecture.pdf",
    "paper/figures/main_results.pdf",
    "paper/figures/ablation.pdf",
    "paper/figures/route_distribution.pdf",
    "paper/citation_claim_audit.md",
    "paper/failure_analysis.md",
    "paper/no_verifier_ablation_run_log.md",
    "scripts/audit_failure_outcomes.py",
]

SOURCE_SCAN_FILES = [
    "paper/main.tex",
    "paper/sections/introduction.tex",
    "paper/sections/related_work.tex",
    "paper/sections/method.tex",
    "paper/sections/experiments.tex",
    "paper/sections/conclusion.tex",
    "paper/create_figures.py",
    "scripts/audit_failure_outcomes.py",
]

LEAK_PATTERNS = {
    "absolute_path": re.compile(r"(/home/|/mnt/|[A-Za-z]:\\)"),
    "repo_or_url": re.compile(r"(github\.com|FreeGrasp_code-freegrasp_codex|FreeGrasp_code-main)", re.I),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "api_key_like": re.compile(
        r"(sk-[A-Za-z0-9_-]{20,}|api[_-]?key\s*[=:]|OPENAI_API_KEY|"
        r"DASHSCOPE_API_KEY|ANTHROPIC_API_KEY)",
        re.I,
    ),
}


def run_cmd(args: list[str], timeout: int = 10) -> str:
    try:
        proc = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required command not found: {args[0]}") from exc
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(args)}\n{proc.stderr}"
        )
    return proc.stdout


def check_required_files(root: Path) -> list[str]:
    failures: list[str] = []
    for rel in REQUIRED_FILES:
        path = root / rel
        if not path.exists():
            failures.append(f"missing required file: {rel}")
        elif path.is_file() and path.stat().st_size == 0:
            failures.append(f"empty required file: {rel}")
    return failures


def check_citations(root: Path) -> tuple[list[str], str]:
    files = [root / "paper/main.tex"] + sorted((root / "paper/sections").glob("*.tex"))
    text = "\n".join(p.read_text(errors="ignore") for p in files)
    main = (root / "paper/main.tex").read_text(errors="ignore")
    bibitems = set(re.findall(r"\\bibitem\{([^}]+)\}", main))
    cites: set[str] = set()
    for cite_group in re.findall(r"\\cite\{([^}]+)\}", text):
        cites.update(key.strip() for key in cite_group.split(",") if key.strip())
    missing = sorted(cites - bibitems)
    uncited = sorted(bibitems - cites)
    summary = f"citation_check cites={len(cites)} bibitems={len(bibitems)} missing={missing} uncited={uncited}"
    failures = []
    if missing:
        failures.append(f"missing bibitems for cited keys: {missing}")
    if uncited:
        failures.append(f"uncited bibitems: {uncited}")
    return failures, summary


def pdf_paths(root: Path) -> list[Path]:
    return [root / "paper/main.pdf"] + sorted((root / "paper/figures").glob("*.pdf"))


def check_pdf_metadata(root: Path) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    summaries: list[str] = []
    identity = re.compile(
        r"(github\.com|FreeGrasp_code|/home/|/mnt/|[A-Za-z]:\\|@|wyl|zb|lenovo)",
        re.I,
    )
    for path in pdf_paths(root):
        rel = path.relative_to(root)
        info = run_cmd(["pdfinfo", str(path)])
        bad_fields = [
            line
            for line in info.splitlines()
            if line.startswith(("Title:", "Author:", "Subject:", "Keywords:"))
            and line.split(":", 1)[1].strip()
        ]
        if bad_fields:
            failures.append(f"{rel} exposes metadata fields: {bad_fields}")

        xmp = run_cmd(["pdfinfo", "-meta", str(path)])
        if identity.search(xmp):
            failures.append(f"{rel} XMP metadata contains identity/path-like text")

        fonts = run_cmd(["pdffonts", str(path)])
        if "Type 3" in fonts:
            failures.append(f"{rel} uses Type 3 fonts")

        summaries.append(
            f"pdf_check {rel} bad_fields={len(bad_fields)} xmp_len={len(xmp)} type3={'Type 3' in fonts}"
        )
    return failures, summaries


def check_main_pdf_text(root: Path) -> tuple[list[str], str]:
    text = run_cmd(["pdftotext", str(root / "paper/main.pdf"), "-"])
    failures: list[str] = []
    bad = re.compile(r"(github\.com|FreeGrasp_code|/home/|/mnt/|[A-Za-z]:\\|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", re.I)
    hits = [line.strip() for line in text.splitlines() if bad.search(line)]
    allowed = [line for line in hits if line == "Anonymous Authors Under Review"]
    unexpected = [line for line in hits if line not in allowed]
    if unexpected:
        failures.append(f"main PDF text contains identity/path-like hits: {unexpected[:5]}")
    return failures, f"main_pdf_text unexpected_identity_hits={len(unexpected)}"


def check_source_leaks(root: Path) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    summaries: list[str] = []
    for rel in SOURCE_SCAN_FILES:
        path = root / rel
        if not path.exists():
            continue
        lines = path.read_text(errors="ignore").splitlines()
        for name, pattern in LEAK_PATTERNS.items():
            hits = []
            for idx, line in enumerate(lines, 1):
                if pattern.search(line):
                    if name == "email" and "@{}" in line:
                        continue
                    hits.append(f"{rel}:{idx}")
            if hits:
                failures.append(f"{name} hits: {hits[:10]}")
            summaries.append(f"source_scan {rel} {name}_hits={len(hits)}")
    return failures, summaries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()
    root = Path(args.root).resolve()

    failures: list[str] = []
    summaries: list[str] = []

    failures.extend(check_required_files(root))
    cite_failures, cite_summary = check_citations(root)
    failures.extend(cite_failures)
    summaries.append(cite_summary)
    pdf_failures, pdf_summaries = check_pdf_metadata(root)
    failures.extend(pdf_failures)
    summaries.extend(pdf_summaries)
    text_failures, text_summary = check_main_pdf_text(root)
    failures.extend(text_failures)
    summaries.append(text_summary)
    leak_failures, leak_summaries = check_source_leaks(root)
    failures.extend(leak_failures)
    summaries.extend(leak_summaries)

    for summary in summaries:
        print(summary)
    if failures:
        print("AUDIT_FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("AUDIT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
