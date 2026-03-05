#!/usr/bin/env python3
"""
FINITE JOB WORKER for x^3 + y^3 + z^3 = 114
Designed for Charity Engine distributed computing.

Usage:
    python worker.py --start N --count M

Searches n values from N to N+M-1 (and their negatives).
For each n, computes D = 36n^3 - 19, factors D, enumerates divisors
as alpha candidates, and checks whether x(alpha,n) is an integer.

Output written to /local/output/ (Charity Engine convention):
  - result.json   : range searched, timing, any solutions
  - SOLUTION.txt  : written ONLY if a solution is found

Each job is meant to be ~1 hour on an average CPU (i5 / Ryzen 5).
Calibrate --count accordingly (~100,000 for moderate n ranges).

Author: Jamal Agbanwa
"""

import argparse
import os
import sys
import time
import math
import json
import random
from collections import Counter

# ─── Output directory (CE convention; overridable for local testing) ───
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/local/output")

# Deterministic seed for Pollard-Rho reproducibility
RANDOM_SEED = 42


# ════════════════════════════════════════════════════════════════════════
# Math helpers — Miller-Rabin primality + Pollard-Rho factoring
# ════════════════════════════════════════════════════════════════════════

def is_probable_prime(n, k=8):
    if n < 2:
        return False
    small_primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    for p in small_primes:
        if n % p == 0:
            return n == p
    d = n - 1
    s = 0
    while d % 2 == 0:
        s += 1
        d //= 2
    for _ in range(k):
        a = random.randrange(2, n - 1)
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = (x * x) % n
            if x == n - 1:
                break
        else:
            return False
    return True


def pollard_rho(n):
    if n % 2 == 0:
        return 2
    if n % 3 == 0:
        return 3
    for _attempt in range(6):
        x = random.randrange(2, n - 1)
        y = x
        c = random.randrange(1, n - 1)
        d = 1
        while d == 1:
            x = (x * x + c) % n
            y = (y * y + c) % n
            y = (y * y + c) % n
            d = math.gcd(abs(x - y), n)
            if d == n:
                break
        if 1 < d < n:
            return d
    return None


def factor(n):
    """Return prime factorisation as Counter(prime -> exponent). n > 0."""
    n = abs(n)
    if n <= 1:
        return Counter()
    if is_probable_prime(n):
        return Counter([n])
    res = Counter()
    small_primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61]
    for p in small_primes:
        while n % p == 0:
            res[p] += 1
            n //= p
    while n > 1:
        if is_probable_prime(n):
            res[n] += 1
            break
        d = pollard_rho(n)
        if d is None:
            limit = int(min(100_000, math.isqrt(n) + 1))
            found = False
            for i in range(2, limit):
                if n % i == 0:
                    res[i] += 1
                    n //= i
                    found = True
                    break
            if not found:
                res[n] += 1
                break
        else:
            res += factor(d)
            n //= d
    return res


def divisors_from_factors(factors):
    """All positive divisors from a Counter of prime factors."""
    items = list(factors.items())
    if not items:
        return [1]

    def rec(i):
        if i == len(items):
            return [1]
        p, e = items[i]
        rest = rec(i + 1)
        out = []
        pe = 1
        for _ in range(e + 1):
            for r in rest:
                out.append(r * pe)
            pe *= p
        return out

    return rec(0)


# ════════════════════════════════════════════════════════════════════════
# Problem-specific check
# ════════════════════════════════════════════════════════════════════════

def is_perfect_square(n):
    if n < 0:
        return False, 0
    r = math.isqrt(n)
    return (r * r == n, r)


def check_candidate(n, alpha):
    """Return (x, y, z, alpha, n) if valid integer solution, else None."""
    if alpha == 0:
        return None
    D = 36 * n ** 3 - 19
    if D % alpha != 0:
        return None
    term = D // alpha
    disc = (alpha + 6 * n) ** 2 + term
    if disc < 0:
        return None
    is_sq, root = is_perfect_square(disc)
    if not is_sq:
        return None
    x = -alpha + root
    y = 2 * alpha + 6 * n
    z = -alpha - root
    if x ** 3 + y ** 3 + z ** 3 != 114:
        return None
    return (x, y, z, alpha, n)


