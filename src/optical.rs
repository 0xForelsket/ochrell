//! Continuous RGB-to-spectrum reconstruction and synthetic optical-strength prior.
//!
//! K and S are nonnegative surrogate material coefficients, not measurements.
//! Preserve encoded states when repeatedly mixing: RGB round trips lose spectra.
use crate::{optical_generated::*, Color, MixError};

// W,C,M,Y,R,G,B,K: continuous cube-simplex decomposition in linear RGB.
fn recipe(x: [f64; 3]) -> [(usize, f64); 4] {
    let [r, g, b] = x;
    let lo = r.min(g).min(b);
    let hi = r.max(g).max(b);
    let (s, p, mid) = if r <= g && r <= b {
        (1, if g > b { 5 } else { 6 }, g.min(b))
    } else if g <= r && g <= b {
        (2, if r > b { 4 } else { 6 }, r.min(b))
    } else {
        (3, if r > g { 4 } else { 5 }, r.min(g))
    };
    [(0, lo), (7, 1. - hi), (s, mid - lo), (p, hi - mid)]
}

// One transparent kernel, instantiated in f32 and f64. No heap allocation,
// table lookup, nonlinear optimizer, or platform-specific runtime dependency.
macro_rules! optical_kernel {
    ($mixer:ident, $latent:ident, $ty:ty, $n:ident, $basis:ident, $rgb:ident, $y:ident) => {
        #[derive(Clone, Copy, Debug)]
        pub struct $latent {
            k: [$ty; $n],
            s: [$ty; $n],
            residual: [$ty; 3],
        }
        impl $latent {
            /// Restore a material state from its wavelength-ordered components.
            ///
            /// Intended for lossless storage and bindings. This checks finite,
            /// nonnegative absorption and finite, strictly positive scattering;
            /// it does not certify that supplied coefficients describe real paint.
            /// The wavelength grid/model version must match this implementation.
            pub fn try_from_parts(
                k: [$ty; $n],
                s: [$ty; $n],
                residual: [$ty; 3],
            ) -> Result<Self, MixError> {
                if k.iter()
                    .chain(s.iter())
                    .chain(residual.iter())
                    .any(|v| !v.is_finite())
                {
                    return Err(MixError::NonFinite);
                }
                if k.iter().any(|v| *v < 0.) || s.iter().any(|v| *v <= 0.) {
                    return Err(MixError::OutOfRange);
                }
                Ok(Self { k, s, residual })
            }
            pub fn absorption(&self) -> &[$ty; $n] {
                &self.k
            }
            pub fn scattering(&self) -> &[$ty; $n] {
                &self.s
            }
            pub fn residual(&self) -> [$ty; 3] {
                self.residual
            }
            pub fn without_residual(mut self) -> Self {
                self.residual = [0.; 3];
                self
            }
            /// Convex optical-state mixture. NaN means zero; other t are clamped.
            pub fn interpolate(self, b: Self, t: $ty) -> Self {
                let t = if t.is_nan() { 0. } else { t.clamp(0., 1.) };
                Self {
                    k: std::array::from_fn(|i| self.k[i] * (1. - t) + b.k[i] * t),
                    s: std::array::from_fn(|i| self.s[i] * (1. - t) + b.s[i] * t),
                    residual: std::array::from_fn(|i| {
                        self.residual[i] * (1. - t) + b.residual[i] * t
                    }),
                }
            }
            /// Normalize nonnegative weights and accumulate in f64. Grouped mixes
            /// agree when their weights include the mass of each group.
            pub fn weighted(items: &[(Self, f32)]) -> Result<Self, MixError> {
                if items.is_empty() || items.iter().any(|(_, w)| !w.is_finite() || *w < 0.) {
                    return Err(MixError::InvalidWeights);
                }
                let total: f64 = items.iter().map(|(_, w)| *w as f64).sum();
                if total <= 0. {
                    return Err(MixError::InvalidWeights);
                }
                let mut k = [0_f64; $n];
                let mut s = [0_f64; $n];
                let mut e = [0_f64; 3];
                for (z, weight) in items {
                    let w = *weight as f64 / total;
                    for i in 0..$n {
                        k[i] += w * z.k[i] as f64;
                        s[i] += w * z.s[i] as f64;
                    }
                    for i in 0..3 {
                        e[i] += w * z.residual[i] as f64;
                    }
                }
                Ok(Self {
                    k: k.map(|v| v as $ty),
                    s: s.map(|v| v as $ty),
                    residual: e.map(|v| v as $ty),
                })
            }
        }
        #[derive(Clone, Copy, Debug, Default)]
        pub struct $mixer;
        impl $mixer {
            pub fn encode(&self, c: Color) -> $latent {
                let x = c.linear();
                let weights = recipe(x);
                let r: [$ty; $n] = std::array::from_fn(|i| {
                    weights.iter().map(|(p, w)| *w as $ty * $basis[*p][i]).sum()
                });
                let luminance: $ty = (0..$n).map(|i| r[i] * $y[i]).sum();
                let neutral_s = 2. * luminance / (1. + luminance * luminance);
                let strength = (1. + (WHITE_STRENGTH - 1.) * x[0].min(x[1]).min(x[2])) as $ty;
                let mut k = [0.; $n];
                let mut s = [0.; $n];
                let mut raw = [0.; 3];
                for i in 0..$n {
                    let q = (1. - r[i]) * (1. - r[i]) / (2. * r[i]);
                    s[i] = strength * (neutral_s / (1. + q)).sqrt();
                    k[i] = q * s[i];
                }
                // Separate independent K/S inference from the ordered projection.
                // KM inversion recovers r algebraically; integrate r directly.
                for i in 0..$n {
                    for ch in 0..3 {
                        raw[ch] += r[i] * $rgb[i][ch];
                    }
                }
                $latent {
                    k,
                    s,
                    residual: std::array::from_fn(|i| (x[i] - raw[i] as f64) as $ty),
                }
            }
            pub fn decode_linear(&self, z: $latent) -> [f64; 3] {
                let mut x: [$ty; 3] = [0.; 3];
                // Compute independent optics first; retain the original ordered
                // colorimetric reduction and all floating-point expressions.
                let reflectance: [$ty; $n] = std::array::from_fn(|i| {
                    let q = z.k[i] / z.s[i];
                    1. / (1. + q + (q * (q + 2.)).sqrt())
                });
                for i in 0..$n {
                    for ch in 0..3 {
                        x[ch] += reflectance[i] * $rgb[i][ch];
                    }
                }
                std::array::from_fn(|i| x[i] as f64 + z.residual[i] as f64)
            }
            pub fn decode(&self, z: $latent) -> Color {
                Color::from_linear_gamut_mapped(self.decode_linear(z))
            }
            /// Clamp t to [0,1]; NaN means zero. Use try_mix for strict checking.
            pub fn mix(&self, a: Color, b: Color, t: f32) -> Color {
                let t = crate::mixing::bounded_t(t);
                if t == 0. || a == b {
                    return a;
                }
                if t == 1. {
                    return b;
                }
                self.decode(self.encode(a).interpolate(self.encode(b), t as $ty))
            }
            pub fn try_mix(&self, a: Color, b: Color, t: f32) -> Result<Color, MixError> {
                if !t.is_finite() {
                    return Err(MixError::NonFinite);
                }
                if !(0. ..=1.).contains(&t) {
                    return Err(MixError::OutOfRange);
                }
                Ok(self.mix(a, b, t))
            }
            /// Normalized nonnegative weights. Zero-weight colors are ignored.
            pub fn mix_weighted(&self, items: &[(Color, f32)]) -> Result<Color, MixError> {
                if items.is_empty() || items.iter().any(|(_, w)| !w.is_finite() || *w < 0.) {
                    return Err(MixError::InvalidWeights);
                }
                let total: f64 = items.iter().map(|(_, w)| *w as f64).sum();
                if total <= 0. {
                    return Err(MixError::InvalidWeights);
                }
                let mut k = [0_f64; $n];
                let mut s = [0_f64; $n];
                let mut e = [0_f64; 3];
                for (c, weight) in items {
                    if *weight == 0. {
                        continue;
                    }
                    let z = self.encode(*c);
                    let w = *weight as f64 / total;
                    for i in 0..$n {
                        k[i] += w * z.k[i] as f64;
                        s[i] += w * z.s[i] as f64;
                    }
                    for i in 0..3 {
                        e[i] += w * z.residual[i] as f64;
                    }
                }
                Ok(self.decode($latent {
                    k: k.map(|v| v as $ty),
                    s: s.map(|v| v as $ty),
                    residual: e.map(|v| v as $ty),
                }))
            }
        }
    };
}
optical_kernel!(
    FastPigmentMixer,
    Latent,
    f32,
    FAST_N,
    FAST_BASIS,
    FAST_RGB,
    FAST_Y
);
optical_kernel!(
    ReferenceSpectralMixer,
    ReferenceLatent,
    f64,
    REF_N,
    REF_BASIS,
    REF_RGB,
    REF_Y
);
pub type PigmentMixer = FastPigmentMixer;
pub fn mix(a: Color, b: Color, t: f32) -> Color {
    FastPigmentMixer.mix(a, b, t)
}
pub fn mix_weighted(items: &[(Color, f32)]) -> Result<Color, MixError> {
    FastPigmentMixer.mix_weighted(items)
}

/// Diagnostic decoder: promote the fast state's coefficients and quadrature
/// weights to f64, isolating f32 decoder roundoff from wavelength sampling.
#[doc(hidden)]
pub fn decode_fast_f64(z: Latent) -> [f64; 3] {
    let mut x = z.residual.map(|v| v as f64);
    for i in 0..FAST_N {
        let q = z.k[i] as f64 / z.s[i] as f64;
        let r = 1. / (1. + q + (q * (q + 2.)).sqrt());
        for ch in 0..3 {
            x[ch] += r * FAST_RGB[i][ch] as f64;
        }
    }
    x
}
