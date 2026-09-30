# Product direction: prepare a palette, then paint with its materials

Date: 2026-09-30. Status: agreed product direction; subsequent implementation
updates are linked below. This document records the product discussion following
the Ochrell/Mixbox performance review. It does not announce a shipped palette
API, generated mixer, new physical calibration, or default change.

Implementation update: the first [Synthetic Four reference](palette-reference.md)
is available as an opt-in recipe API, now with an explicit
[prepared forward decoder](palette-lut.md). [Target matching and custom palettes](palette-workflow.md)
and native recipe painting in the sibling renderer are implemented as opt-in
capabilities. [Measured oil calibration studies](measured-oils-v3-results.md)
remain research candidates; no measured preset or default promotion is established.

## Decision

Extend Ochrell into a library that lets a person or an agent choose a palette,
prepare an accelerated mixer for that palette, and paint with persistent material
recipes. Support agents painting through code as a primary workflow. A painting
application can expose the same operations through virtual paint tubes and a
mixing interface.

Keep the current continuous spectral implementation as a supported mode for
arbitrary RGB input and existing projects. Develop palette mode alongside it.
The intended eventual painting-app default is a bundled, prepared palette once
quality, performance and persistence are demonstrated. Preserve the existing
library API default initially; a later default change must be explicit and
versioned. Existing paintings retain their original model.

The product is an accelerated, reproducible palette mixer. A LUT is a candidate
implementation, not a requirement that every palette use the same table shape.
Choosing different paint materials should change mixing behavior, including
tints and mixture trajectories, rather than just changing displayed swatches.

The selected [starter palette tracks](starter-palettes.md) are a four-tube Old
Holland oil study subset and an independent synthetic four-material baseline.
The measured dataset's distribution terms and fitted model remain to be resolved.
The full eight-tube Monet-inspired study palette is a later research track.

## Why this direction

Current Ochrell reconstructs a spectrum from RGB and assigns absorption and
scattering through a synthetic optical-strength prior. Its fast material stores
41 K samples, 41 S samples and three residual channels: 85 f32 values, 340 bytes.
It evaluates spectral optics during decoding. This provides an inspectable
general RGB model, but entails substantially more state and arithmetic than a
small fixed-pigment representation. See [architecture](architecture.md) and the
[recorded optimization evidence](optimization-round1.md).

A fixed palette instead stores proportions of known virtual materials. Under
the chosen homogeneous K-M model, their K and S can be combined from those
proportions. The same materials can be evaluated directly as a spectral
reference or through an accelerated approximation. A smaller recipe state and
precomputed decoding are opportunities to measure, not speed guarantees.

The v0.2 change away from a finite palette addressed actual reconstruction,
mixture and tint failures. Those findings remain relevant: this direction is not
a decision to restore the legacy palette unchanged or accept its failures.
See [revision decisions](revision-decisions.md).

## Two supported modes

| Concern | Current continuous spectral mode | Planned palette mode |
|---|---|---|
| Input | Arbitrary RGB | Explicit paints and mixture proportions; optional color targets |
| Material identity | Inferred K/S spectrum plus residual | Recipe in a named, versioned palette |
| Preparation | No runtime model generation | Load a prepared palette or generate and verify one |
| Reference | Existing 81-band f64 model | Direct spectral evaluation of the selected palette |
| Acceleration | Existing 41-band kernel and optional compact state | LUT or another independently generated approximation |
| Role | Existing API, saved projects and general RGB mixing | Deliberate palette selection and code-driven painting |

The current spectral reference does not define the correct output for a new
palette. Every palette mode needs its own reference based on its selected
material properties. Comparisons with v0.2 can show differences; they cannot
serve as the new palette's physical ground truth.

## User and agent workflow

1. **Choose a palette.** Select named materials from an available library, load a
   shared palette, or specify synthetic materials. The starter research tracks
   are selected in [starter-palettes.md](starter-palettes.md); a historically
   calibrated launch palette is not yet established.
2. **Inspect its behavior.** Preview source paints, pair mixtures, white tints,
   dark mixtures and achievable colors. Show whether materials are measured,
   reconstructed or deliberately synthetic.
3. **Prepare the mixer.** Reuse a compatible cached artifact or generate an
   accelerated evaluator and check it against that palette's reference. Bundled
   palettes arrive prepared; users need not wait for generation every session.
