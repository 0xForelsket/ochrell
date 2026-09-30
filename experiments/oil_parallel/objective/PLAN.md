# Frozen objective experiment

Before fitting, declare exactly one candidate and no ablation. Preserve fixed
pure homogeneous opaque K-M, recorded mass recipes, white S=1, and 93 log-S
parameters. Objective = 0.5 mean(Rpred-Robs)^2 +
0.5 (0.02/3)^2 mean(||Labpred-Labobs||^2), plus unchanged v1 curvature and
amplitude penalties. The mean Lab norm is across rows (not channels).
Equal weights at the existing engineering screen magnitudes give color visible
importance while retaining spectral information. DE76 is only a smooth fitting
surrogate: evaluate with original DE00 and disclose spectral tradeoffs.

Use unchanged v1 starts 0, ln(0.1), ln(10), bounds, tolerances and maximum 2000
evaluations. Select successful start by training objective alone. Fit primary29
and complete Y+R, Y+B, R+B family exclusions before evaluation. No multicolor
assessment enters fitting; all assessments remain previously exposed exploratory
data. Compare frozen v1 and frozen v3 on identical rows. No evaluation-driven
weight changes, additional candidates or row exclusions.

Before real fitting verify analytic hybrid Jacobian by central differences,
Lab parity with the existing colour implementation including its linear branch,
synthetic noiseless recovery, v1 baseline metric reproduction, and v3 score
reproduction. Freeze config, plan, implementation and shared dependency hashes.
Save coefficients only in ignored target output. Publish scalar summary and
per-row errors, family/tail/regression statistics, optimizer outcomes and costs.
