# Mathematical specification

All optical quantities use relative, dimensionless units. The package models a homogeneous, opaque layer; it is not a model of thickness or brush transport. A color is unassociated sRGB, without alpha.

## Color conversions

For an encoded channel u∈[0,1], linear x=u/12.92 if u≤0.04045; otherwise x=((u+0.055)/1.055)^2.4. The inverse is u=12.92x for x≤0.0031308, otherwise u=1.055x^(1/2.4)−0.055. Optical math never uses encoded channels. The sRGB matrix and OKLab matrices in `conversion.rs` are published color-space definitions [CSS,O20 in research.md]. ΔEOK100 means 100 times Euclidean distance in OKLab; it is not CIEDE2000 and should not be given the same perceptual interpretation.

At wavelengths λ_j, define trapezoidal factors h_j (half at endpoints). Set A_j=h_j E_j (xbar_j,ybar_j,zbar_j) / sum_j h_j E_j ybar_j. Δλ cancels between numerator and denominator on an evenly spaced grid. XYZ=sum_j A_j R_j, with Y=1 for a perfect diffuser. Apply the published D65 XYZ→linear-sRGB matrix M. The implemented display integrator additionally divides each linear-RGB column by its perfect-diffuser sum to remove the small truncated-tabulation white bias. This diagonal normalization is a documented colorimetric approximation, not exact unmodified CIE integration.

The reference uses 81 wavelengths from 380 to 780 nm in 5 nm steps, f64. The fast decoder uses 21 wavelengths at 20 nm in f32. Runtime weights precombine illumination, observer, quadrature, the matrix and white normalization. Generating them explicitly and folding them at compile time is algebraically identical to those operations.

## Infinite-thickness Kubelka–Munk

For nonnegative concentration c_i summing to one,

K(λ)=Σ_i c_i K_i(λ), S(λ)=Σ_i c_i S_i(λ), q(λ)=K(λ)/S(λ).

R∞(q)=1+q−sqrt(q²+2q)=1/[1+q+sqrt(q(q+2))].

The reciprocal form avoids subtracting almost equal terms for large q. The standalone f64 routine evaluates sqrt(q)*sqrt(q+2) to extend the usable range. In the known bounded palette, the ordinary product used by the fast decoder is safe. The inverse is q=(1−R)²/(2R). Mixing q directly assumes equal S; that assumption is not made for the palette. R=0 implies infinite K/S, so the basis uses a positive floor.

For an isolated finite layer, a=1+K/S and b=sqrt(a²−1) lead to R0=sinh(bSd)/(a sinh(bSd)+b cosh(bSd)), T0=b/(a sinh(bSd)+b cosh(bSd)). Over backing Rg, R=R0+T0² Rg/(1−R0 Rg). This extension is reviewed but **not implemented**; b→0 requires a separate limit. It should not be confused with averaging pigments in an opaque layer.

## Synthetic palette

Let H_e(λ)=1/[1+exp(−(λ−e)/22)]. Define B=1−H_510, Y=H_530, R=H_600, C=1−R, G=YC, M=1−G. Each letter denotes a *spectral shape*, not an RGB value. Eight reflectances are R_i=0.025+0.915 b_i with b_i=(1,C,M,Y,R,G,B,0). Scatterings are S_i=(8,1,1,1,1,1,1,0.5), constant in wavelength. Set K_i=S_i(1−R_i)²/(2R_i). Every number is exposed in `config.toml`; parameter provenance and the edge sweep are in `data/README.md` and `results/exploration`.

These are synthetic broad-band pigments. Names such as white, cyan or magenta express a role, not a claimed titanium-white or phthalocyanine measurement. The white scattering ratio creates strong tinting, but RGB alone cannot calibrate this ratio.

## Encoder and objective

Let F(c) be the unbounded linear-RGB spectral decoder. Given encoded RGB u and x=transfer_decode(u), find c in the probability simplex approximately minimizing

J(c;u)=||OKLab(F(c))−OKLab(x)||² + η||c−p(u)||²,

where η=0.0002. p is a continuous piecewise-linear RGB cube decomposition. White receives min(r,g,b); black 1−max(r,g,b); the remaining mass is distributed to one secondary and one primary according to sorted channel differences. Example r≤g≤b: p_C=g−r, p_B=b−g; all other chromatic weights zero. The full symmetric cases appear in `pigment.rs`.

