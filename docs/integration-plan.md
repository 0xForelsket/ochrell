# Oil-paint integration plan (2026-09-30)

## Inspected baseline

Ochrell is a dependency-free Rust library, 41-band f32 K/S/residual and 81-band
f64 reference. README, changelog, architecture, math, coefficient provenance,
benchmarks, revision report, optical kernels and tests were read. All 23 tests
and the basic example pass on rustc 1.91.1, Windows x64. Neither checkout nor
their parents contain AGENTS.md. Ochrell is a source distribution without .git;
the renderer starts clean at f6c39db.

The renderer is Python/NumPy planning and CPU rasterization, not an interactive
GPU app. Production uses ctypes -> C; an existing Rust port has the same bristle
geometry, pickup, depletion, height and four modes. Python relights sRGB albedo
using height-derived normals, canvas weave, diffuse shading and gloss. Existing
latent interpolation uses alpha directly. Load/deplete and height are heuristic,
not conserved paint volume. Per-lane tips collect underlying states; canvas
planes are latent, RGB, height, wetness, accumulated coverage, blurred height
and region. Stroke serialization assumes seven floats; canvas snapshots use f16.
The existing Mixbox import is eager even for RGB. No C compiler is on PATH here.

## Implementation

1. Add checked K/S/residual import to Ochrell for array storage and bindings;
   retain private fields, zero runtime dependencies and all notices.
2. Add a small renderer-owned native crate using a local Ochrell dependency and
   the existing Rust bristle kernel. Gate additions so original C and Rust paths
   keep their behavior. Make Mixbox loading optional, without acquiring its data.
3. Expose `--mixer ochrell` through the existing Python planner/Canvas/CLI. Cache
   stroke states, retain f32 canvas states, add mixer-tagged exact snapshots.
4. Separate exposed material state and relative amount from coverage compositing
   (linear-light) and renderer height. Wetness selects accessible paint. Keep
   pickup/depletion as declared non-conserving transport approximations. Glaze
   composites RGB without claiming finite-thickness KM optics.
5. Use identical authored geometry, color inputs, seeds and brush parameters for
   persistent Ochrell, forced RGB round trips, and an sRGB control on the same
   transport. Check group weights, tints, black, repeated operations, smudging,
   snapshot/resume and all surface modes. Render a real existing scene too.
6. Record separate encode/mix/decode, coherent/scattered state access and brush
   replay/lighting timings, repetitions, seed, environment, memory and images.
   Start uncompressed; evaluate f16 storage against reference before making any
   compression claim. No speculative SIMD, GPU or WASM rewrite.
7. Document commands, measured costs, negative results, licenses and next step.

User extension: compare Mixbox mixing and rendering performance too. Use the
existing optional pymixbox 2.0.0 installation only in the renderer environment;
retain no proprietary artifacts in Ochrell. Report original and matched-transport
brush/scene timings, native cached kernels, actual Python adapter batches and
fresh-process memory. Compare one shared source-derived RGB stroke corpus without
replanning, and keep this separate from optical/reference correctness.

## Acceptance

Core tests and example still pass; native and Python integration tests pass;
existing surface geometry remains reproducible; scene CLI and exact resume run;
raw numerical/benchmark evidence and a viewable comparison are retained. The
old Mixbox-specific harness cannot establish Ochrell physical accuracy. No
paper quality claim changes without new supporting experiments.
