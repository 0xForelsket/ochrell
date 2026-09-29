# Ochrell hill climbing

Baseline: `17531c6` (v0.2 model plus checked component import and integration
evidence). Renderer checkpoint: `7fa7844`; renderer development is separate.

## Round 1: preserve the model, reduce CPU cost

Hold coefficients, wavelength grids, residual, gamut mapping, state size and
public behavior fixed. First investigate loop structure and cross-crate inlining.
The decoder's per-band division/square-root work is interleaved with ordered
RGB accumulation. Separating independent optics from the reduction may let the
compiler schedule/vectorize the independent work without changing the reduction
order. The same experiment applies to encoding.

Candidates: baseline, decoder inlining, all hot-path inlining, separate decoder
optics, separate encoder optics, both separated, separated plus inlining, and an
algebraic one-division decoder. The latter is deliberately tested on extreme
valid imported states as well as ordinary paint: an algebraic identity is not a
floating-point equivalence or a license to narrow the component-import contract.

Acceptance is declared before timing:

- All existing release tests pass.
- Exact state fingerprints and RGB output bits match the frozen baseline on
  deterministic reconstruction, mixtures, white/black addition, weighted and
  grouped states, repeated updates, tiny pickups, and valid imported extremes.
- Fast/reference errors are recorded, but this round accepts no changed output
  merely because its error seems visually small.
- Improved throughput must survive alternating baseline/candidate execution;
  retain raw repetitions, losing candidates, compiler/CPU settings and source
  hashes. Do not compare timings taken in different sessions as proof of a win.
- No runtime dependency, unsafe code, ISA-specific intrinsic, coefficient or
  renderer change. Compiler auto-vectorization of portable Rust is permitted.

Selection uses seed 20260930. A separately seeded holdout (1907) is evaluated
after selection. Benchmark seeds/order, iterations and CPU affinity are explicit.
Temporary candidate edits and executables stay in ignored `target/hillclimb`;
the runner restores the original source even on failure. Evidence is stored in
`results/optimization/round1`, distinct from the frozen integration measurements.

## Later rounds

Study compact material representations against the full f32 reference, including
many tiny additions and storage reloads. Naive f16 has already failed that case.
Investigate batch APIs only where real call patterns benefit. Model-quality
changes need a separate experimental objective and independently sourced data;
Mixbox similarity is not a fitting target or a physical-accuracy score.
