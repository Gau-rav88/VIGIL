#!/usr/bin/env python3
"""
scripts/check_no_fabricated.py
Static scanner to verify that no fabricated data, hardcoded test symbols (e.g., ZENITHSME),
canned mock alerts, or non-deterministic random data fabrication exist in production
services and frontend source code outside tests and demo fixtures.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Directories to scan
SCAN_DIRS = [
    Path("services"),
    Path("frontend/src"),
    Path("libs/vigil_common"),
]

# Paths/patterns to ignore
IGNORE_PATHS = [
    re.compile(r"tests/"),
    re.compile(r"fixtures/"),
    re.compile(r"\.next/"),
    re.compile(r"node_modules/"),
    re.compile(r"__pycache__/"),
    re.compile(r"\.pyc$"),
    re.compile(r"reports/"),
    re.compile(r"services/simulator/"),  # Simulator generates market simulation events
]

# Disallowed regex patterns in production code
FORBIDDEN_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "Hardcoded test symbol ZENITHSME",
        re.compile(r"\bZENITHSME\b"),
    ),
    (
        "Hardcoded case fallback case_01",
        re.compile(r"""["']case_01["']"""),
    ),
    (
        "Fabricated mock evidence tag",
        re.compile(r"""["']EV-MOCK-"""),
    ),
]

# Random usage is forbidden in analytics, api, and evidence services
RANDOM_FORBIDDEN_DIRS = [
    Path("services/api"),
    Path("services/evidence_engine"),
    Path("services/alignment_engine"),
    Path("services/agents"),
    Path("frontend/src"),
]

RANDOM_PATTERN = re.compile(r"\brandom\.(randint|random|choice|choices|sample|uniform)\b")


def check_file(path: Path) -> list[str]:
    violations: list[str] = []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return [f"Could not read {path}: {e}"]

    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        # Ignore comments
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        for rule_name, pat in FORBIDDEN_RULES:
            if pat.search(line):
                violations.append(f"[{rule_name}] {path}:{idx}: {line.strip()}")

        # Check random usage if in restricted dirs
        if any(r_dir in path.parents or path.is_relative_to(r_dir) for r_dir in RANDOM_FORBIDDEN_DIRS):
            if RANDOM_PATTERN.search(line):
                violations.append(f"[Random data generation in production] {path}:{idx}: {line.strip()}")

    return violations


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)

    print("Running static verification against fabricated/canned mock data...")
    all_violations: list[str] = []
    files_checked = 0

    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for p in scan_dir.rglob("*"):
            if not p.is_file():
                continue
            if any(ign.search(str(p)) for ign in IGNORE_PATHS):
                continue
            if p.suffix not in (".py", ".ts", ".tsx", ".js", ".jsx", ".json"):
                continue

            files_checked += 1
            violations = check_file(p)
            all_violations.extend(violations)

    print(f"Checked {files_checked} production source files.")
    if all_violations:
        print(f"\n[FAIL] Found {len(all_violations)} violations of no-fabricated-data rules:")
        for v in all_violations:
            print(f"  - {v}")
        return 1
    else:
        print("[PASS] Zero fabricated data, canned symbols, or random data patterns detected.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
