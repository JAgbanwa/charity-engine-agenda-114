#!/usr/bin/env python3
"""
collect_results.py — Aggregate results from all BOINC work unit output files.

Scans a directory of output files, extracts SOLUTION lines, deduplicates,
and writes a final report.

Usage:
    python3 collect_results.py [--results-dir ./results] [--output solutions_final.txt]
"""

import argparse
import os
import re
import sys

SOLUTION_RE = re.compile(
    r"SOLUTION(?:\s+FOUND)?:?\s*"
    r"m\s*=\s*(-?\d+)\s+"
    r"x\s*=\s*(-?\d+)\s+"
    r"y\s*=\s*(-?\d+)"
)

def parse_file(path):
    solutions = []
    try:
        with open(path) as f:
            content = f.read()
        for match in SOLUTION_RE.finditer(content):
            m, x, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
            solutions.append((m, x, y))
    except Exception as e:
        print(f"[warn] Could not parse {path}: {e}", file=sys.stderr)
    return solutions

def verify(m, x, y):
    """Verify y^2 == x^3 + A(m)*x + B(m) in exact integer arithmetic."""
    from fractions import Fraction
    A = Fraction(-1,3)*m**4 + Fraction(1,3)*m**3
    B = Fraction(2,27)*m**6 - Fraction(1,9)*m**5 + Fraction(1,36)*m**4 - Fraction(19,36)*m
    lhs = y * y
    rhs = x**3 + A*x + B
    return lhs == rhs, A, B

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--output",      default="solutions_final.txt")
    args = parser.parse_args()

    all_solutions = set()
    files_scanned = 0

    for root, dirs, files in os.walk(args.results_dir):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            sols = parse_file(fpath)
            for s in sols:
                all_solutions.add(s)
            files_scanned += 1

    print(f"Scanned {files_scanned} files, found {len(all_solutions)} unique (m,x,y) triples.")

    verified = []
    failed   = []
    for (m, x, y) in sorted(all_solutions):
        ok, A, B = verify(m, x, y)
        if ok:
            verified.append((m, x, y, A, B))
        else:
            failed.append((m, x, y))

    print(f"  Verified: {len(verified)}")
    print(f"  Failed verification: {len(failed)}")

    with open(args.output, "w") as f:
        f.write("=" * 70 + "\n")
        f.write("VERIFIED INTEGER SOLUTIONS TO:\n")
        f.write("  y^2 = x^3 + [(-1/3)m^4 + (1/3)m^3]*x\n")
        f.write("        + [(2/27)m^6 - (1/9)m^5 + (1/36)m^4 - (19/36)m]\n")
        f.write("=" * 70 + "\n\n")

        if verified:
            for (m, x, y, A, B) in verified:
                f.write(f"m = {m}\n")
                f.write(f"  x = {x}\n")
                f.write(f"  y = {y}  (and y = {-y} if nonzero)\n")
                f.write(f"  A(m) = {A}\n")
                f.write(f"  B(m) = {B}\n")
                f.write(f"  Check: {y}^2 = {y*y},  "
                        f"x^3+Ax+B = {x**3 + A*x + B}\n\n")
        else:
            f.write("No verified solutions found yet.\n")

        if failed:
            f.write("\n--- FAILED VERIFICATION (possibly corrupted output) ---\n")
            for (m, x, y) in failed:
                f.write(f"  m={m}  x={x}  y={y}\n")

    print(f"Report written to: {args.output}")

if __name__ == "__main__":
    main()
