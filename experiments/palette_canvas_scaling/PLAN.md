# Profile realistic canvas sizes before selecting a forward accelerator

2026-10-01. Use the frozen balanced Old Holland Eight package and three saved
jobs from the package comparison: fixed recipes (96 strokes), matched targets
(96 strokes), and the renderer fixture (94 strokes, eight layers). No fitting,
RGB authoring or inverse matching belongs in the painting timings.

Measure widths 512, 1024 and 2048 at the existing 4:5 aspect. Retain one warmup
and three measured repetitions per mode, rotating mode order. Report wall-time
medians/ranges and accounted canvas-buffer bytes, plus a source-based estimate
of temporary blur storage. Distinguish allocated canvas storage from process
memory; do not call it a whole-process peak without measuring one.

Profile with two equivalent transport runs: the direct spectral decoder and a
diagnostic RGB bypass. Bypass returns a fixed display value but keeps all brush,
material, height, wetness and coverage operations. Verify non-RGB planes and
statistics agree exactly; never expose bypass output as a usable painting.
Verify the profiling harness's direct output against the public paint API at
each scene/size. Record decode calls/deposits, unique pixels with deposits and
height-blur time. Timing subtraction estimates removable display cost, not an
independent instruction-level profiler. It retains RGB writes and material work.

If decoding dominates, first test exact deferred display: the kernel writes
material proportions without spectral evaluation; once transport finishes,
decode each pixel with positive deposited coverage once. RGB is not read by
brush transport in this implementation. Preserve all material/state arithmetic,
the same direct model and exact RGB for untouched ground. Compare final pixels,
all canvas planes, statistics, save/load replay and timing against the ordinary
path. This avoids intermediate calculations and does not approximate the optics.

Keep the callback paint API's observable previews unchanged. Any final-only
optimization must be explicit, preserve saved formats and fall back to the exact
model. If the proposed deferred strategy fails correctness or speed checks,
report that result and use the measured bottleneck to decide another approach.
Do not invent a dense high-dimensional LUT or silently reduce paint counts.

Keep source-derived OPJ/package/image files under ignored target/. Commit the
original profiler/implementation/tests, numerical evidence and report. No global
paint-model change, physical accuracy claim or push is part of this step.
