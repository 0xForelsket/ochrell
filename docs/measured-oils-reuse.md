# Old Holland source reuse audit

Checked 2026-09-30 for this research request. **A license for the separate data
archive, including commercial redistribution and fitted coefficients/LUTs, could
not be established from the published material inspected.** This is unresolved,
not a finding that commercial use is expressly forbidden.

| Source | What is established | What is not established |
|---|---|---|
| [Author's dataset page](https://www.azadehasadi.net/paintdatasets.html) | Public download link, authorship, paper citation, research use and description of measured mixtures | No explicit dataset license or grant covering commercial redistribution |
| [Archive](https://www.azadehasadi.net/publication_files/spectralDatasets.zip) | Exact previously audited bytes; readme describes columns and wavelength range | No license-named member; readme contains no reuse terms |
| [Publisher article](https://library.imaging.org/ei/articles/32/5/art00007) and [institutional paper copy](https://pure.mpg.de/rest/items/item_3285223_3/component/file_3285224/content) | Institutional indexed paper text carries a CC BY 4.0 notice | The scope of that notice does not explicitly identify the separately hosted ZIP |

The author's downloaded manuscript copy does not contain that license notice.
The institution's PDF is indexed with it, but direct retrieval returned HTTP 403
in the browser tool during this audit. The article notice is evidence about the
article; we do not silently transfer it to the ZIP. Search for a dataset-specific
license did not locate one. Public availability and a checksum are not licenses.

The archive SHA-256 remains
`cda35e5ab968bb18a05127c1b9fb0b2bd3c4a4bb88d4bf4ae1e4b2bb5de07538`.
Downloaded author manuscript SHA-256:
`33b2d1f0297556467e870e9267a951745a94a550b96c0d8ecdc056dd028d6af3`.

This run performs the requested local analysis. The source archive, measurement
arrays, fitted optical curves and their swatches stay in ignored research output.
The repository receives original analysis code, the frozen methodology, source
identifiers and numerical error reports; no bundled measured-paint preset or LUT
is produced. This keeps the earlier redistribution decision intact without
blocking the requested fit and held-out evaluation.

Correction after discussion: this audit has not established that permission is
legally required for an independently implemented model. Missing license terms
alone do not establish infringement or make fitted coefficients copyrighted
derivative works. The applicability of any copyright, database right or contract
has not been determined. Local storage of the research artifacts is the current
project arrangement, not a finding that sharing them is prohibited.

Asking the source author to clarify commercial use and redistribution of data,
coefficients and LUTs is one way to reduce release uncertainty, not an automatic
prerequisite for research or a demonstrated legal requirement. No email has been
sent. If clarification is obtained, retain it with the provenance. The current
fixed-pure model does encode the four measured pure spectra through an invertible
K/S transform; that is a technical fact relevant to analysis of a release, not
proof that the underlying factual measurements are protected.

This is an evidence audit for the project's release decision, not a legal ruling
about ownership or the protectability of individual measurements.
