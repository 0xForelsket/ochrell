# Research review and design record

This document preserves the initial investigation and its decisions. The final section records the v0.2 mathematical revision; current equations and runtime architecture are in `math.md` and `architecture.md`.

Date: 2026-09-29. This review preceded the Rust implementation. Public research was consulted; no Mixbox SDK, source, coefficient table, binary, or dataset was downloaded or inspected. This is an independent implementation of published ideas, not an independent invention of those ideas. Public availability of a paper is not a software or dataset license. The source license does not constitute a patent clearance opinion.

## Main findings

An RGB triplet specifies three colorimetric integrals, not a unique reflectance spectrum. Even a known opaque reflectance gives only K/S, not the separate K and S needed to predict the effect of mixing pigments with different scattering strengths. An RGB-input engine must choose both a spectral prior and a scattering prior. Exact RGB reconstruction is consequently not evidence that the inferred paint is real.

Sochorová and Jamriška (2021) contribute an RGB-compatible latent representation: nonnegative primary-pigment concentrations accompanied by an additive RGB residual. The concentrations and residuals are linearly combined, then decoded. Residuals restore colors beyond the pigment gamut. The paper also develops surrogate pigments to address display-gamut issues and accelerates the transforms using tables. The underlying Kubelka–Munk law is older. We reproduce the **published representation concept**, independently designing spectra, inversion, tables, and implementation. We do not claim this representation as new. [SJ21]

## Literature and implementation assessment

| Source / problem | Equations and assumptions | Strengths / limitations | Cost and decision |
|---|---|---|---|
| Kubelka & Munk 1931; Kubelka 1948, 1954: diffuse paint layers [KM31,K48,K54] | Two counter-propagating diffuse fluxes; homogeneous K,S in the basic case; infinite R=1+q-sqrt(q²+2q), q=K/S | Separates absorption and scattering; ignores directional microstructure, gloss and fluorescence | O(wavelengths × pigments), appropriate physical reference; finite layers researched but outside core |
| Haase & Meyer 1992 [HM92]: pigment graphics | Spectral K–M and colorimetric conversion, color matching | Connects paint optics to graphics; requires pigment characterization | Spectral work per pixel; reference architecture |
| Curtis et al. 1997 [C97]: watercolor | Shallow-water transport plus layered K–M compositing | Demonstrates optics and transport are distinct; requires paper/fluid state | Whole simulation much larger than a color mixer; do not imply watercolor physics from mixing alone |
| Burns 2020 [B20]: reconstruct reflectance from tristimulus values | Minimize slope/log-slope variation subject to color constraints and bounds | Smooth spectra, underdetermined metamer choice; nonlinear bounded solve can be expensive | Offline/reference candidate A; this project's exploratory bounded smoothness objective is independently defined |
| Smits 1999 [S99]: inexpensive RGB spectral upsampling | Decompose RGB over primary/secondary/white spectra | Cheap evaluation; depends on chosen basis and illuminant; not pigment identification | O(N); conceptual precedent for a deterministic initializer only; no spectra copied |
| Jakob & Hanika 2019 [JH19]: compact bounded reflectance | Sigmoid of a low-degree polynomial, coefficients found numerically | Very compact spectral textures; spectra need not correspond to paint | Excellent rendering option, but still requires a scattering prior for K–M; no coefficients used |
| Tan et al., Pigmento [T17]: pigment image decomposition | Infer spectral K,S and nonnegative pigment maps from an image | Captures palette structure; RGB ambiguity remains | Global image optimization, unsuitable as a per-pixel stateless encoder; informs regularization |
| Gossett & Chen [GC04]: intuitive visualization | Artist-inspired RYB cube interpolation | Inexpensive and controllable, lacks absorption/scattering interpretation | Rejected as core; reviewed as alternative, not benchmarked here |
| Hébert & Hersch 2015 [HH15]: halftone prediction | Neugebauer R=sum a_i R_i; Yule–Nielsen R=(sum a_i R_i^(1/n))^n | Models area coverage and optical dot gain; needs measured overprints | Not a homogeneous paint-volume model; no adoption |
| Ottosson 2020 [O20]: perceptual interpolation | Linear transforms, cube roots, Euclidean OKLab distance | Useful diagnostic; not a pigment mixture law | O(1), mandatory baseline and error metric |
| Wyman et al. 2013 [W13]: analytic observer fits | Gaussian-type fits to standard observer | Avoids tables but introduces extra colorimetric error | Reviewed; choose tabulated observer for reference |

