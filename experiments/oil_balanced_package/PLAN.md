# Package the balanced Old Holland Eight candidate and compare painting workflows

2026-10-01. Product verification after the completed fixed-weight calibration
study; no new fitting rule, parameter sweep or validation claim is introduced.

Fit one final model on all 286 measured recipes with the unchanged balanced
fitter and settings. Preserve the 8 measured pure endpoints and the four
nonpure categories' equal total weight. Freeze the model and source/method
hashes. The 107-family exclusion report remains the predictive accuracy evidence;
any full-data residuals are calibration diagnostics only.

Export uniquely identified native 31-band OPP3 K-M and corrected packages with
explicit full-data/balanced provenance. Preserve the prior 103-row packages.
Verify Python/scalar and Rust predictions on pures, all measured recipes, all
pair ramps, near-pure boundaries and dense all-eight mixtures. Check byte-exact
package/recipe round trips and future mixing after recipe restoration.

Compare the prior corrected package and final balanced corrected package using
identical authored amounts, targets, stroke geometry and renderer settings:

- A recipe sheet covering all pures, dark/chromatic mixtures, neutrals, white
  tints, saturated pairs and mixtures with all eight paints. Same loads isolate
  optical changes; all material and transport planes should agree between models.
- Target-matched strokes with fixed RGB targets covering black/near-black,
  neutral grays, saturated colors and pastels. Report achieved colors, recipes,
  residual errors and authoring time. Do not assert a certified optimal inverse.
- Existing 94-stroke renderer fixture for overlap, pickup, drying, smudging and
  related modes. This exercises software behavior, not physical glaze validation.
- Save/read/repaint each job, require exact bytes and every canvas plane on this
  host; verify valid persistent eight-material states and future mixing.
- Warmed, alternating repeated direct-decode and full-paint timings on the same
  executable and corpus. Retain every timing. Separate cold preparation, target
  matching and painting. Host variation is a limitation, not an accuracy result.

Review visual comparisons and recommend whether balanced should be the preferred
local measured package. Do not infer greater physical accuracy from attractive
rendering or reduced RGB-target error. Keep the old package available and the
global/synthetic default separate.

LUT scope: the current dense decoder is four-paint/81-band only. Eight-paint
recipes have seven independent coordinates. Calculate storage scaling and
measure the direct runtime first. Do not silently reduce mixtures to four paints
or replace material state with RGB. A general large-palette accelerator is a
separate engineering step; document suitable next directions and distinguish
RGB-to-recipe authoring lookup from recipe-to-display acceleration.

Measurements, optical coefficients, local packages, rendered previews and saved
paintings remain under ignored target/. Commit original scripts, numerical
verification, timing records and the report. No source-data redistribution or
push is part of this step.
