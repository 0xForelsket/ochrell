# Frozen empirical pair-interaction experiment

Declared before real fitting, 2026-09-30. Exploratory: all assessment data were
previously exposed. No paper-faithful or measured physical K/S claim is made.

For normalized nonnegative mass recipe c, fit unchanged v3 KM using its original
settings and three starts, selected by training objective only. Freeze this base.
Then R = sigmoid(logit(R_KM) + sum(i<j) 4 c_i c_j sum(k=0..3) B_k(t) theta_ijk),
where t=(nm-400)/300 and B is cubic Bernstein. Four controls per six pairs,
24 empirical parameters, each bounded [-0.8,0.8]. Minimize mean squared spectral
error plus 1e-4 mean(theta_active squared), analytic Jacobian, one zero start,
TRF, max_nfev=2000, ftol=xtol=gtol=1e-10. No diagnostic ablation.

Every pair absent from that fit's recipe array is fixed to zero (not inferred
from other pairs or withheld targets). Therefore each withheld chromatic pair
uses solely its fold's KM prediction. Fit interfaces receive training arrays only.
Fit 29/assess 16 and three complete-family exclusions per shared README.
No new model or setting will be tried after evaluation. Stop on convergence
failure and retain failure metadata. No scores choose a candidate or start.

Pure endpoints are unchanged since all pair products vanish. Bernstein curves
are convex combinations of bounded controls; sum 4c_i c_j <=1.5, so the logit
shift is bounded by 1.2 for every simplex recipe. Reflectance remains in (0,1)
without post-prediction clipping. Endpoint KM values are retained exactly when
the shift is zero. The model may leave the pure ingredient envelope; this is
declared empirical behavior. No extrapolation beyond 400-700 nm is defined.

Numerical tests: analytic derivatives, scalar forward agreement, synthetic
parameter recovery, exact pure endpoints, zero correction reduction, random
and boundary recipes at extreme controls, mass scaling, invalid recipes,
whole-family exclusion and withheld target perturbation invariance. Report v1
and v3 reproduction, all spectral/color summaries, family errors and regressions,
pure drift, complexity, bound hits and timing. Raw coefficients stay ignored.
