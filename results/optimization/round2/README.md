# Compact-state experiment records

See `../../../docs/optimization-round2.md` for the interpretation and commands.
Error metric: delta E OKLab * 100; this is model agreement, not paint accuracy.

- `environment.json`, `fitting-provenance.json`, `fitting.npz`: authoring
  versions, data hashes, greedy knot order and PCA trained only on Ochrell states.
- `screening-initial.json`: original screen before canonical ramps and the
  neighboring 22/23-knot candidates were added. Not used as final acceptance.
- `screening.json`, `screening-*-errors.npz`: final 26-candidate selection data,
  including failed cases. Each NPZ contains named per-case error arrays.
- `selection.json`: 24-knot decision frozen before the independent holdout.
- `holdout.json`, `holdout-adaptive24-errors.npz`: NumPy holdout evaluation.
- `reproduction-check.json`: a fresh refit reproduces every fitting array and
  the selected candidate's screening metrics exactly on the recorded host.
- `compact-initial.rs.txt`, `benchmark-initial.csv`, `benchmark-candidate.csv`,
  `implementation-trial.json`, `rust-holdout*.csv.gz`: initial Rust implementation
  and overhead-reduction trial. The numerical CSVs are identical. These timing
  trials were unpinned, 200,000 iterations, seven recorded repeats plus warmup.
- `confirmation-initial/`: first pinned timing confirmation, before the
  equivalent constant-initializer change for Rust 1.75 compatibility. Its
  recorded source hash identifies that source revision. Substantial timing
  variation is retained, not filtered out.
- `rust-quality.csv.gz`: final actual-Rust holdout, 58,751 records. Includes
  compact/full and compact/reference errors and each method's display RGB.
- `rust-environment.json`, `rust-summary.json`, `benchmark-run*.csv`: final
  implementation hashes, toolchain, corpus checksums, packages, acceptance and
  all timing samples. Timings rotate operations and include one discarded
  warmup per process. No rendering or FFI timing is included.
- `canonical-comparison.png`: same input colors and amount fractions, full and
  compact strips plus error curves, generated from the Rust CSV.
- `tests-*.txt`, `basic.txt`, `check-all-targets.txt`: local validation logs.

Derived numerical data retain the existing CIE/CC BY-SA 4.0 attribution;
see `../../../data/README.md` and `../../../docs/coefficients.md`. Original
implementation/reproduction code is MIT OR Apache-2.0. No proprietary comparator
implementation, coefficients, fitted target data or new paint measurements
were used in this round. The default optical model is unchanged.