The original 1931 bibliographic record and later primary exposition were located; a complete translation of the 1931 article was not obtained. The 1948 primary publisher abstract, the accessible 2021 paper, and later primary graphics sources ground the equations. Haase/Meyer was reviewed through its institutional abstract, not a complete paywalled article. The bibliography distinguishes papers from software and reports; no claim is made that every historical source was read in full.

### Public implementations (reviewed, not copied)

* **Colour 0.4.6**: BSD-3-Clause Python library; broad colorimetric conversions, reconstruction, differences and standard datasets. Used as an independent metric oracle and as the transport for standard observer/daylight samples. Its package license does not erase the original dataset attribution. https://github.com/colour-science/colour
* **rgb2spec**: authors' implementation of [JH19]. A compact coefficient-table approach; no table or source is incorporated. The repository is a useful generator/runtime separation example. https://github.com/mitsuba-renderer/rgb2spec
* **Spectral.js**: repository README describes seven reflectance components, constant-S K–M, concentration weighting, and gamut mapping; MIT stated in README. No source, spectral coefficients, or concentration heuristic is used. https://github.com/rvanwijnen/spectral.js/
* **PBRT 4**: spectral-rendering reference, useful for distinctions between reflectance, illuminant and radiance. No source/data imported. https://pbr-book.org/4ed/Radiometry%2C_Spectra%2C_and_Color
* Rust ecosystem: `palette` offers color-space operations; `colorimetry` offers spectral/colorimetric types. These were located as ecosystem options, not audited or adopted. The runtime crate will have no external dependencies to keep its scope and licensing inspectable.

## Mathematical options and inversion

A. **Full spectral reconstruction.** Solve a bounded smoothness-regularized RGB fit for R(lambda), infer q=(1-R)^2/(2R), choose S, average K and S. Advantages: broad colorimetric coverage and few palette assumptions. Weakness: the smoothest metamer need not mix like paint. For small R, q grows rapidly; strongly absorbing narrow bands can make mixtures too dark. Exact RGB fit does not determine tint strength.

B. **Fixed latent basis.** Specify independent smooth R_i and scattering S_i, derive K_i. Fit nonnegative concentrations on a simplex. A small basis makes intermediate mixtures interpretable and avoids arbitrary narrow spikes. It cannot generally cover the RGB cube; more pigments increase gamut but introduce multiple possible recipes. A prior and deterministic solver are necessary.

C. **Basis + residual.** Keep B's concentrations and store linear-RGB residual e=x-F(c). Decode F(c)+e. Source reconstruction becomes an algebraic identity, while mixture curvature comes from F. The residual is a color correction, not a physical pigment. Large residuals can dominate or cause out-of-gamut intermediates. Therefore evaluate raw B error and intermediate colors, not only corrected reconstruction.

NNLS is appropriate for a *linear* spectral matching stage, but direct colorimetric K–M inversion is nonlinear. Candidates include projected gradient, projected Gauss–Newton, constrained SQP, and a neural approximation. We will first benchmark a deterministic regularized solver, then bake its encoder to a reproducible RGB cube. A neural model adds training and deployment complexity before any demonstrated need. Polynomial decoders can be fast but may violate positivity and produce poor extrapolation; direct spectral f32 decoding is a simpler first approximation.

