#!/usr/bin/env python3
"""
wu_generator.py — Work Unit generator for the elliptic curve search project.

Run on the Charity Engine / BOINC server to create work units.
Each work unit covers a slice of m values (multiples of 108) and a fixed x range.

Usage:
    python3 wu_generator.py [--m-total 10000000] [--x-range 5000000] \
                            [--wu-size 100000] [--output-dir ./wu_inputs]

    --m-total   Total symmetric range of m (default: 10,000,000)
                Search covers m in [-m_total, +m_total] stepping by 108
    --x-range   x search range per m (default: 5,000,000)
                Search covers x in [-x_range, +x_range]
    --wu-size   Number of m-steps per work unit (default: 10,000)
    --output-dir Directory to write input files into
"""

import argparse
import os
import math

def main():
    parser = argparse.ArgumentParser(description="Generate BOINC work units for elliptic curve search")
    parser.add_argument("--m-total",   type=int, default=10_000_000,
                        help="Search m in [-m_total, m_total]")
    parser.add_argument("--x-range",   type=int, default=5_000_000,
                        help="Search x in [-x_range, x_range] for each m")
    parser.add_argument("--wu-size",   type=int, default=10_000,
                        help="Number of m-steps per work unit")
    parser.add_argument("--output-dir",type=str, default="wu_inputs",
                        help="Directory to write work unit input files")
    args = parser.parse_args()

    M_STEP = 108          # lcm(3, 27, 36) = 108; only multiples give integer A,B
    m_total = args.m_total
    x_range = args.x_range
    wu_size = args.wu_size
    out_dir = args.output_dir

    # Round m_total to nearest multiple of 108
    m_total = (m_total // M_STEP) * M_STEP

    os.makedirs(out_dir, exist_ok=True)

    wu_count = 0
    m = -m_total
    while m <= m_total:
        m_start = m
        m_end   = min(m + (wu_size - 1) * M_STEP, m_total)
        fname   = os.path.join(out_dir, f"wu_{wu_count:08d}.txt")
        with open(fname, "w") as f:
            # Format: m_start m_end m_step x_min x_max
            f.write(f"{m_start} {m_end} {M_STEP} {-x_range} {x_range}\n")
        wu_count += 1
        m = m_end + M_STEP

    print(f"Generated {wu_count} work units in '{out_dir}'")
    print(f"m range: [{-m_total}, {m_total}] step {M_STEP}")
    print(f"x range: [{-x_range}, {x_range}]")
    total_m_values = 2 * (m_total // M_STEP) + 1
    total_x_values = 2 * x_range + 1
    ops = total_m_values * total_x_values
    print(f"Total (m,x) pairs to test: ~{ops:,}")

if __name__ == "__main__":
    main()
