#!/usr/bin/env python3
"""
ENDLESS WORKER for x^3 + y^3 + z^3 = 114
- Deterministic partitioning across containers:
    n = BASE + k * TOTAL_CONTAINERS  (k = 0,1,2,...)
- Tests both sign(n) variants
- Uses Miller-Rabin + Pollard-Rho for factoring big D and enumerates divisors
- Writes solution immediately and checkpoints periodically
Author: adapted for Jamal Agbanwa
"""

import os
import sys
import time
import math
import json
import random
from collections import Counter

# ====== CONFIG ======
CONTAINER_ID = int(os.getenv("CONTAINER_ID", "0"))
TOTAL_CONTAINERS = int(os.getenv("TOTAL_CONTAINERS", "1000"))
CHECKPOINT_FILE = os.getenv("CHECKPOINT_FILE", f"checkpoint_{CONTAINER_ID}.json")
SOLUTIONS_FILE = os.getenv("SOLUTIONS_FILE", "/app/solutions.txt")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "5000"))   # save progress every N absolute-n steps
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))

# Set deterministic seed for Pollard-Rho attempts
random.seed(RANDOM_SEED + CONTAINER_ID)

# ====== Math helpers (Miller-Rabin & Pollard Rho) ======

def is_probable_prime(n, k=8):
    if n < 2:
        return False
    small_primes = [2,3,5,7,11,13,17,19,23,29]
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
    # random polynomial: f(x) = x^2 + c
    for attempt in range(6):
        x = random.randrange(2, n-1)
        y = x
        c = random.randrange(1, n-1)
        d = 1
        while d == 1:
            x = (x*x + c) % n
            y = (y*y + c) % n
            y = (y*y + c) % n
            d = math.gcd(abs(x-y), n)
            if d == n:
                break
        if 1 < d < n:
            return d
    return None

def factor(n):
    """Return prime factorization as Counter(p->exp). Works for n>0."""
    n = abs(n)
    if n == 1:
        return Counter()
    if is_probable_prime(n):
        return Counter([n])
    res = Counter()
    # trial divide small primes to speed up
    small_primes = [2,3,5,7,11,13,17,19,23,29,31,37,41,43,47,53,59,61]
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
            # fallback: try small trial divisions up to a limit
            limit = int(min(100000, math.isqrt(n)+1))
            found = False
            for i in range(2, limit):
                if n % i == 0:
                    res[i] += 1
                    n //= i
                    found = True
                    break
            if not found:
                # give up, treat remainder as prime-ish
                res[n] += 1
                break
        else:
            res += factor(d)
            n //= d
    return res

def divisors_from_factors(factors):
    """Given Counter of prime factors, return all divisors (positive)."""
    items = list(factors.items())
    if not items:
        return [1]
    def rec(i):
        if i == len(items):
            return [1]
        p, e = items[i]
        rest = rec(i+1)
        out = []
        pe = 1
        for _ in range(e+1):
            for r in rest:
                out.append(r * pe)
            pe *= p
        return out
    return rec(0)

# ====== Problem-specific helpers ======

def is_perfect_square(n):
    if n < 0:
        return False, 0
    r = math.isqrt(n)
    return (r*r == n, r)

def check_candidate(n, alpha):
    if alpha == 0:
        return None
    D = 36 * n**3 - 19
    if D % alpha != 0:
        return None
    term = D // alpha
    disc = (alpha + 6*n)**2 + term
    if disc < 0:
        return None
    is_sq, root = is_perfect_square(disc)
    if not is_sq:
        return None
    x = -alpha + root
    y = 2*alpha + 6*n
    z = -alpha - root
    if x**3 + y**3 + z**3 != 114:
        return None
    return (x, y, z, alpha, n)

# ====== Checkpoint utilities ======

def load_checkpoint():
    try:
        with open(CHECKPOINT_FILE, "r") as f:
            data = json.load(f)
            return data.get("k", 0)
    except Exception:
        return 0