A 3D RGB encoder table remains possible with more than four output pigment weights: RGB is the table domain, and each entry stores an N-vector. A 3D *decoder* table generally cannot parameterize an unrestricted simplex with more than four pigments. These are different dimensionality constraints.

## Numerical and architectural recommendations (before experiments)

1. Use sRGB transfer functions only at the public color boundary. Optical integration and residuals use linear RGB. Never apply K–M directly to encoded RGB channels.
2. Use 380–780 nm at 5 nm in f64 for a physical reference, and evaluate 10/20 nm f32 alternatives against it. The range truncation is explicit.
3. Normalize XYZ by integral E*ybar. Keep the small tabulation whitepoint discrepancy visible; document any diagonal white normalization in the display transform.
4. Derive positive synthetic spectra with smooth band transitions and explicitly chosen relative S; pigment names are descriptive, not measured commercial identities.
5. Fit simplex concentrations with a weak deterministic prior. Check recipe continuity; LUT interpolation guarantees C0 but not C1 continuity.
6. At a table query, compute the residual against the actual runtime decoder. Interpolating precomputed residuals alone would not guarantee exact reconstruction between nodes.
7. Keep raw linear RGB available for diagnostics. A display gamut mapper should be continuous and exact inside the cube; record how often it acts.
8. Cache latents at brush/color level where possible. Separately benchmark full RGB-in/RGB-out and already-encoded mixing.
9. Ship numerical invariants, seeded reconstruction trials, canonical mixtures, random pair trajectories, spectral-resolution and basis ablations. A color-space metric is not a substitute for real-paint measurements or artist evaluation.

## Provenance policy

No measured pigment data is incorporated: the investigation did not establish a sufficiently documented set of separate K,S spectra with suitable redistribution terms. All pigment parameters will be original analytic design choices, with their formulas and values retained in TOML. No empirical fit to commercial paint is claimed.

The CIE dataset pages identify the standard observer and D65 sources; their metadata reports **CC BY-SA 4.0**. The colorimetric subset is obtained via Colour 0.4.6 (observer samples plus linearly interpolated 5 nm D65 data), attributed in `data/README.md`, and kept under those dataset terms. Original Rust/Python source and synthetic pigment parameters use MIT OR Apache-2.0. This mixed-license distribution is documented rather than calling all bundled data MIT.

## References

[KM31] P. Kubelka and F. Munk. 1931. Ein Beitrag zur Optik der Farbanstriche. Zeitschrift für technische Physik 12, 593–601. Historical reference, cited in [K48,SJ21].

[K48] P. Kubelka. 1948. New Contributions to the Optics of Intensely Light-Scattering Materials. Part I. JOSA 38(5), 448–457. https://doi.org/10.1364/JOSA.38.000448

[K54] P. Kubelka. 1954. New Contributions ... Part II: Nonhomogeneous Layers. JOSA 44(4), 330. https://doi.org/10.1364/JOSA.44.000330

[HM92] C. S. Haase and G. W. Meyer. 1992. Modeling Pigmented Materials for Realistic Image Synthesis. TOG 11(4), 305–335. https://doi.org/10.1145/146443.146452

[C97] C. J. Curtis, S. E. Anderson, J. E. Seims, K. W. Fleischer and D. H. Salesin. 1997. Computer-Generated Watercolor. SIGGRAPH, 421–430. https://grail.cs.washington.edu/projects/watercolor/

[S99] B. Smits. 1999. An RGB-to-Spectrum Conversion for Reflectances. JGT 4(4), 11–22. https://doi.org/10.1080/10867651.1999.10487511

[B20] S. A. Burns. 2020. Numerical Methods for Smoothest Reflectance Reconstruction. Color Research & Application 45, 8–21. https://doi.org/10.1002/col.22437 ; public precursor https://arxiv.org/abs/1710.05732

[JH19] W. Jakob and J. Hanika. 2019. A Low-Dimensional Function Space for Efficient Spectral Upsampling. CGF 38(2). https://doi.org/10.1111/cgf.13626

