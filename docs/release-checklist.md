# Release validation, v0.2

The reproducible numerical suite is `python3 tools/reproduce.py`. Rust tests cover K–M/transfer identities, the retained legacy path, default reconstruction, positive optics, canonical hue diagnostics, weighted-state grouping, input-channel-order boundaries, f32/f64 decoder agreement, sampled tint luminance and black-endpoint convergence. Raw experiments test broader inputs, all declared trajectories, residual ablation, wavelength discretization and timing.

The external comparison is observational and post-selection. The complete original capture package is retained for auditing. Coefficient generation reads only attributed CIE data and root model configuration. The revised paper explicitly records failed alternatives, larger state, slower full/cached mixing, nonuniform trajectory-tail improvement, and the unresolved absence of measured-paint calibration.

A release must include generated source/basis, data notices, both model versions, pinned Python requirements, raw results, environment, figure scripts, paper sources and bibliography. Exclude build directories, Python caches and temporary PDF renderings from the archive. Run formatting and release tests after generation; inspect the rendered main PDF before publishing it.
