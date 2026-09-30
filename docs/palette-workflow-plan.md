# Target matching, custom palettes and native renderer integration

Starting checkpoint: `b2fd85e`. Implement the three requested capabilities as an
opt-in workflow. Preserve the current RGB mixer, OPR1 recipes and OPL1 tables.
Do not change the renderer's active brush/transport edits or its default mixer.

1. Load owned four-material palettes with checked finite optical coefficients,
   names, source description, amount convention and an explicit spectral grid.
   Start with the existing 81-band CIE/D65 reference convention; reject other
   grids rather than padding measurements. Content identity must cover numerical
   values and metadata. Built-in recipes retain their existing fingerprint.
2. Find a recipe for a requested display color using a deterministic bounded
   multistart search. Report the achieved color and OKLab distance, never add a
   residual to manufacture an exact match. Unreachable colors are valid results
   with nonzero error. Similar-color recipes use a stable search/tie order; no
   unique inverse or globally optimal solution is promised.
3. Integrate four-component paint recipes with the existing renderer kernel.
   Use its portable gamma/cube-root conventions, explicit palette identity and
   prepared decoder. Provide code-driven target matching and explicit loads,
   and a versioned replay artifact retaining the actual palette and recipes.
   Native end-to-end replay is the first integration acceptance; browser/TS
   exposure and default promotion require their own evidence.

Palette packages and LUTs must reject corrupt, incompatible and nonfinite data.
Test same-named palettes with different coefficients and independently loaded
equivalent copies. Keep the core dependency-free, safe Rust and compatible with
Rust 1.75. Verify existing tests and retain the measured Old Holland split/data
boundary. Renderer dependency pins must point at a clean committed Ochrell state.

Matching acceptance: pure paints recover their displayed colors, a separately
seeded corpus of reachable targets has maximum OKLab*100 error <=0.10, and
unreachable targets return honest finite errors with valid recipes. Repeated
calls are deterministic on a given arithmetic implementation. Include corner,
white/dark, boundary, serialized and custom-palette cases. Record evaluation
counts and elapsed time separately from painting; this is a color-authoring
operation, not something to run per covered pixel.
