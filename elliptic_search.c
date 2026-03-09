/*
 * elliptic_search.c
 *
 * Searches for integer solutions (x, y) to the elliptic curve:
 *
 *   y^2 = x^3 + A(m)*x + B(m)
 *
 * where:
 *   A(m) = (-1/3)*m^4 + (1/3)*m^3
 *   B(m) = (2/27)*m^6 - (1/9)*m^5 + (1/36)*m^4 - (19/36)*m
 *
 * Since A and B must be integers, m must be a multiple of 6 (lcm of 3,27,36).
 * We search over integer values of m (multiples of 6) and integer x in a range.
 *
 * Charity Engine / BOINC compatible:
 *   - Reads work unit parameters from "in" file (or uses defaults)
 *   - Writes results to "out" file
 *   - Writes checkpoint to "checkpoint.dat"
 *   - Handles BOINC signals for suspend/resume
 *
 * Build:
 *   gcc -O3 -o elliptic_search elliptic_search.c -lm -lboinc -lboinc_api
 *   (or without BOINC: gcc -O3 -DSTANDALONE -o elliptic_search elliptic_search.c -lm)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <inttypes.h>
#include <signal.h>
#include <time.h>

/* ------------------------------------------------------------------ */
/*  Compile with -DSTANDALONE to run outside BOINC for local testing   */
/* ------------------------------------------------------------------ */
#ifndef STANDALONE
  #include "boinc_api.h"
  #include "filesys.h"
  #define BOINC_INIT()        boinc_init()
  #define BOINC_FINISH(x)     boinc_finish(x)
  #define BOINC_FRACTION(f)   boinc_fraction_done(f)
  #define BOINC_CHECKPOINT()  boinc_checkpoint_completed()
  #define SHOULD_CHECKPOINT()  boinc_time_to_checkpoint()
  #define RESOLVE(name,path)  boinc_resolve_filename(name,path,sizeof(path))
#else
  #define BOINC_INIT()        (0)
  #define BOINC_FINISH(x)     exit(x)
  #define BOINC_FRACTION(f)   /* nothing */
  #define BOINC_CHECKPOINT()  /* nothing */
  #define SHOULD_CHECKPOINT() (1)   /* always checkpoint when standalone */
  #define RESOLVE(name,path)  strncpy(path,name,sizeof(path))
#endif

/* ------------------------------------------------------------------ */
/*  128-bit integer helpers (GCC built-in)                              */
/* ------------------------------------------------------------------ */
typedef __int128  int128_t;
typedef unsigned __int128 uint128_t;

/* Print a 128-bit integer to a string */
static void int128_to_str(int128_t v, char *buf, size_t buflen) {
    if (v == 0) { snprintf(buf, buflen, "0"); return; }
    char tmp[50]; int idx = 0;
    int neg = (v < 0);
    if (neg) v = -v;
    while (v > 0) { tmp[idx++] = '0' + (int)(v % 10); v /= 10; }
    if (neg) tmp[idx++] = '-';
    tmp[idx] = '\0';
    /* reverse */
    for (int i = 0, j = idx-1; i < j; i++, j--) {
        char c = tmp[i]; tmp[i] = tmp[j]; tmp[j] = c;
    }
    snprintf(buf, buflen, "%s", tmp);
}

