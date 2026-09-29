//! Bounded, unassociated sRGB colors. Alpha/compositing are deliberately separate.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Color(pub(crate) [f32; 3]);
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MixError {
    NonFinite,
    OutOfRange,
    InvalidWeights,
    InvalidLut,
}
impl core::fmt::Display for MixError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(f, "{self:?}")
    }
}
impl std::error::Error for MixError {}
impl Color {
    pub fn srgb8(r: u8, g: u8, b: u8) -> Self {
        Self([r as f32 / 255., g as f32 / 255., b as f32 / 255.])
    }
    /// Checked sRGB input in [0,1]. Rejects NaN, infinity, HDR, and negative values.
    pub fn srgb(r: f32, g: f32, b: f32) -> Result<Self, MixError> {
        let c = [r, g, b];
        if c.iter().any(|x| !x.is_finite()) {
            return Err(MixError::NonFinite);
        }
        if c.iter().any(|x| !(0. ..=1.).contains(x)) {
            return Err(MixError::OutOfRange);
        }
        Ok(Self(c))
    }
    pub const fn channels(self) -> [f32; 3] {
        self.0
    }
    pub fn to_srgb8(self) -> [u8; 3] {
        self.0.map(|x| (255. * x).round() as u8)
    }
    pub fn linear(self) -> [f64; 3] {
        self.0.map(|x| crate::conversion::srgb_to_linear(x as f64))
    }
    pub fn from_linear_gamut_mapped(x: [f64; 3]) -> Self {
        let y = crate::conversion::gamut_map(x);
        Self(y.map(|v| crate::conversion::linear_to_srgb(v) as f32))
    }
}
