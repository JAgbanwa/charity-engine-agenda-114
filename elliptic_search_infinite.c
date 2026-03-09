/*
 * elliptic_search_infinite.c
 *
 * Standalone version that NEVER STOPS — it keeps expanding the search
 * range of m and x until a solution is found (or you kill it).
 *
 * Strategy:
 *   Round 0:  m in [-108, 108],          x in [-1000, 1000]
 *   Round 1:  m in [-10800, 10800],       x in [-100000, 100000]
 *   Round r:  m in [-108*10^r, 108*10^r], x in [-10^(3+r), 10^(3+r)]
 *
 * Compile (standalone, no BOINC):
 *   gcc -O3 -o elliptic_search_infinite elliptic_search_infinite.c -lm
 *
 * On Charity Engine (BOINC) — use elliptic_search.c with work units instead.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <inttypes.h>
#include <signal.h>
#include <time.h>

typedef __int128  int128_t;

/* ---- helpers ---- */
static void int128_to_str(int128_t v, char *buf, size_t buflen) {
    if (v == 0) { snprintf(buf, buflen, "0"); return; }
    char tmp[50]; int idx = 0;
    int neg = (v < 0); if (neg) v = -v;
    while (v > 0) { tmp[idx++] = '0' + (int)(v % 10); v /= 10; }
    if (neg) tmp[idx++] = '-';
    tmp[idx] = '\0';
    for (int i = 0, j = idx-1; i < j; i++, j--) { char c=tmp[i]; tmp[i]=tmp[j]; tmp[j]=c; }
    snprintf(buf, buflen, "%s", tmp);
}

static int is_perfect_square(int128_t n, int128_t *root) {
    if (n < 0) return 0;
    if (n == 0) { *root = 0; return 1; }
    double approx = sqrtl((long double)n);
    int128_t r = (int128_t)approx;
    for (int128_t d = -3; d <= 3; d++) {
        int128_t c = r + d;
        if (c >= 0 && c * c == n) { *root = c; return 1; }
    }
    return 0;
}

static int compute_AB(int64_t m, int128_t *A, int128_t *B) {
    int128_t m1 = (int128_t)m;
    int128_t m2 = m1*m1, m3 = m2*m1, m4 = m3*m1, m5 = m4*m1, m6 = m5*m1;
    int128_t numA = -m4 + m3;
    if (numA % 3 != 0) return 0;
    *A = numA / 3;
    int128_t numB = 8*m6 - 12*m5 + 3*m4 - 57*m1;
    if (numB % 108 != 0) return 0;
    *B = numB / 108;
    return 1;
}

/* ---- volatile flag for Ctrl-C ---- */
static volatile int keep_running = 1;
void handle_sigint(int sig) { keep_running = 0; (void)sig; }

int main(void) {
    signal(SIGINT,  handle_sigint);
    signal(SIGTERM, handle_sigint);

    FILE *log = fopen("solutions.txt", "a");
    if (!log) { perror("fopen solutions.txt"); return 1; }
    fprintf(log, "=== Search started ===\n"); fflush(log);

    int64_t total_solutions = 0;
    int round = 0;

    printf("Elliptic curve integer solution search\n");
    printf("y^2 = x^3 + A(m)*x + B(m)\n");
    printf("Press Ctrl-C to stop gracefully.\n\n");

    while (keep_running) {
        /* Expand search bounds each round */
        int64_t m_lim, x_lim;

        if (round == 0) {
            m_lim = 108;
            x_lim = 1000;
        } else {
            /* multiply by 10 each round */
            m_lim = 108;
            for (int i = 0; i < round; i++) m_lim *= 10;
            x_lim = 1000;
            for (int i = 0; i < round; i++) x_lim *= 10;
            /* cap to avoid overflow with 128-bit arithmetic */
            if (m_lim > 1000000000LL) m_lim = 1000000000LL;
            if (x_lim > 100000000000LL) x_lim = 100000000000LL;
        }

        printf("[Round %d] m in [-%" PRId64 ", %" PRId64 "], "
               "x in [-%" PRId64 ", %" PRId64 "]\n",
               round, m_lim, m_lim, x_lim, x_lim);

        int64_t m_step = 108;   /* smallest m giving integer A,B */
        int64_t m_count = 0;
        time_t t0 = time(NULL);

        for (int64_t m = -m_lim; m <= m_lim && keep_running; m += m_step) {
            int128_t A, B;
            if (!compute_AB(m, &A, &B)) continue;

            for (int64_t xi = -x_lim; xi <= x_lim; xi++) {
                int128_t x = (int128_t)xi;
                int128_t rhs = x*x*x + A*x + B;
                int128_t y;
                if (is_perfect_square(rhs, &y)) {
                    char xs[60], ys[60], As[60], Bs[60];
                    int128_to_str(x, xs, sizeof(xs));
                    int128_to_str(y, ys, sizeof(ys));
                    int128_to_str(A, As, sizeof(As));
                    int128_to_str(B, Bs, sizeof(Bs));
                    printf("\n*** SOLUTION ***  m=%" PRId64 "  x=%s  y=%s\n\n", m, xs, ys);
                    fprintf(log,
                        "SOLUTION: m=%" PRId64 "  x=%s  y=%s  A=%s  B=%s\n",
                        m, xs, ys, As, Bs);
                    if (y != 0) {
                        int128_to_str(-y, ys, sizeof(ys));
                        fprintf(log,
                            "SOLUTION: m=%" PRId64 "  x=%s  y=%s  A=%s  B=%s\n",
                            m, xs, ys, As, Bs);
                    }
                    fflush(log);
                    total_solutions++;
                }
            }

            m_count++;
            if (m_count % 1000 == 0) {
                time_t elapsed = time(NULL) - t0;
                double pct = 100.0 * (double)(m + m_lim) / (double)(2*m_lim);
                printf("\r  %.1f%% (m=%" PRId64 ", elapsed %lds, "
                       "solutions so far: %" PRId64 ")     ",
                       pct, m, (long)elapsed, total_solutions);
                fflush(stdout);
            }
        }

        printf("\n[Round %d done] Total solutions so far: %" PRId64 "\n\n",
               round, total_solutions);
        round++;

        /* If we've hit max bounds, just keep repeating the last round */
        if (m_lim >= 1000000000LL && x_lim >= 100000000000LL) {
            printf("Max range reached. Continuing at maximum bounds...\n");
            /* stay at round that gives max bounds */
            round--;
        }
    }

    printf("\nSearch stopped. Total solutions found: %" PRId64 "\n", total_solutions);
    fprintf(log, "=== Search stopped. Total solutions: %" PRId64 " ===\n", total_solutions);
    fclose(log);
    return 0;
}