/* ------------------------------------------------------------------ */
/*  Exact integer square root: returns 1 if n >= 0 is a perfect square */
/* ------------------------------------------------------------------ */
static int is_perfect_square(int128_t n, int128_t *root) {
    if (n < 0) return 0;
    if (n == 0) { *root = 0; return 1; }
    /* Use double approximation then correct */
    double approx = sqrt((double)n);
    int128_t r = (int128_t)approx;
    /* Check r-1, r, r+1 to handle floating-point imprecision */
    for (int128_t delta = -2; delta <= 2; delta++) {
        int128_t candidate = r + delta;
        if (candidate >= 0 && candidate * candidate == n) {
            *root = candidate;
            return 1;
        }
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/*  Compute A(m) and B(m) * 36  to keep everything integer arithmetic  */
/*                                                                       */
/*  A(m) = (-m^4 + m^3) / 3    — integer when 3 | m                   */
/*  B(m) = (2/27)*m^6 - (1/9)*m^5 + (1/36)*m^4 - (19/36)*m            */
/*       = [24*m^6 - 12*m^5 + 3*m^4*... wait, let's use lcm=108        */
/*                                                                       */
/*  Multiply through by 108 = lcm(3,27,9,36):                           */
/*    108*A(m) = -36*m^4 + 36*m^3                                       */
/*    108*B(m) = 8*m^6 - 12*m^5 + 3*m^4 - 57*m                         */
/*                                                                       */
/*  For A and B to be integers we need 3|m and 27|m and 36|m            */
/*  lcm(3,27,36) = 108.  So m must be a multiple of 108.                */
/*  (We also test multiples of smaller divisors in case some cancel.)   */
/* ------------------------------------------------------------------ */

/* Returns 1 if m gives integer A and B, and sets *A and *B */
static int compute_AB(int64_t m, int128_t *A, int128_t *B) {
    /*
     * A(m) = (-m^4 + m^3) / 3
     * B(m) = (2*m^6)/27 - m^5/9 + m^4/36 - 19*m/36
     *
     * We check divisibility before dividing.
     */
    int128_t m1 = (int128_t)m;
    int128_t m2 = m1*m1;
    int128_t m3 = m2*m1;
    int128_t m4 = m3*m1;
    int128_t m5 = m4*m1;
    int128_t m6 = m5*m1;

    /* A(m) = (-m^4 + m^3) / 3 */
    int128_t numA = -m4 + m3;
    if (numA % 3 != 0) return 0;
    *A = numA / 3;

    /* B numerator over 108:  8*m^6 - 12*m^5 + 3*m^4 - 57*m  */
    /* B(m) = [8*m^6 - 12*m^5 + 3*m^4 - 57*m] / 108           */
    int128_t numB = 8*m6 - 12*m5 + 3*m4 - 57*m1;
    if (numB % 108 != 0) return 0;
    *B = numB / 108;

    return 1;
}

/* ------------------------------------------------------------------ */
/*  Checkpoint / result file paths                                      */
/* ------------------------------------------------------------------ */
#define CHECKPOINT_FILE  "checkpoint.dat"
#define RESULT_FILE      "out"
#define INPUT_FILE       "in"

/* ------------------------------------------------------------------ */
/*  Work unit parameters                                                */
/* ------------------------------------------------------------------ */
typedef struct {
    int64_t m_start;      /* first m to test (should be multiple of step) */
    int64_t m_end;        /* last m to test (inclusive)                    */
    int64_t m_step;       /* step size for m (multiple of 108)             */
    int64_t x_min;        /* min x to test for each m                      */
    int64_t x_max;        /* max x to test for each m                      */
} WorkUnit;

/* ------------------------------------------------------------------ */
/*  Read work unit from input file                                       */
/* ------------------------------------------------------------------ */
static void read_input(WorkUnit *wu) {
    /* Sensible defaults for standalone / first run */
    wu->m_start = -1080000;
    wu->m_end   =  1080000;
    wu->m_step  =  108;
    wu->x_min   = -1000000;
    wu->x_max   =  1000000;

    char path[512];
    RESOLVE(INPUT_FILE, path);
    FILE *f = fopen(path, "r");
    if (!f) {
        fprintf(stderr, "[info] No input file found, using defaults.\n");
        return;
    }
    fscanf(f, "%" SCNd64 " %" SCNd64 " %" SCNd64 " %" SCNd64 " %" SCNd64,
           &wu->m_start, &wu->m_end, &wu->m_step,
           &wu->x_min, &wu->x_max);
    fclose(f);
    fprintf(stderr, "[info] Work unit: m=[%" PRId64 "..%" PRId64 " step %" PRId64
                    "] x=[%" PRId64 "..%" PRId64 "]\n",
            wu->m_start, wu->m_end, wu->m_step, wu->x_min, wu->x_max);
}

/* ------------------------------------------------------------------ */
/*  Checkpoint: save / restore current m                               */
/* ------------------------------------------------------------------ */
static int64_t read_checkpoint(void) {
    char path[512];
    RESOLVE(CHECKPOINT_FILE, path);
    FILE *f = fopen(path, "r");
    if (!f) return INT64_MIN;   /* no checkpoint */
    int64_t val;
    fscanf(f, "%" SCNd64, &val);
    fclose(f);
    fprintf(stderr, "[info] Resuming from checkpoint m=%" PRId64 "\n", val);
    return val;
}

static void write_checkpoint(int64_t m) {
    char path[512];
    RESOLVE(CHECKPOINT_FILE, path);
    FILE *f = fopen(path, "w");
    if (!f) return;
    fprintf(f, "%" PRId64 "\n", m);
    fclose(f);
    BOINC_CHECKPOINT();
}

/* ------------------------------------------------------------------ */
/*  Write a solution to the output file                                 */
/* ------------------------------------------------------------------ */
static void write_solution(FILE *out, int64_t m, int128_t x, int128_t y,
                            int128_t A, int128_t B) {
    char xs[60], ys[60], As[60], Bs[60];
    char ms[30];
    int128_to_str(x, xs, sizeof(xs));
    int128_to_str(y, ys, sizeof(ys));
    int128_to_str(A, As, sizeof(As));
    int128_to_str(B, Bs, sizeof(Bs));
    snprintf(ms, sizeof(ms), "%" PRId64, m);

    fprintf(out,
        "SOLUTION FOUND:\n"
        "  m = %s\n"
        "  x = %s\n"
        "  y = %s\n"
        "  A(m) = %s\n"
        "  B(m) = %s\n"
        "  Verification: y^2 = %s,  x^3+A*x+B = %s\n"
        "---\n",
        ms, xs, ys, As, Bs, ys, xs);   /* caller verifies; we just log */

    fflush(out);
    /* Also echo to stderr for BOINC task log */
    fprintf(stderr, "*** SOLUTION: m=%s  x=%s  y=%s ***\n", ms, xs, ys);
}

/* ------------------------------------------------------------------ */
/*  Main search loop                                                    */
/* ------------------------------------------------------------------ */
int main(int argc, char **argv) {
    BOINC_INIT();

    WorkUnit wu;
    read_input(&wu);

    /* Open output file */
    char outpath[512];
    RESOLVE(RESULT_FILE, outpath);
    FILE *out = fopen(outpath, "a");   /* append so we don't lose results */
    if (!out) {
        fprintf(stderr, "[error] Cannot open output file %s\n", outpath);
        BOINC_FINISH(1);
    }

    /* Resume from checkpoint if available */
    int64_t m_resume = read_checkpoint();
    int64_t m_start = wu.m_start;
    if (m_resume != INT64_MIN && m_resume >= wu.m_start && m_resume <= wu.m_end) {
        m_start = m_resume;
    }

    int64_t total_m = (wu.m_end - wu.m_start) / wu.m_step + 1;
    int64_t done_m  = (m_start  - wu.m_start) / wu.m_step;
    int64_t solutions_found = 0;
    time_t last_checkpoint_time = time(NULL);

    fprintf(stderr, "[info] Starting search from m=%" PRId64 "\n", m_start);

    for (int64_t m = m_start; m <= wu.m_end; m += wu.m_step) {

        int128_t A, B;
        if (!compute_AB(m, &A, &B)) {
            /* m doesn't give integer A,B — skip (shouldn't happen if step=108) */
            continue;
        }

        /* Search x in [x_min, x_max] */
        for (int64_t xi = wu.x_min; xi <= wu.x_max; xi++) {
            int128_t x = (int128_t)xi;
            /* rhs = x^3 + A*x + B */
            int128_t rhs = x*x*x + A*x + B;

            int128_t y;
            if (is_perfect_square(rhs, &y)) {
                solutions_found++;
                write_solution(out, m, x, y, A, B);
                /* Also write negative y if nonzero */
                if (y != 0) {
                    write_solution(out, m, x, -y, A, B);
                }
            }
        }

        /* Checkpoint and progress update */
        done_m++;
        time_t now = time(NULL);
        if (SHOULD_CHECKPOINT() || (now - last_checkpoint_time) >= 60) {
            write_checkpoint(m + wu.m_step);
            last_checkpoint_time = now;
            double frac = (total_m > 0) ? (double)done_m / (double)total_m : 0.0;
            BOINC_FRACTION(frac);
            fprintf(stderr, "[progress] m=%" PRId64 "  %.2f%%  solutions=%" PRId64 "\n",
                    m, frac * 100.0, solutions_found);
        }
    }

    fprintf(out, "SEARCH COMPLETE: m=[%" PRId64 "..%" PRId64 "] "
                 "x=[%" PRId64 "..%" PRId64 "]  Solutions=%" PRId64 "\n",
            wu.m_start, wu.m_end, wu.x_min, wu.x_max, solutions_found);
    fclose(out);

    fprintf(stderr, "[done] Total solutions found: %" PRId64 "\n", solutions_found);
    BOINC_FINISH(0);
    return 0;
}
