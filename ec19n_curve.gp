/* ================================================================
 * ec19n_curve.gp  —  PARI/GP provably-complete integer-point search
 *
 * Target equation (original form):
 *   y² = x³ + 1296·n²·x² + 15552·n³·x + (46656·n⁴ − 19·n)
 *
 * Short Weierstrass reduction  (X = x + 432·n²):
 *   y² = X³ + A(n)·X + B(n)
 *
 *   A(n) = 15552·n³ − 559872·n⁴
 *   B(n) = 161243136·n⁶ − 6718464·n⁵ + 46656·n⁴ − 19·n
 *
 *   x = X − 432·n²
 *
 * Algorithm: PARI/GP ellintegralpoints() — Tzanakis–de Weger
 *   (provably complete: no integer points can be missed)
 *
 * Invocation:
 *   Called inline from ec19n_worker.py via subprocess (no file I/O).
 *
 * Output tokens parsed by Python:
 *   SOLUTION: n=<n> x=<x> y=<y>
 *   SINGULAR: n=<n>
 *   DEGENERATE: n=<n>   (disc=0, special handling done in Python)
 *   RANK: n=<n> rank=<r>
 *   NOINT: n=<n>
 *   DONE: n=<n>
 * ================================================================ */

{
  /* Check if a PARI object is a rational integer */
  isint(v) = (type(v) == "t_INT");
}

/* ── A(n) and B(n) ─────────────────────────────────────────── */
{
  ec19n_A(n) =
    15552*n^3 - 559872*n^4;
}

{
  ec19n_B(n) =
    161243136*n^6 - 6718464*n^5 + 46656*n^4 - 19*n;
}

/* ── Main search for a single n value ─────────────────────── */
{
  search_n(N) =
  local(n, A, B, E, pts, rk, P, X_val, y_val, x_val, lhs, rhs);

  n = N;

  /* n=0: y^2 = x^3  (discriminant=0, infinitely many trivial sols) */
  if (n == 0,
    printf("DEGENERATE: n=0 (y^2=x^3, trivial solutions x=t^2 y=t^3)\n");
    printf("DONE: n=0\n");
    return(0);
  );

  A = ec19n_A(n);
  B = ec19n_B(n);

  /* Construct short Weierstrass model [a1, a2, a3, a4, a6] */
  E = ellinit([0, 0, 0, A, B]);

  /* Check for singularity */
  if (E.disc == 0,
    printf("SINGULAR: n=%d  A=%d  B=%d\n", n, A, B);
    printf("DONE: n=%d\n", n);
    return(0);
  );

  /* Analytic rank (fast estimate, helps PARI internals) */
  rk = ellanalyticrank(E);
  printf("RANK: n=%d rank=%d\n", n, rk[1]);

  /* ── Provably complete integral-point search ──────────────
   * flag=1  → ellintegralpoints returns BOTH  (X,y) and (X,-y)
   * This implements the full Tzanakis–de Weger algorithm:
   *   1. Mordell-Weil group computation (2-descent)
   *   2. Baker–Wüstholz height bound
   *   3. LLL lattice reduction to enumerate candidates
   *   4. Final check of each candidate
   * ─────────────────────────────────────────────────────── */
  pts = ellintegralpoints(E, 1);

  if (#pts == 0,
    printf("NOINT: n=%d\n", n);
    printf("DONE: n=%d\n", n);
    return(0);
  );

  for (i = 1, #pts,
    P     = pts[i];
    X_val = P[1];
    y_val = P[2];

    /* Must be integers (ellintegralpoints should guarantee this) */
    if (!isint(X_val) || !isint(y_val), next());

    /* Transform back: x = X − 432·n²  */
    x_val = X_val - 432*n^2;

    /* Double-check in original equation */
    lhs = y_val^2;
    rhs = x_val^3 + 1296*n^2*x_val^2 + 15552*n^3*x_val + 46656*n^4 - 19*n;
    if (lhs != rhs,
      printf("VERIFY_FAIL: n=%d X=%d x=%d y=%d lhs=%d rhs=%d\n",
             n, X_val, x_val, y_val, lhs, rhs);
      next()
    );

    printf("SOLUTION: n=%d x=%d y=%d\n", n, x_val, y_val);
  );

  printf("DONE: n=%d\n", n);
  return(#pts);
}
