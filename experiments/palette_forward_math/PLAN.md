# One forward-decoder engineering pass

2026-10-01. Keep the frozen balanced Old Holland Eight optics, fitting evidence,
material proportions and exact reference decoder. Optimize only recipe-to-display
evaluation. Do not silently change old saved-job decoding or current defaults.

## Algebraic candidate

The current empirical correction is sigmoid(log(r)-log1p(-r)+shift). Evaluate
the equivalent r / (r + (1-r)*exp(-shift)), keeping exact endpoint/zero-shift
branches. Retain the same normalized amounts, K/S sums, K-M inverse, pair-control
sum and RGB projection. Prepare the four Bernstein values per band once.
Use the renderer's deterministic oil-math exponential. This is equivalent real
arithmetic but is not promised bit-identical floating-point evaluation.

Screen before changing production behavior. Require pure endpoints unchanged;
finite bounded spectra; maximum absolute spectral and raw-linear RGB difference
<=2e-12 against the reference; displayed OKLab*100 error <=0.001. Test all pures,
all pairs, white tints, dark recipes, tiny components, sparse faces, dense recipes
and actual material states from rendered jobs. Include 1/4/8/10/16-paint synthetic
controls and both 31/81 bands to verify the generalized API and extreme optics.

## Conditional compact lookup

If the algebraic screen passes but decoding still has a material cost, test one
fixed 513-node f64 exp table spanning [-1.6,1.6], with linear interpolation.
This table approximates exp(-shift), not a seven-dimensional paint-recipe grid.
For valid controls bounded by 0.8 and normalized nonnegative c,
|shift| <= 0.8*sum(i<j,4*c_i*c_j) <= 1.6*(1-1/N) <=1.5 for N<=16.
The extra interval margin accommodates floating-point normalization. Fail or
fall back to the algebraic exponential outside the supported interval; never
index/clamp an out-of-range shift as if it were a valid table query.

Use the same zero-shift/pure branches. Predeclare maximum absolute reflectance
error <=1e-5, raw-linear RGB <=2e-5, displayed channel error <=1e-4 and displayed
OKLab*100 error <=0.01 on the full screen. Retain group mean/p95/max and all
failures. Require at least a 10% decode-median gain over algebraic, then check
full painting. Keep algebraic if the added approximation buys too little speed.
There is no table-resolution sweep in this pass.

## Performance and product checks

Use the same release executable and rotating mode order, one warmup and five
measured decode rounds on a fixed recipe corpus. If selected, repeat the three
saved eight-paint jobs at 512/1024/2048 widths using paint_final and three measured
rounds after warmup. Separate preparation, matching, paint, validation and hashing.
Report added decoder storage, source/recipe hashes and timing ranges.

Persistent material/height/wetness/coverage/blurred-height planes and transport
statistics must stay byte-identical. Quantify RGB differences rather than
assuming equivalent formulas guarantee equal bits. Preserve reference authoring
inputs for streak generation so display selection does not perturb recipes.
Record an explicit versioned decoder choice in new saved jobs; old reference and
prepared-four artifacts retain their meaning and bytes. Test malformed decoder
tags, cache invalidation, actual achieved-color reports and selected-decoder
save/load replay. Keep old native golden cases unchanged. No global engine/model
default switch or fitted-model change is part of this work.

Raw measured models, recipes/frames derived from them and saved jobs stay under
ignored target/. Commit implementation, tests, original numerical reports and
scripts. No push or external publication is requested.
