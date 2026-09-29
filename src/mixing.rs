use crate::latent::{Latent, ReferenceLatent};
use crate::{lut::Lut, spectrum, Color, MixError};
use std::sync::{Arc, OnceLock};
pub(crate) fn bounded_t(t: f32) -> f32 {
    if t.is_nan() {
        0.
    } else {
        t.clamp(0., 1.)
    }
}
#[derive(Clone, Debug)]
pub struct FastPigmentMixer {
    lut: Arc<Lut>,
}
#[derive(Clone, Copy, Debug, Default)]
pub struct ReferenceSpectralMixer;
impl Default for FastPigmentMixer {
    fn default() -> Self {
        static LUT: OnceLock<Arc<Lut>> = OnceLock::new();
        Self {
            lut: LUT
                .get_or_init(|| {
                    Arc::new(
                        Lut::from_bytes(include_bytes!("../data/default.lut"))
                            .expect("bundled LUT must be valid"),
                    )
                })
                .clone(),
        }
    }
}
impl FastPigmentMixer {
    pub fn with_lut(lut: Lut) -> Self {
        Self { lut: Arc::new(lut) }
    }
    pub fn lut(&self) -> &Lut {
        &self.lut
    }
    pub fn encode(&self, c: Color) -> Latent {
        self.encode_weights(c, self.lut.lookup(c))
    }
    pub fn encode_trilinear(&self, c: Color) -> Latent {
        self.encode_weights(c, self.lut.lookup_trilinear(c))
    }
    fn encode_weights(&self, c: Color, w: [f32; 8]) -> Latent {
        let x = c.linear();
        let f = spectrum::forward_fast(&w);
        Latent {
            weights: w,
            residual: std::array::from_fn(|i| (x[i] - f[i] as f64) as f32),
        }
    }
    pub fn decode_linear(&self, z: Latent) -> [f64; 3] {
        let f = spectrum::forward_fast(&z.weights);
        std::array::from_fn(|i| f[i] as f64 + z.residual[i] as f64)
    }
    pub fn decode(&self, z: Latent) -> Color {
        Color::from_linear_gamut_mapped(self.decode_linear(z))
    }
    /// t is clamped to [0,1]; NaN means 0. Use try_mix to reject invalid t.
    pub fn mix(&self, a: Color, b: Color, t: f32) -> Color {
        let t = bounded_t(t);
        if t == 0. {
            return a;
        }
        if t == 1. {
            return b;
        }
        if a == b {
            return a;
        }
        self.decode(self.encode(a).interpolate(self.encode(b), t))
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
    /// Nonnegative weights are normalized. Empty/all-zero/nonfinite/negative input fails.
    pub fn mix_weighted(&self, items: &[(Color, f32)]) -> Result<Color, MixError> {
        if items.is_empty() || items.iter().any(|(_, w)| !w.is_finite() || *w < 0.) {
            return Err(MixError::InvalidWeights);
        }
        let total: f64 = items.iter().map(|(_, w)| *w as f64).sum();
        if total <= 0. {
            return Err(MixError::InvalidWeights);
        }
        let mut w = [0.; 8];
        let mut e = [0.; 3];
        for (c, weight) in items {
            if *weight == 0. {
                continue;
            }
            let z = self.encode(*c);
            let a = *weight as f64 / total;
            for i in 0..8 {
                w[i] += a * z.weights[i] as f64
            }
            for i in 0..3 {
                e[i] += a * z.residual[i] as f64
            }
        }
        Ok(self.decode(Latent {
            weights: w.map(|x| x as f32),
            residual: e.map(|x| x as f32),
        }))
    }
}
impl ReferenceSpectralMixer {
    pub fn encode(&self, c: Color) -> ReferenceLatent {
        let w = crate::latent::invert(c.channels().map(|x| x as f64));
        let f = spectrum::forward(&w);
        let x = c.linear();
        ReferenceLatent {
            weights: w,
            residual: std::array::from_fn(|i| x[i] - f[i]),
        }
    }
    pub fn decode_linear(&self, z: ReferenceLatent) -> [f64; 3] {
        let f = spectrum::forward(&z.weights);
        std::array::from_fn(|i| f[i] + z.residual[i])
    }
    pub fn decode(&self, z: ReferenceLatent) -> Color {
        Color::from_linear_gamut_mapped(self.decode_linear(z))
    }
    pub fn mix(&self, a: Color, b: Color, t: f32) -> Color {
        let t = bounded_t(t);
        if t == 0. {
            return a;
        }
        if t == 1. {
            return b;
        }
        self.decode(self.encode(a).interpolate(self.encode(b), t as f64))
    }
}
pub type PigmentMixer = FastPigmentMixer;
pub fn mix(a: Color, b: Color, t: f32) -> Color {
    FastPigmentMixer::default().mix(a, b, t)
}
pub fn mix_weighted(items: &[(Color, f32)]) -> Result<Color, MixError> {
    FastPigmentMixer::default().mix_weighted(items)
}