# ════════════════════════════════════════════════════════════════════════
# Main finite worker
# ════════════════════════════════════════════════════════════════════════

MAX_DIVISORS = 20_000  # safety cap per n-value


def search_range(start, count):
    """Search n in [start, start+count) and their negatives. Return list of solutions."""
    solutions = []
    checked = 0
    end = start + count

    for n_val in range(start, end):
        if n_val == 0:
            continue
        for n in (n_val, -n_val):
            D = 36 * n ** 3 - 19
            if D == 0:
                continue

            # Quick alpha checks: ±1, ±D
            for alpha in (1, -1, D, -D):
                res = check_candidate(n, alpha)
                if res:
                    solutions.append(res)

            # Factor D and enumerate divisors
            try:
                factors = factor(D)
                divs = divisors_from_factors(factors)
                divs.sort()
            except Exception:
                divs = [1]

            tried = 0
            for d in divs:
                if d in (1, abs(D)):
                    continue
                if tried >= MAX_DIVISORS:
                    break
                for alpha in (d, -d):
                    res = check_candidate(n, alpha)
                    if res:
                        solutions.append(res)
                tried += 1

            checked += 1

    return solutions, checked


def write_results(start, count, solutions, checked, elapsed):
    """Write output files in CE output directory."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    result = {
        "problem": "x^3 + y^3 + z^3 = 114",
        "range_start": start,
        "range_end": start + count,
        "n_values_checked": checked,
        "elapsed_seconds": round(elapsed, 2),
        "rate_per_second": round(checked / max(elapsed, 0.001), 2),
        "solutions_found": len(solutions),
        "solutions": [],
    }

    for s in solutions:
        x, y, z, alpha, n = s
        result["solutions"].append({
            "x": x, "y": y, "z": z,
            "alpha": alpha, "n": n,
            "verification": x ** 3 + y ** 3 + z ** 3,
        })

    with open(os.path.join(OUTPUT_DIR, "result.json"), "w") as f:
        json.dump(result, f, indent=2)

    if solutions:
        with open(os.path.join(OUTPUT_DIR, "SOLUTION.txt"), "w") as f:
            f.write("=" * 60 + "\n")
            f.write("SOLUTION FOUND: x^3 + y^3 + z^3 = 114\n")
            f.write("=" * 60 + "\n\n")
            for s in solutions:
                x, y, z, alpha, n = s
                f.write(f"x = {x}\ny = {y}\nz = {z}\n")
                f.write(f"alpha = {alpha}, n = {n}\n")
                f.write(f"Verification: ({x})^3 + ({y})^3 + ({z})^3 = {x**3 + y**3 + z**3}\n\n")


def main():
    parser = argparse.ArgumentParser(
        description="Finite worker for x^3 + y^3 + z^3 = 114 (Charity Engine)"
    )
    parser.add_argument("--start", type=int, required=True,
                        help="First n value in this job's range")
    parser.add_argument("--count", type=int, required=True,
                        help="Number of n values to search")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED,
                        help="Random seed for Pollard-Rho (default: 42)")
    args = parser.parse_args()

    random.seed(args.seed + args.start)

    print(f"[worker] Searching n in [{args.start}, {args.start + args.count})")
    print(f"[worker] Output dir: {OUTPUT_DIR}")
    sys.stdout.flush()

    t0 = time.time()
    solutions, checked = search_range(args.start, args.count)
    elapsed = time.time() - t0

    write_results(args.start, args.count, solutions, checked, elapsed)

    print(f"[worker] Done. Checked {checked:,} n-values in {elapsed:.1f}s "
          f"({checked / max(elapsed, 0.001):.1f}/s)")
    if solutions:
        print(f"[worker] *** {len(solutions)} SOLUTION(S) FOUND ***")
    else:
        print(f"[worker] No solutions in this range.")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
