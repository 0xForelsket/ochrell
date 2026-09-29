# Research release verification

The reproducible command is `python3 tools/reproduce.py`; it fails on a failing Cargo test, a failed experiment process, a missing precision dataset, or paper rendering error when TeX is available. The release archive includes the recorded results rather than only the manuscript's summaries.

Completed validation scope:

* Stable K–M inversion and reflectance round trip, transfer-function round trip, neutral reflectors, and an OKLab primary reference.
* Analytic optical Jacobian against central differences.
* Affine-field reproduction by both 3D interpolation schemes, including all six tetrahedron coordinate orderings.
* Checked color inputs, invalid weights, malformed/NaN LUTs and binary round trips.
* Endpoint identity, symmetry, canonical green/purple checks, source reconstruction on a grid, and shrinking-neighborhood endpoint continuity.
* Independent Python/Rust f64 forward comparison, f32/f64 comparison and sampling ablations.
* Full RGB reconstruction and random-mixture datasets; raw out-of-gamut values retained.
* Dense canonical and random-trajectory measurements, including steep cases.
* Native scalar-source performance and startup measurements.
* Markdown, TeX, PDF, figure and table regeneration; visual PDF review.

Not established:

* Physical accuracy against measured paint mixtures or fidelity to any commercial mixer.
* Globally optimal or globally smooth direct inversion.
* Uniformly small LUT approximation error or uniformly gentle visual trajectories.
* Browser/WASM runtime performance, C ABI, GPU, manual SIMD, brush-engine integration, or production readiness.

Use `python3 tools/package_release.py` after reproduction. It checks required files, creates `MANIFEST.sha256`, packages source and evidence without build debris, and verifies the archive bytes. No remote repository publishing or package-registry upload is part of this deliverable.
