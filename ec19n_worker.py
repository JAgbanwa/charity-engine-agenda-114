#!/usr/bin/env python3
"""
ec19n_worker.py  —  Charity Engine worker
==========================================
Searches for ALL integer solutions (n, x, y) satisfying:

    y² = x³ + 1296·n²·x² + 15552·n³·x + (46656·n⁴ − 19·n)

Reduction to short Weierstrass form:
    Let  X = x + 432·n²
    Then y² = X³ + A(n)·X + B(n)   where
         A(n) = 15552·n³ − 559872·n⁴
         B(n) = 161243136·n⁶ − 6718464·n⁵ + 46656·n⁴ − 19·n

Algorithm: PARI/GP ellintegralpoints() — the Tzanakis–de Weger method,
which is PROVABLY COMPLETE (no integer points are ever missed).

This worker covers both positive and negative n.  The sign symmetry:
    For E_n vs E_(-n):  A(-n) = -15552n³ - 559872n⁴,  B(-n) differs.
So positive and negative n must be checked independently.

CE invocation:
    python /app/ec19n_worker.py --n-start 1 --n-count 500
    python /app/ec19n_worker.py --n-start 1 --n-count 500 --negatives

Output → /local/output/
    result.json      — always written
    SOLUTION.txt     — written only when solutions are found

Author: Jamal Agbanwa
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────────────────────
OUTPUT_DIR     = Path(os.environ.get("CE_OUTPUT_DIR", "/local/output"))
TIMEOUT_PER_N  = int(os.environ.get("EC19N_TIMEOUT", "600"))   # 10 min per n
TOTAL_TIMEOUT  = int(os.environ.get("EC19N_TOTAL",   "82800"))  # 23 h
CHECKPOINT_FILE = Path("/tmp/ec19n_checkpoint.dat")
PARI_GP_BIN    = os.environ.get("PARI_GP_BIN", "gp")

# ─── Graceful shutdown ────────────────────────────────────────────────────────
_keep_running = True
def _sig_handler(sig, frame):
    global _keep_running
    _keep_running = False
    print("\n[signal] Shutdown requested; finishing current n...", file=sys.stderr)
signal.signal(signal.SIGTERM, _sig_handler)
signal.signal(signal.SIGINT,  _sig_handler)


# ─── Short Weierstrass coefficients (Python big-int, for verification) ────────
def ec_AB(n: int) -> tuple[int, int]:
    A = 15552 * n**3 - 559872 * n**4
    B = 161243136 * n**6 - 6718464 * n**5 + 46656 * n**4 - 19 * n
    return A, B


def verify_solution(n: int, x: int, y: int) -> bool:
    """Verify (x,y) in ORIGINAL equation."""
    lhs = y * y
    rhs = (x**3 + 1296 * n**2 * x**2
           + 15552 * n**3 * x
           + 46656 * n**4 - 19 * n)
    return lhs == rhs


# ─── PARI/GP helpers ──────────────────────────────────────────────────────────
def find_gp() -> str:
    import shutil
    env_val = os.environ.get("PARI_GP_BIN", "")
    if env_val and shutil.which(env_val):
        return env_val
    for cand in ["gp", "gp-2.15", "gp2c"]:
        if shutil.which(cand):
            return cand
    raise FileNotFoundError(
        "PARI/GP binary 'gp' not found. "
        "Install with:  apt-get install pari-gp"
    )


def _make_gp_script(n: int) -> str:
    A, B = ec_AB(n)
    return f"""\
A = {A};
B = {B};
N_VAL = {n};
SHIFT = {432 * n * n};

/* ---- Degenerate case: n=0 → y²=x³ → skip ---- */
if (N_VAL == 0,
  print("DEGENERATE: n=0");
  print("DONE: n=0");
  quit
);

E = ellinit([0, 0, 0, A, B]);

if (E.disc == 0,
  print("SINGULAR: n=", N_VAL);
  print("DONE: n=", N_VAL);
  quit
);

rk = ellanalyticrank(E);
print("RANK: n=", N_VAL, " rank=", rk[1]);

pts = ellintegralpoints(E, 1);

