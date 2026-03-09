#!/usr/bin/env python3
"""
ELLIPTIC WORKER  —  Charity Engine finite-job driver
Searches for integer solutions (x, y) to:

    y² = x³ + A(m)·x + B(m)

where:
    A(m) = (-1/3)·m⁴ + (1/3)·m³
    B(m) = (2/27)·m⁶ − (1/9)·m⁵ + (1/36)·m⁴ − (19/36)·m

Per the README, A and B are integers only when m ≡ 0 (mod 108).
This driver:
  1. Accepts --m-start / --m-count / --x-range from the CE command line.
  2. Generates a single STANDALONE work-unit input file ("in").
  3. Executes the compiled C binary (/app/elliptic_search) against it.
  4. Parses stdout/stderr for SOLUTION lines.
  5. Writes result.json (and SOLUTION.txt if anything is found) to OUTPUT_DIR.

Usage:
    python /app/elliptic_worker.py --m-start 0 --m-count 1000 --x-range 1000000

Args
----
--m-start   First m-step index (actual m = m_start * 108).
            m_start=0 → m starts at 0; m_start=100 → m starts at 10,800.
--m-count   Number of 108-multiples to cover in this job (default 1000).
--x-range   Symmetric x range tested for each m value (default 1,000,000).
            Actual search: x ∈ [−x_range, +x_range].

Output (CE convention): written to /local/output/
    result.json    — always written; contains stats + any solutions
    SOLUTION.txt   — written only when at least one solution is found

Author: Jamal Agbanwa
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

# ─── CE output directory (matches the Dockerfile VOLUME) ─────────────
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/local/output")

# Path to the compiled C binary built inside the Docker image
BINARY = os.environ.get("ELLIPTIC_BINARY", "/app/elliptic_search")

# In-file / out-file expected by the C binary (STANDALONE resolve = identity)
WORK_INPUT  = "/tmp/elliptic_in"
WORK_OUTPUT = "/tmp/elliptic_out"

# Pattern matching lines written by write_solution() in elliptic_search.c
# e.g.  "  m = 108"  / "  x = -345"  / "  y = 92"
SOL_BLOCK_RE = re.compile(
    r"SOLUTION FOUND:.*?m\s*=\s*(-?\d+).*?x\s*=\s*(-?\d+).*?y\s*=\s*(-?\d+)",
    re.DOTALL | re.MULTILINE,
)

M_STEP = 108   # lcm(3, 27, 9, 36) — only multiples give integer A, B


# ─── Verification (exact fraction arithmetic) ────────────────────────

def verify(m: int, x: int, y: int) -> bool:
    """Return True iff y² = x³ + A(m)·x + B(m) holds exactly."""
    from fractions import Fraction
    A = Fraction(-1, 3) * m**4 + Fraction(1, 3) * m**3
    B = (Fraction(2, 27) * m**6
         - Fraction(1, 9) * m**5
         + Fraction(1, 36) * m**4
         - Fraction(19, 36) * m)
    return y * y == x**3 + A * x + B


# ─── Write the work-unit input file ──────────────────────────────────

def write_input(m_start_idx: int, m_count: int, x_range: int) -> tuple[int, int]:
    """
    Write the binary's stdin file and return (m_first, m_last).
    Format expected by elliptic_search.c:
        m_start m_end m_step x_min x_max
    """
    m_first = m_start_idx * M_STEP
    m_last  = m_first + (m_count - 1) * M_STEP

    os.makedirs(os.path.dirname(WORK_INPUT) if os.path.dirname(WORK_INPUT) else ".", exist_ok=True)
    with open(WORK_INPUT, "w") as f:
        f.write(f"{m_first} {m_last} {M_STEP} {-x_range} {x_range}\n")

    return m_first, m_last


# ─── Parse solutions from C binary output ────────────────────────────

def parse_output(text: str) -> list[dict]:
    solutions = []
    for match in SOL_BLOCK_RE.finditer(text):
        m, x, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
        ok = verify(m, x, y)
        solutions.append({"m": m, "x": x, "y": y, "verified": ok})
    # Deduplicate (same m,x,|y|)
    seen = set()
    unique = []
    for s in solutions:
        key = (s["m"], s["x"], abs(s["y"]))
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


# ─── Write CE output files ────────────────────────────────────────────

def write_results(m_first: int, m_last: int, x_range: int,
                  solutions: list[dict], elapsed: float, returncode: int) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    result = {
        "problem": "y^2 = x^3 + A(m)*x + B(m)",
        "A_formula": "(-m^4 + m^3) / 3",
        "B_formula": "(8*m^6 - 12*m^5 + 3*m^4 - 57*m) / 108",
        "m_range": [m_first, m_last],
        "m_step": M_STEP,
        "x_range": [-x_range, x_range],
        "elapsed_seconds": round(elapsed, 2),
        "binary_exit_code": returncode,
        "solutions_found": len(solutions),
        "solutions": solutions,
    }

    with open(os.path.join(OUTPUT_DIR, "result.json"), "w") as f:
        json.dump(result, f, indent=2)

    if solutions:
        with open(os.path.join(OUTPUT_DIR, "SOLUTION.txt"), "w") as f:
            f.write("=" * 60 + "\n")
            f.write("SOLUTION(S) FOUND\n")
            f.write("y^2 = x^3 + A(m)*x + B(m)\n")
            f.write("=" * 60 + "\n\n")
            for s in solutions:
                f.write(f"m = {s['m']}\n")
                f.write(f"x = {s['x']}\n")
                f.write(f"y = {s['y']}\n")
                f.write(f"verified = {s['verified']}\n\n")


# ─── Entry point ─────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Charity Engine worker: elliptic curve integer solution search"
    )
    parser.add_argument(
        "--m-start", type=int, default=0,
        help="First m-step index (m = m_start * 108).  Default: 0",
    )
    parser.add_argument(
        "--m-count", type=int, default=1000,
        help="Number of m-multiples to search in this job.  Default: 1000",
    )
    parser.add_argument(
        "--x-range", type=int, default=1_000_000,
        help="Symmetric x-range tested per m.  Default: 1,000,000",
    )
    args = parser.parse_args()

    m_first, m_last = write_input(args.m_start, args.m_count, args.x_range)

    print(f"[elliptic_worker] m range : [{m_first}, {m_last}]  step {M_STEP}")
    print(f"[elliptic_worker] x range : [{-args.x_range}, {args.x_range}]")
    print(f"[elliptic_worker] binary  : {BINARY}")
    print(f"[elliptic_worker] output  : {OUTPUT_DIR}")
    sys.stdout.flush()

    if not os.path.isfile(BINARY):
        print(f"[elliptic_worker] ERROR: binary not found at {BINARY}", file=sys.stderr)
        sys.exit(1)

    # Patch environment so the C binary finds its files in /tmp
    env = os.environ.copy()
    # STANDALONE build uses strncpy(path, name, sizeof(path)) — reads "in" / writes "out"
    # We run from /tmp so relative names resolve correctly.
    run_cwd = "/tmp"

    # Link our input file to the name the binary expects ("in")
    in_link = os.path.join(run_cwd, "in")
    out_file = os.path.join(run_cwd, "out")
    try:
        if os.path.lexists(in_link):
            os.remove(in_link)
        os.symlink(WORK_INPUT, in_link)
    except OSError:
        # If symlink fails just copy
        import shutil
        shutil.copy(WORK_INPUT, in_link)

    # Remove stale output from a previous run
    if os.path.exists(out_file):
        os.remove(out_file)

    t0 = time.time()
    proc = subprocess.run(
        [BINARY],
        capture_output=True,
        text=True,
        cwd=run_cwd,
    )
    elapsed = time.time() - t0

    # Combine all output for parsing
    combined = (proc.stdout or "") + (proc.stderr or "")

    # Also read the "out" file written by the C binary (primary solution log)
    if os.path.exists(out_file):
        with open(out_file) as f:
            combined += f.read()

    solutions = parse_output(combined)

    print(f"[elliptic_worker] Done in {elapsed:.1f}s  |  solutions: {len(solutions)}")
    if solutions:
        for s in solutions:
            print(f"[elliptic_worker] *** SOLUTION: m={s['m']}  x={s['x']}  y={s['y']}  "
                  f"verified={s['verified']} ***")
    else:
        print("[elliptic_worker] No solutions found in this range.")
    sys.stdout.flush()

    write_results(m_first, m_last, args.x_range, solutions, elapsed, proc.returncode)

    # Mirror binary stderr to our stderr so CE task logs capture progress
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="")


if __name__ == "__main__":
    main()