4. **Paint through code or UI.** Load a paint or saved mixture, mix quantities,
   and apply it through the host's brushes. Preserve recipes through pickup,
   mixing, deposition and storage.
5. **Save and reopen.** Retain the palette identity and the model/artifact needed
   to reproduce the painting. Reuse successful mixture recipes across strokes.

The agent makes artistic decisions; the library performs numerical mixing and
recipe search. An agent should be able to render swatch sheets and trial strokes
programmatically, compare results, and reuse named mixtures. It should not have
to infer optical coefficients or guess exact recipes from pigment names.

The following is illustrative pseudocode, not an existing Python binding or a
committed API shape. Equivalent operations should be available to code hosts,
including the sibling renderer's Rust/TypeScript interfaces.

```python
palette = load_palette("example-palette", version="1")
mixer = prepare_palette(palette)  # reuse a compatible artifact when available

green = mixer.mix({"yellow": 0.6, "blue": 0.3, "white": 0.1})
canvas.stroke(path, paint=green, brush=brush)

shadow = mixer.match_color("#596878")
print(shadow.actual_rgb, shadow.match_error)
canvas.stroke(shadow_path, paint=shadow.paint, brush=brush)
```

Both paths produce material recipes. `match_color` searches for an achievable
color under the selected palette and reports the result and mismatch. It must
not silently escape the palette to claim an exact match. Adding an RGB residual
for a broader compatibility mode is a separate design choice; its semantics and
effect on future mixtures must be visible and tested.

A matching policy must define its color space, error metric and deterministic
handling of multiple recipes. Similar immediate colors can have different
future tint or mixing behavior. Searching for a recipe that also achieves a
specified interaction is a later extension, not a prerequisite for the first
palette workflow.

## Reference model and preparation

Palette definitions need material identities, spectral properties and their
source, wavelength/observer/illuminant conventions, and the meaning of mixture
amounts. Mass fractions, volume fractions and arbitrary optical-strength units
must not be silently interchanged. Preserve group amounts when combining
already-mixed recipes; keep host coverage and paint transport separate from
material proportions.

Generate accelerated data from the palette's own reference. Use independently
sourced, appropriately licensed material data or explicitly synthetic
properties. Preserve the existing boundary: Mixbox and Spectral.js code, spectra,
coefficients, LUTs and observed outputs do not become fitting targets or
generation dependencies. A palette-specific model can use new measured data
without rewriting v0.2's frozen provenance or experiments.

There are two different acceleration problems:

- **Recipe to color:** evaluate a known mixture and accelerate its display
  decoding. Explicit tube-based painting primarily needs this direction.
- **Color to recipe:** solve an inverse problem for a requested color. Start with
  on-demand matching and caching where useful; an exhaustive RGB encoder LUT is
  not required before direct recipe painting can begin.

Four normalized pigment concentrations have three independent coordinates, so
a 3D decoder table is practical to investigate. Seven pigments have six
independent coordinates. An unrestricted seven-pigment decoder cannot simply be
put into the same 3D table while preserving all recipes. An RGB-domain encoder
table may still output any number of concentrations, but it does not solve this
decoder dimensionality problem.

Start the acceleration experiment with four materials. Larger palettes remain
part of the product direction and require a measured representation choice;
do not silently reduce a requested full palette to four materials. Pairwise
mixture charts are useful previews, but do not alone define arbitrary mixtures
or persistent multi-paint histories.

Generation cost is unmeasured for the proposed system. Measure reference/data
preparation, forward-table generation, inverse matching, validation, artifact
size and load time separately. Table resolution, solver behavior and material
count affect the result. Neither instant custom generation nor Mixbox speed
parity is an accepted promise. Reusing a prepared palette is distinct from
generating a new one.

## Reproducibility and compatibility

A prepared palette package should identify its material data and provenance,
model version, color conventions, generator settings, acceleration format and
content hash. Retain its numerical validation results and benchmark conditions.
The exact manifest/schema and storage layout are open implementation decisions.

Save the palette/model identity with recipes and paintings, and embed or retain
the exact compatible artifact needed for replay. Reject a missing or mismatched
palette rather than interpreting stored concentration slots as different paints.
Define the intended determinism across supported hosts and verify it; a seed or
data hash alone does not guarantee identical floating-point results everywhere.

Adding a pigment or changing its properties creates a new palette version.
Switching palettes mid-painting needs a declared conversion or coexistence
policy. RGB matching cannot generally preserve the old material's future
behavior, so no automatic lossless migration is assumed. Existing full K/S,
compact and legacy states remain identifiable and must not be reinterpreted as
new palette recipes. Plan migration before any painting-app default change.