if (#pts == 0,
  print("NOINT: n=", N_VAL),
  for(i=1,#pts,
    P     = pts[i];
    X_val = P[1];
    y_val = P[2];
    x_val = X_val - SHIFT;
    lhs = y_val^2;
    rhs = x_val^3 + 1296*N_VAL^2*x_val^2
          + 15552*N_VAL^3*x_val + 46656*N_VAL^4 - 19*N_VAL;
    if (lhs == rhs,
      print("SOLUTION: n=", N_VAL, " x=", x_val, " y=", y_val),
      print("VERIFY_FAIL: n=", N_VAL, " x=", x_val, " y=", y_val)
    )
  )
);

print("DONE: n=", N_VAL);
quit
"""


def run_gp_for_n(n: int, gp_bin: str, timeout: int) -> list[dict]:
    """Invoke PARI/GP for a single n.  Returns list of solution dicts."""
    script = _make_gp_script(n)
    try:
        proc = subprocess.run(
            [gp_bin, "-q"],
            input=script,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (proc.stdout + "\n" + proc.stderr).strip()
    except subprocess.TimeoutExpired:
        print(f"[timeout] n={n} exceeded {timeout}s", file=sys.stderr)
        return []
    except Exception as exc:
        print(f"[error] gp failed for n={n}: {exc}", file=sys.stderr)
        return []

    solutions = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("SOLUTION:"):
            try:
                parts = {}
                for tok in line.split()[1:]:
                    k, v = tok.split("=", 1)
                    parts[k] = int(v)
                if "n" in parts and "x" in parts and "y" in parts:
                    nn, xx, yy = parts["n"], parts["x"], parts["y"]
                    if verify_solution(nn, xx, yy):
                        solutions.append({"n": nn, "x": xx, "y": yy})
                    else:
                        print(f"[warn] gp reported solution fails verify: "
                              f"n={nn} x={xx} y={yy}", file=sys.stderr)
            except Exception:
                pass
        elif line.startswith("RANK:"):
            print(f"  [gp] {line}", file=sys.stderr)
        elif line.startswith("SINGULAR:") or line.startswith("DEGENERATE:"):
            print(f"  [gp] {line}", file=sys.stderr)
        elif line.startswith("NOINT:"):
            pass
        elif line.startswith("VERIFY_FAIL:"):
            print(f"  [gp][verify_fail] {line}", file=sys.stderr)
        elif line.startswith("*** "):
            print(f"  [gp][error] {line}", file=sys.stderr)

    return solutions


# ─── Checkpoint helpers ───────────────────────────────────────────────────────
def write_checkpoint(n: int) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(str(n))

def read_checkpoint() -> int | None:
    try:
        val = int(CHECKPOINT_FILE.read_text().strip())
        print(f"[ckpt] Resuming from n={val}", file=sys.stderr)
        return val
    except Exception:
        return None


# ─── Output helpers ───────────────────────────────────────────────────────────
def write_output(solutions: list[dict], stats: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    record = {
        "equation": "y^2 = x^3 + 1296*n^2*x^2 + 15552*n^3*x + 46656*n^4 - 19*n",
        "algorithm": "PARI/GP ellintegralpoints (Tzanakis–de Weger, provably complete)",
        "solutions": solutions,
        "stats": stats,
    }
    rpath = OUTPUT_DIR / "result.json"
    rpath.write_text(json.dumps(record, indent=2))
    print(f"[out] result.json → {rpath}", file=sys.stderr)

    if solutions:
        lines = [
            "=" * 66,
            f"  SOLUTIONS FOUND — {len(solutions)} total",
            f"  Equation:  y² = x³ + 1296n²x² + 15552n³x + 46656n⁴ − 19n",
            "=" * 66,
        ]
        for s in solutions:
            n, x, y = s["n"], s["x"], s["y"]
            ok = verify_solution(n, x, y)
            lines.append(
                f"  n={n:>20}   x={x:>25}   y={y:>25}   "
                + ("✓" if ok else "✗ VERIFY FAILED")
            )
        lines.append("=" * 66)
        txt = "\n".join(lines) + "\n"
        spath = OUTPUT_DIR / "SOLUTION.txt"
        spath.write_text(txt)
        print(txt)
        print(f"[out] SOLUTION.txt → {spath}", file=sys.stderr)


# ─── Main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "CE worker: find ALL integer (n,x,y) satisfying\n"
            "  y² = x³ + 1296n²x² + 15552n³x + 46656n⁴ − 19n\n"
            "Uses PARI/GP ellintegralpoints (provably complete)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--n-start",   type=int, required=True,
                    help="First |n| value to test (always positive; negatives added via --negatives)")
    ap.add_argument("--n-count",   type=int, default=500,
                    help="How many consecutive n values (default 500)")
    ap.add_argument("--negatives", action="store_true",
                    help="Also test n = −n_start, …, −(n_start+n_count−1)")
    ap.add_argument("--include-zero", action="store_true",
                    help="Include n=0 (degenerate case, skipped by default)")
    ap.add_argument("--timeout",   type=int, default=TIMEOUT_PER_N,
                    help=f"Seconds per n value (default {TIMEOUT_PER_N})")
    ap.add_argument("--no-resume", action="store_true",
                    help="Ignore checkpoint and restart from scratch")
    args = ap.parse_args()

    # Build the ordered list of n values for this job
    n_list = list(range(args.n_start, args.n_start + args.n_count))
    if args.negatives:
        # Interleave: +n, −n for same |n| so solutions are found quickly
        n_list = [sign * v
                  for v in range(args.n_start, args.n_start + args.n_count)
                  for sign in (+1, -1)]
    if args.include_zero:
        n_list = [0] + n_list

    total = len(n_list)

    # Locate PARI/GP
    try:
        gp_bin = find_gp()
        print(f"[gp] binary: {gp_bin}", file=sys.stderr)
    except FileNotFoundError as exc:
        print(f"[fatal] {exc}", file=sys.stderr)
        return 1

    # Verify ellintegralpoints availability
    chk = subprocess.run(
        [gp_bin, "-q"],
        input="print(type(ellintegralpoints)); quit",
        capture_output=True, text=True, timeout=15,
    )
    if "CLOSURE" not in chk.stdout.upper() and "FUNC" not in chk.stdout.upper():
        print("[warn] ellintegralpoints may be absent — check PARI version",
              file=sys.stderr)
    else:
        print("[gp] ellintegralpoints: ✓ available", file=sys.stderr)

    # Resume logic
    resume_from = None
    if not args.no_resume:
        resume_from = read_checkpoint()

    print(f"[job] n-start={args.n_start}  n-count={args.n_count}  "
          f"negatives={args.negatives}  total-tests={total}",
          file=sys.stderr)

    all_solutions: list[dict] = []
    done = 0
    t0 = time.time()
    last_ckpt = t0

    for n_val in n_list:
        if not _keep_running:
            print("[signal] Stopping early.", file=sys.stderr)
            break

        # Wall-clock guard
        elapsed = time.time() - t0
        if elapsed > TOTAL_TIMEOUT:
            print(f"[limit] Total runtime {elapsed:.0f}s — stopping.", file=sys.stderr)
            break

        # Skip already-done n values when resuming
        if resume_from is not None and n_val < resume_from:
            done += 1
            continue

        # Skip n=0 unless requested
        if n_val == 0 and not args.include_zero:
            done += 1
            continue

        # Time budget for this n
        remaining = TOTAL_TIMEOUT - (time.time() - t0)
        per_n_limit = min(args.timeout, int(remaining))

        print(f"[search] n={n_val}  ({done+1}/{total})", file=sys.stderr)
        sols = run_gp_for_n(n_val, gp_bin, per_n_limit)

        if sols:
            all_solutions.extend(sols)
            print(f"[!!] {len(sols)} SOLUTION(S) for n={n_val}", file=sys.stderr)
            for s in sols:
                print(f"     x={s['x']}  y={s['y']}", file=sys.stderr)

        done += 1
        elapsed = time.time() - t0
        pct = 100.0 * done / total
        rate = done / max(elapsed, 0.1)
        print(f"[prog] {done}/{total} ({pct:.1f}%)  "
              f"elapsed={elapsed:.1f}s  rate={rate:.2f} n/s  "
              f"solutions={len(all_solutions)}",
              file=sys.stderr)

        # Checkpoint every 5 minutes
        if time.time() - last_ckpt >= 300:
            write_checkpoint(n_val + 1)
            last_ckpt = time.time()

    stats = {
        "n_start":        args.n_start,
        "n_count":        args.n_count,
        "negatives":      args.negatives,
        "n_tested":       done,
        "solutions_found": len(all_solutions),
        "runtime_s":      round(time.time() - t0, 2),
    }
    write_output(all_solutions, stats)

    # Clean checkpoint on clean exit
    if done == total and CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink(missing_ok=True)

    print(f"\n[done] Tested {done}/{total} n-values — "
          f"found {len(all_solutions)} solution(s).  "
          f"Runtime: {stats['runtime_s']:.1f}s",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