def save_checkpoint(k):
    tmp = {"k": k, "timestamp": time.time(), "container_id": CONTAINER_ID}
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(tmp, f)

def save_solution_record(x, y, z, alpha, n):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp},container={CONTAINER_ID},n={n},alpha={alpha},x={x},y={y},z={z}\n"
    try:
        # Make directory if needed
        os.makedirs(os.path.dirname(SOLUTIONS_FILE), exist_ok=True)
    except Exception:
        pass
    with open(SOLUTIONS_FILE, "a") as f:
        f.write(line)
    print("\n" + "!"*60)
    print("SOLUTION FOUND")
    print(line.strip())
    print("!"*60 + "\n")
    sys.stdout.flush()

# ====== Main endless loop ======

def endless_worker():
    # deterministic arithmetic progression partition:
    # absolute-n sequence: for k=K0,1,2,...
    # evaluate n_pos = BASE + k * TOTAL_CONTAINERS   and n_neg = -n_pos
    # where BASE = CONTAINER_ID
    base = CONTAINER_ID
    k = load_checkpoint()
    steps_since_save = 0
    checked = 0
    start_time = time.time()

    print(f"Container {CONTAINER_ID}/{TOTAL_CONTAINERS}. Resuming k={k}.")
    print("Iterating n = base + k * TOTAL_CONTAINERS (and negative) forever.")

    while True:
        try:
            n_candidate = base + k * TOTAL_CONTAINERS
            # skip n=0 if it occurs
            if n_candidate != 0:
                for n in (n_candidate, -n_candidate):
                    # compute D
                    D = 36 * n**3 - 19
                    if D == 0:
                        continue

                    # alpha candidates: ±1, ±D, divisors of D
                    # first quick checks ±1
                    for alpha in (1, -1):
                        res = check_candidate(n, alpha)
                        if res:
                            x,y,z,alpha_v,n_v = res
                            save_solution_record(x,y,z,alpha_v,n_v)
                    # check ±D (fast, but D might be huge)
                    # to avoid huge memory/time, only test ±D if abs(D) fits in python int (it does),
                    # testing divisibility is trivial (D % D == 0)
                    for alpha in (D, -D):
                        res = check_candidate(n, alpha)
                        if res:
                            x,y,z,alpha_v,n_v = res
                            save_solution_record(x,y,z,alpha_v,n_v)

                    # Factor D and enumerate divisors (but limit divisor count)
                    try:
                        factors = factor(D)
                        divs = divisors_from_factors(factors)
                        # optionally sort small-to-large so cheap alphas checked first
                        divs.sort()
                    except Exception:
                        divs = [1]  # fallback to minimal set

                    # iterate divisors but skip ±1 and ±D duplicates
                    max_divisors_to_try = 20000  # safety cap
                    tried = 0
                    for d in divs:
                        if d in (1, abs(D)):
                            continue
                        if tried >= max_divisors_to_try:
                            break
                        for alpha in (d, -d):
                            res = check_candidate(n, alpha)
                            if res:
                                x,y,z,alpha_v,n_v = res
                                save_solution_record(x,y,z,alpha_v,n_v)
                        tried += 1

                    checked += 1

            # progress bookkeeping
            k += 1
            steps_since_save += 1

            if steps_since_save >= CHECK_INTERVAL:
                save_checkpoint(k)
                steps_since_save = 0
                elapsed = time.time() - start_time
                rate = (k+1) / max(elapsed, 1.0)
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] k={k:,} | checked≈{checked:,} | rate≈{rate:.2f}/s")
                # flush
                sys.stdout.flush()

        except KeyboardInterrupt:
            print("Interrupted by user; saving checkpoint and exiting.")
            save_checkpoint(k)
            raise
        except Exception as e:
            # log and continue -- don't die on one bad n
            print(f"Error at k={k}: {e}", file=sys.stderr)
            k += 1
            steps_since_save += 1
            if steps_since_save >= CHECK_INTERVAL:
                save_checkpoint(k)
                steps_since_save = 0

if __name__ == "__main__":
    endless_worker()
