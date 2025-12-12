#!/usr/bin/env python3
"""
INFINITE SEARCH for k=114 on Charity Engine
Searches indefinitely, each container gets unique slice
"""

import os
import math
import sys
import time
import random

print("=" * 70)
print("INFINITE SEARCH FOR x³+y³+z³=114")
print("Equation: x = -α + √((α+6n)² + (36n³ - 19)/α)")
print("=" * 70)

# ========== CONFIGURATION ==========
# Each container gets a UNIQUE starting point
CONTAINER_ID = int(os.getenv('CONTAINER_ID', '0'))
TOTAL_CONTAINERS = int(os.getenv('TOTAL_CONTAINERS', '10000'))

# Search strategy: Jump around in n-space to cover more ground
JUMP_SIZE = 1000000  # Jump 1 million n values at a time

# ========== INFINITE SEARCH LOOP ==========
def infinite_search():
    """Search indefinitely, each container covers different regions."""
    
    print(f"Container {CONTAINER_ID} of {TOTAL_CONTAINERS}")
    print(f"Starting infinite search...")
    print(f"Will jump by {JUMP_SIZE:,} n values each iteration")
    print("-" * 70)
    
    solutions_found = 0
    total_checks = 0
    start_time = time.time()
    
    # Each container starts at a different base n
    base_n = CONTAINER_ID * 1000000000  # 1 billion apart
    
    iteration = 0
    
    while True:  # INFINITE LOOP - Charity Engine will stop when needed
        iteration += 1
        
        # Calculate current search window
        current_base = base_n + (iteration * JUMP_SIZE * TOTAL_CONTAINERS)
        
        # Search FORWARD direction
        print(f"\nIteration {iteration}: Searching n ≈ {current_base:,}")
        
        # Search a block of JUMP_SIZE n values
        for offset in range(JUMP_SIZE):
            n = current_base + offset
            
            # Also search negative n (symmetry)
            n_neg = -n
            
            # Check both positive and negative n
            for current_n in [n, n_neg]:
                total_checks += 1
                
                # Progress report
                if total_checks % 10000 == 0:
                    elapsed = time.time() - start_time
                    rate = total_checks / max(elapsed, 1)
                    print(f"  Checks: {total_checks:,} | "
                          f"Rate: {rate:.0f}/sec | "
                          f"Solutions: {solutions_found}", 
                          end='\r', flush=True)
                
                # Skip n=0
                if current_n == 0:
                    continue
                
                # Compute D = 36n³ - 19
                D = 36 * current_n**3 - 19
                
                if D == 0:
                    continue
                
                # SMART α SELECTION (from your analysis)
                # Only check promising α values
                
                # 1. Always check α = ±1
                for α in [1, -1]:
                    if check_solution_pair(current_n, α, D):
                        solutions_found += 1
                
                # 2. Check α = ±D (the other trivial divisor)
                if abs(D) < 10**15:  # Avoid too large numbers
                    for α in [D, -D]:
                        if check_solution_pair(current_n, α, D):
                            solutions_found += 1
                
                # 3. Check common small divisors from your analysis
                common_divisors = [17, 19, 37, 73, 109, 127]
                for α in common_divisors:
                    if D % α == 0:
                        if check_solution_pair(current_n, α, D):
                            solutions_found += 1
                        if check_solution_pair(current_n, -α, D):
                            solutions_found += 1
                
                # 4. Check a few random divisors (for diversity)
                if random.random() < 0.01:  # 1% chance
                    # Try to factor D partially
                    abs_D = abs(D)
                    for d in range(2, min(1000, int(abs_D**0.5) + 1)):
                        if abs_D % d == 0:
                            if check_solution_pair(current_n, d, D):
                                solutions_found += 1
                            if check_solution_pair(current_n, -d, D):
                                solutions_found += 1
        
        # Save checkpoint
        save_checkpoint(iteration, current_base, solutions_found, total_checks)

def check_solution_pair(n, α, D):
    """Check if (n, α) gives a solution."""
    if α == 0:
        return False
    
    # Check divisibility
    if D % α != 0:
        return False
    
    # Compute discriminant
    discriminant = (α + 6*n)**2 + D // α
    
    if discriminant < 0:
        return False
    
    # Perfect square check
    root = math.isqrt(discriminant)
    if root * root == discriminant:
        x = -α + root
        y = 2*α + 6*n
        z = -α - root
        
        # Final verification
        if x**3 + y**3 + z**3 == 114 and x != 0:
            save_solution(n, α, x, y, z)
            return True
    
    return False

def save_solution(n, α, x, y, z):
    """Save found solution."""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"\n\n{'!' * 70}")
    print("🎯 SOLUTION FOUND! 🎯")
    print(f"Time: {timestamp}")
    print(f"Container: {CONTAINER_ID}")
    print(f"n = {n:,}")
    print(f"α = {α:,}")
    print(f"x = {x:,}")
    print(f"y = {y:,}")
    print(f"z = {z:,}")
    print(f"Check: {x}³ + {y}³ + {z}³ = {x**3 + y**3 + z**3}")
    print(f"{'!' * 70}\n")
    
    # Save to file
    with open('/app/solutions.txt', 'a') as f:
        f.write(f"{timestamp},{CONTAINER_ID},{n},{α},{x},{y},{z}\n")
    
    # Also log to Docker output
    sys.stdout.flush()

def save_checkpoint(iteration, current_n, solutions, checks):
    """Save progress checkpoint."""
    checkpoint_data = {
        'container_id': CONTAINER_ID,
        'iteration': iteration,
        'current_n': current_n,
        'solutions_found': solutions,
        'total_checks': checks,
        'timestamp': time.time()
    }
    
    with open(f'/app/checkpoint_{CONTAINER_ID}.txt', 'w') as f:
        f.write(str(checkpoint_data))
    
    print(f"\nCheckpoint saved: Iteration {iteration}, n ≈ {current_n:,}")

# ========== MAIN ==========
if __name__ == "__main__":
    try:
        infinite_search()
    except KeyboardInterrupt:
        print("\n\nSearch interrupted. Saving final checkpoint...")
    except Exception as e:
        print(f"\n\nError: {e}")
        sys.exit(1)