[SJ21] Š. Sochorová and O. Jamriška. 2021. Practical Pigment Mixing for Digital Painting. TOG 40(6), Article 234. https://doi.org/10.1145/3478513.3480549 ; author-hosted paper https://dcgi.fel.cvut.cz/wp-content/wpallimport-dist/publications/pdf/publications-2021-sochorova-tog-pigments-paper.pdf

[T17] J. Tan, S. DiVerdi, J. Lu and Y. Gingold. Pigmento: Pigment-Based Image Analysis and Editing. Public preprint 2017. https://arxiv.org/abs/1707.08323

[GC04] N. Gossett and B. Chen. 2004. Paint Inspired Color Mixing and Compositing for Visualization. IEEE InfoVis, 113–118. https://doi.org/10.1109/INFOVIS.2004.52 ; accessible extended author report: https://bahamas10.github.io/ryb/assets/ryb.pdf

[HH15] M. Hébert and R. D. Hersch. 2015. Review of Spectral Reflectance Models for Halftone Prints: Principles, Calibration, and Prediction Accuracy. Color Research & Application. https://doi.org/10.1002/col.21907

[O20] B. Ottosson. 2020. A Perceptual Color Space for Image Processing. https://bottosson.github.io/posts/oklab/

[W13] C. Wyman, P.-P. Sloan and P. Shirley. 2013. Simple Analytic Approximations to the CIE XYZ Color Matching Functions. JCGT 2(2), 1–11. https://jcgt.org/published/0002/02/01/

[DE00] G. Sharma, W. Wu and E. N. Dalal. 2005. The CIEDE2000 Color-Difference Formula: Implementation Notes, Supplementary Test Data, and Mathematical Observations. https://doi.org/10.1002/col.20070

[CIE-O] CIE. 2019. Colour-matching functions of CIE 1931 standard colorimetric observer. https://doi.org/10.25039/CIE.DS.xvudnb9b

[CIE-D] CIE. 2019. CIE standard illuminant D65. https://doi.org/10.25039/CIE.DS.hjfjmt59

[CSS] W3C. CSS Color Module Level 4, color conversion equations. https://www.w3.org/TR/css-color-4/

## v0.2 follow-up: mathematical improvement without new measurements

The follow-up retains the original literature review and changes the chosen architecture in response to recorded failures. The RGB inverse is now an explicit continuous decomposition into independently fitted bounded spectral anchors. This follows the general compact-basis motivation of Smits and the smooth-reconstruction motivation of Burns; our logit-space first-difference objective, initial solve, coefficients and optical normalization are independently specified in `docs/math.md` and generated in this repository. We do not claim a new general spectral-upsampling principle.

Reflectance alone fixes K/S, not the absolute K and S. Consequently merely improving RGB spectral reconstruction does not fix tinting behavior. Constant scattering with near-black spectra produced extremely dark black/white mixtures. Per-band bounded K+S improved some purple mixtures but produced gray blue/yellow. The selected geometric-mean normalization is a declared prior between these extremes, not a derived law of real paint.

A direct refit of the original finite physical-palette model did not resolve all failures. The continuous spectral encoder improves numerical stability by removing optimizer ambiguity, but the tradeoff is conceptual and practical: its anchors are spectral reconstruction functions rather than identifiable physical paint ingredients, and its persistent latent stores K and S at every wavelength. The method's scope is a general RGB painting surrogate. It cannot infer which actual pigment, binder or paint formulation produced an RGB triplet.

After model selection, the frozen Mixbox screenshot samples and Spectral.js 3.0.0 API outputs were compared observationally. Neither appears in the fitting objective or generation dependencies. Similarity to either is not validation against real paint. A future calibrated palette would require known paints and measured mixture ratios, with sufficient optical information to resolve scattering/tint strength. It would be a separate material mode, not proof that every RGB color has a uniquely correct physical interpretation.