## Accuracy and scope

Separate three claims: reproducing a source color, approximating a numerical
reference, and predicting real paint mixtures. More wavelength samples improve
evaluation of a chosen model; they do not recover missing material measurements.
RGB does not uniquely identify a reflectance spectrum, and opaque reflectance
alone determines K/S rather than each component's relative mixing strength.

A model built from measured paints can be evaluated for those formulations and
conditions. Synthetic palettes can ship as synthetic without making that claim.
Historical pigment identification is not a complete optical calibration of the
artist's tube paints. Monet changed palettes over his career; a historical preset
must name its period/source and distinguish documented pigments from modern
equivalents or inferred properties.

The first palette mixer concerns homogeneous color mixing. Brush geometry,
pickup/depletion, coverage, surface lighting, finite-layer glazing, drying and
other medium behavior remain host or separate research concerns. A palette alone
does not reproduce an artist's brushwork or all properties of oil paint.

## Delivery sequence and evidence

| Stage | Deliverable and evidence needed |
|---|---|
| 1. Palette reference | One explicitly defined four-material palette; data provenance; direct spectral mixtures; declared amounts, matching policy and persistence semantics |
| 2. Prepared mixer | Independently generated acceleration; declared numerical error budgets before selection; held-out recipe/tint/ramp results; build time, memory and runtime measurements |
| 3. Code-driven painting | Explicit recipes and optional target-color matching; swatch/trial rendering; cached preparation; reproducible save/reopen in a separate renderer integration |
| 4. Palette choice | At least two palettes with documented behavioral differences; demonstrate that the same interface preserves each palette's identity |
| 5. Default decision | Review quality, end-to-end speed, generation/load cost and compatibility; change the painting-app default only if supported; consider library default/versioning separately |

Validation must include simplex boundaries, white and dark mixtures, multicolor
mixtures, grouping with amounts, long mixing chains, tiny updates and exact
serialization of the chosen state format. Match-color tests include unreachable
targets and recipe ambiguity. Report approximation error separately from any
held-out physical-mixture error. Keep failed candidates and the direct reference.

Performance comparisons must use paired runs on the same host/build and matched
renderer workloads. Separate mixing from dispatch, transport, storage and
lighting. Historical core and renderer ratios are not current-HEAD benchmarks.
Measure any proposed removal of repeated validation or copies while retaining
checked external input. General batching/locality work can benefit both modes;
specialized spectral-state compression is not a prerequisite for this pivot.

This sequence guides the next product experiments. Existing papers, generated
results and completed optimization reports stay as records of their original
models and conditions. This documentation decision itself changes no runtime
code, dependency, state format or renderer behavior.

## Prior art and product distinction

The core workflow is not a novel algorithm claim. Sochorova and Jamriska's 2021
paper, section 3.3, explicitly proposes choosing primary pigments and
precomputing their lookup tables before painting. Its original implementation
uses two LUTs; the later Mixbox polynomial decoder is a separate implementation
detail, not a requirement of reproducing the paper. A faithful reference should
document which published elements it implements and which it changes.

Earlier work also extracts image palettes and computes recipes from measured
base paints for digital and robotic painting. The intended product contribution
is a repeatable, inspectable preparation workflow, code-oriented recipe and
matching operations, and portable versioned palette artifacts. A focused prior
art review does not establish that this whole product combination is unique.

- [Sochorova and Jamriska, Practical Pigment Mixing for Digital Painting (2021), sections 3.2-3.3](https://dcgi.fel.cvut.cz/wp-content/wpallimport-dist/publications/pdf/publications-2021-sochorova-tog-pigments-paper.pdf)
- [Lindemeier, Gulzow and Deussen, Painterly Rendering using Limited Paint Color Palettes (2018)](https://diglib.eg.org/server/api/core/bitstreams/98c9fd61-2fec-4aff-a3b6-abf6335e8dd0/content)
- [RIT, Artist Spectral Database: measurement and optical characterization](https://www.rit.edu/science/sites/rit.edu.science/files/2019-03/ArtistSpectralDatabase.pdf)
- [Roy, Monet's Palette in the Twentieth Century: Water-Lilies and Irises (2007)](https://www.nationalgallery.org.uk/technical-bulletin/roy2007)