The prior resolves some, not all, recipe ambiguity and discourages abrupt changes between unrelated recipes. It is not a physical law. The solver is deterministic for a given build but has no global-optimality guarantee.

### Solver

1. Initialize c=p. Evaluate F and its analytic Jacobian.
2. Convert derivatives to OKLab, using real cube roots; guard the derivative denominator with |LMS|≥1e−12.
3. Form H=J_FᵀJ_F+(η+1e−5)I and g=J_Fᵀ(error)+η(c−p). Solve H d=−g using pivoted Gaussian elimination.
4. Try simplex projection of c+αd, α=1,1/2,..., at most 16 trials. Accept only objective improvement >1e−13.
5. If none succeeds, try projected negative gradient, α=8,4,..., at most 24 trials. A projected unconstrained Newton step is not necessarily descending on an active face; this fallback was required experimentally.
6. Stop on no improvement or after 80 outer iterations. No neighbor warm start is used, so LUT order does not affect node recipes.

The simplex projection sorts v descending, identifies θ=(Σ_{i≤ρ}v_i−1)/ρ with v_ρ>θ, and returns max(v_i−θ,0). The regularizer is part of the objective; 1e−5 is numerical damping. The fixed iteration budget bounds offline work rather than certifying optimality.

Derivatives: dR/dq=−R/sqrt(q(q+2)); dq/dc_i=(K_i−qS_i)/S. These yield the forward Jacobian without finite differences.

## Residual, mixing and reconstruction

Store z=(c,e), with e=x−F(c). For normalized nonnegative mixture weights α_i, use c̄=Σα_i c_i and ē=Σα_i e_i. The result before gamut mapping is x̄=F(c̄)+ē. This is the published concentration-plus-residual construction [SJ21], independently instantiated here with eight pigments and a separate numerical design. We do not claim novelty for it.

Decode(encode(x))=F(c)+(x−F(c))=x in exact arithmetic, independent of inversion quality. This is why source reconstruction is an algebraic consistency check rather than a physical-accuracy result. Finite precision creates tiny deviations. The public pair API returns original endpoint colors exactly; the interior limit agrees up to floating-point error. The fast encoder recomputes e against the f32 decoder after interpolating c. Baking residuals at LUT nodes and interpolating them would not have the same guarantee.

A persistent latent representation preserves convex-combination associativity up to roundoff when weighted amounts are retained. Repeatedly decoding to RGB and re-encoding changes the recipe; RGB-only mixing is generally not associative. Residuals are correction light and may be negative. They are not pigment concentrations and need not satisfy positivity.

## LUT and continuity

The RGB cube is sampled uniformly in **encoded** sRGB at n³ nodes; each stores eight f32 weights. For fractions sorted f_a≥f_b≥f_c, the four tetrahedron vertices have coefficients (1−f_a,f_a−f_b,f_b−f_c,f_c). All are nonnegative and sum to one, preserving the simplex. A consistent cube triangulation agrees on shared faces, so this encoder is C0. It need not be C1, and increasing resolution need not monotonically improve a non-smooth target inverse. Trilinear interpolation is included as an ablation. It uses eight vertices rather than four.

For fixed endpoint latents, K,S and residuals are affine in t. The palette has strictly positive S and K, so the spectral decoder is smooth. Display gamut mapping is continuous but may create derivative kinks. Thus the complete mathematical curve is continuous, not necessarily differentiable everywhere. Floating-point outputs remain quantized; converting to 8-bit introduces additional banding.

## Gamut mapping

If raw linear x is in [0,1]³, preserve it. Otherwise set y=clamp(0.2126x_R+0.7152x_G+0.0722x_B,0,1), d=x−y(1,1,1), and choose the greatest a∈[0,1] for which y+ad stays in the cube. For d_j>0, a≤(1−y)/d_j; for d_j<0, a≤−y/d_j. Return y+ad. A final clamp handles roundoff. This preserves linear luminance when in range, but does not promise perceptual hue preservation. At luminance beyond the cube it returns white/black. Measurements explicitly count how often this acts.
