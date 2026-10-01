//! Opt-in, palette-bound material recipes (1-16 paints).
//!
//! The built-in palette is independently synthetic; callers can import optical
//! definitions with `PaletteN`. Recipes have no RGB residual. Four-paint LUTs
//! remain an optional accelerator in `palette_lut`.
//! See `docs/palette-reference.md` for the optical model and provenance.
//!
//! ```
//! use ochrell::palette::synthetic_four;
//! let palette = synthetic_four();
//! let yellow = palette.paint("yellow").unwrap();
//! let blue = palette.paint("blue").unwrap();
//! let green = yellow.interpolate(blue, 0.5).unwrap();
//! let saved = green.to_le_bytes();
//! let restored = palette.recipe_from_bytes(&saved).unwrap();
//! assert_eq!(green.decode(), restored.decode());
//! ```

use crate::{palette_generated as data, Color};
use std::borrow::Cow;
#[path = "palette_package.rs"]
mod package;
#[path = "palette_window.rs"]
mod window;

/// Coefficients must have been calibrated consistently with the chosen amount basis.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum AmountBasis {
    Relative,
    Mass,
    Volume,
}

/// Human-readable identity and attribution stored with custom optical data.
pub struct PaletteMetadataN<'a, const N: usize> {
    pub id: &'a str,
    pub paint_names: [&'a str; N],
    pub amount_basis: AmountBasis,
    pub provenance: &'a str,
}

const BUILTIN_PROVENANCE: &str = "Original independent synthetic smoothstep spectra; CIE-derived D65 projection. See data/README.md.";

/// Number of paints in the backwards-compatible built-in palette.
pub const PAINT_COUNT: usize = 4;
/// Bound package sizes and matching work, including eight-, ten- and sixteen-paint palettes.
pub const MAX_PAINTS: usize = 16;
/// Original four-paint API and storage remain compatible.
pub type Palette = PaletteN<4>;
/// Metadata for the original four-paint API.
pub type PaletteMetadata<'a> = PaletteMetadataN<'a, 4>;
/// Recipe for the original four-paint API.
pub type Recipe<'a> = RecipeN<'a, 4>;
pub const SAMPLES: usize = 81;
pub const START_NM: usize = 380;
pub const STEP_NM: usize = 5;
/// Four-byte format marker, 32-byte palette fingerprint, four little-endian f64s.
pub const RECIPE_BYTES: usize = 68;
const RECIPE_MAGIC: &[u8; 4] = b"OPR1";
const SUM_TOLERANCE: f64 = 1e-12;

/// Failures are distinct from the existing RGB mixer's error contract.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PaletteError {
    UnknownPaint,
    InvalidAmounts,
    InvalidFraction,
    PaletteMismatch,
    InvalidRecipe,
    InvalidFormat,
    InvalidPalette,
    UnsupportedGrid,
    InvalidChecksum,
    InvalidTarget,
    InvalidMetric,
}

impl core::fmt::Display for PaletteError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.write_str(match self {
            Self::UnknownPaint => "paint name is not present in this palette",
            Self::InvalidAmounts => "amounts must be finite, nonnegative and not all zero",
            Self::InvalidFraction => "mixing fraction must be finite and in [0, 1]",
            Self::PaletteMismatch => "recipe belongs to a different palette",
            Self::InvalidRecipe => {
                "recipe must contain finite nonnegative proportions summing to one"
            }
            Self::InvalidFormat => "invalid recipe format, paint count or payload length",
            Self::InvalidPalette => "invalid palette metadata or optical coefficients",
            Self::UnsupportedGrid => "unsupported spectral grid or CIE/D65 projection (expected 81 bands at 380/5 nm or 31 at 400/10 nm)",
            Self::InvalidChecksum => "palette package checksum does not match",
            Self::InvalidTarget => "target linear RGB must be finite and in [0, 1]",
            Self::InvalidMetric => "color metric produced a nonfinite value",
        })
    }
}
impl std::error::Error for PaletteError {}

/// An immutable palette with N material slots; N must be in 1..=MAX_PAINTS.
///
/// Its generated fingerprint identifies paint order, optical coefficients and
/// color projection. Changing the reference requires a new identity.
///
/// ```
/// use ochrell::{palette::PaletteN, palette_match::ColorMatcherN, Color};
/// # fn eight_paints(bytes: &[u8]) -> Result<(), Box<dyn std::error::Error>> {
/// let palette = PaletteN::<8>::from_bytes(bytes)?;
/// let mixture = palette.recipe([1., 2., 0., 0., 1., 0., 0., 4.])?;
/// let restored = palette.recipe_from_bytes(&mixture.to_bytes())?;
/// assert_eq!(mixture.decode(), restored.decode());
/// let matcher = ColorMatcherN::new(&palette)?;
/// let found = matcher.match_color(Color::srgb8(80, 170, 120))?;
/// println!("{:?}", found.recipe.proportions());
/// # Ok(()) }
/// ```
#[derive(Clone, Debug)]
pub struct PaletteN<const N: usize, const B: usize = SAMPLES> {
    id: Cow<'static, str>,
    fingerprint: [u8; 32],
    names: [Cow<'static, str>; N],
    amount_basis: AmountBasis,
    provenance: Cow<'static, str>,
    k: [[f64; N]; B],
    s: [[f64; N]; B],
    rgb: [[f64; 3]; B],
    pair_controls: Vec<[f64; 4]>,
}

static SYNTHETIC_FOUR: Palette = Palette {
    id: Cow::Borrowed(data::ID),
    fingerprint: data::FINGERPRINT,
    names: [
        Cow::Borrowed(data::NAMES[0]),
        Cow::Borrowed(data::NAMES[1]),
        Cow::Borrowed(data::NAMES[2]),
        Cow::Borrowed(data::NAMES[3]),
    ],
    amount_basis: AmountBasis::Relative,
    provenance: Cow::Borrowed(BUILTIN_PROVENANCE),
    k: data::K,
    s: data::S,
    rgb: data::RGB,
    pair_controls: Vec::new(),
};

/// The built-in independent synthetic reference. No allocation or startup fit.
pub fn synthetic_four() -> &'static Palette {
    &SYNTHETIC_FOUR
}

impl<const N: usize, const B: usize> PaletteN<N, B> {
    /// Supported grids: 81 bands at 380-780/5 nm, or 31 at 400-700/10 nm.
    pub fn spectral_grid(&self) -> (usize, usize, usize) {
        if B == 31 {
            (400, 10, B)
        } else {
            (START_NM, STEP_NM, B)
        }
    }
    pub fn pair_controls(&self) -> &[[f64; 4]] {
        &self.pair_controls
    }
    pub fn display_projection(&self) -> &[[f64; 3]; B] {
        &self.rgb
    }
    pub fn paint_count(&self) -> usize {
        N
    }

    pub fn id(&self) -> &str {
        &self.id
    }

    pub fn fingerprint(&self) -> [u8; 32] {
        self.fingerprint
    }

    /// Order used by `recipe` and stored concentration arrays.
    pub fn paint_names(&self) -> [&str; N] {
        std::array::from_fn(|i| self.names[i].as_ref())
    }
    pub fn amount_basis(&self) -> AmountBasis {
        self.amount_basis
    }
    pub fn provenance(&self) -> &str {
        &self.provenance
    }
    pub fn absorption(&self) -> &[[f64; N]; B] {
        &self.k
    }
    pub fn scattering(&self) -> &[[f64; N]; B] {
        &self.s
    }

    pub fn paint(&self, name: &str) -> Result<RecipeN<'_, N, B>, PaletteError> {
        let index = self
            .names
            .iter()
            .position(|candidate| *candidate == name)
            .ok_or(PaletteError::UnknownPaint)?;
        let mut proportions = [0.; N];
        proportions[index] = 1.;
        Ok(RecipeN {
            palette: self,
            proportions,
        })
    }

    /// Normalize amounts in `paint_names()` order without changing materials.
    ///
    /// Units are relative synthetic amounts for the built-in palette, not grams
    /// or paint volume. Zero components are allowed, but the total must be positive.
    pub fn recipe(&self, amounts: [f64; N]) -> Result<RecipeN<'_, N, B>, PaletteError> {
        Ok(RecipeN {
            palette: self,
            proportions: normalize(amounts)?,
        })
    }

    /// Restore an exact recipe; never normalize, repair or remap saved values.
    ///
    /// The fingerprint is a compatibility identifier, not a checksum of the
    /// recipe payload. Hosts needing corruption detection must checksum storage.
    pub fn recipe_from_bytes(&self, bytes: &[u8]) -> Result<RecipeN<'_, N, B>, PaletteError> {
        let offset = if N == 4 { 36 } else { 40 };
        if bytes.len() != offset + 8 * N {
            return Err(PaletteError::InvalidFormat);
        }
        let fingerprint_start = if N == 4 {
            if &bytes[..4] != RECIPE_MAGIC {
                return Err(PaletteError::InvalidFormat);
            }
            4
        } else {
            if &bytes[..4] != b"OPR2"
                || u32::from_le_bytes(bytes[4..8].try_into().unwrap()) as usize != N
            {
                return Err(PaletteError::InvalidFormat);
            }
            8
        };
        if bytes[fingerprint_start..offset] != self.fingerprint {
            return Err(PaletteError::PaletteMismatch);
        }
        let proportions = std::array::from_fn(|i| {
            f64::from_le_bytes(
                bytes[offset + 8 * i..offset + 8 * (i + 1)]
                    .try_into()
                    .unwrap(),
            )
        });
        if proportions
            .iter()
            .any(|v| !v.is_finite() || !(0. ..=1.).contains(v))
            || (proportions.iter().sum::<f64>() - 1.).abs() > SUM_TOLERANCE
        {
            return Err(PaletteError::InvalidRecipe);
        }
        Ok(RecipeN {
            palette: self,
            proportions,
        })
    }
}

/// A persistent recipe bound to an immutable palette; no RGB round trip.
///
/// This f64 reference includes a palette borrow. It is not a promised compact
/// canvas layout. Hosts store paint amount, coverage and transport separately.
#[derive(Clone, Copy, Debug)]
pub struct RecipeN<'a, const N: usize, const B: usize = SAMPLES> {
    palette: &'a PaletteN<N, B>,
    proportions: [f64; N],
}

impl<'a, const N: usize, const B: usize> RecipeN<'a, N, B> {
    pub fn palette(&self) -> &'a PaletteN<N, B> {
        self.palette
    }

    pub fn proportions(&self) -> [f64; N] {
        self.proportions
    }

    /// Checked fraction of `other`; exact endpoints retain the original state.
    pub fn interpolate(self, other: Self, t: f64) -> Result<Self, PaletteError> {
        self.check_palette(other)?;
        if !t.is_finite() || !(0. ..=1.).contains(&t) {
            return Err(PaletteError::InvalidFraction);
        }
        if t == 0. {
            return Ok(self);
        }
        if t == 1. {
            return Ok(other);
        }
        self.palette.recipe(std::array::from_fn(|i| {
            self.proportions[i] * (1. - t) + other.proportions[i] * t
        }))
    }

    /// Combine recipes using their material amounts. For grouped mixtures pass
    /// each group's total amount, not one vote per group.
    ///
    /// Zero amounts are ignored numerically; every recipe must still belong to
    /// the same palette. Scaling avoids overflow in a naive sum of large amounts.
    pub fn weighted(items: &[(Self, f64)]) -> Result<Self, PaletteError> {
        let first = items.first().ok_or(PaletteError::InvalidAmounts)?.0;
        let mut scale: f64 = 0.;
        for (recipe, amount) in items {
            first.check_palette(*recipe)?;
            if !amount.is_finite() || *amount < 0. {
                return Err(PaletteError::InvalidAmounts);
            }
            scale = scale.max(*amount);
        }
        if scale == 0. {
            return Err(PaletteError::InvalidAmounts);
        }
        let total: f64 = items.iter().map(|(_, amount)| amount / scale).sum();
        let mut proportions = [0.; N];
        for (recipe, amount) in items {
            let fraction = (amount / scale) / total;
            for (value, source) in proportions.iter_mut().zip(recipe.proportions) {
                *value += fraction * source;
            }
        }
        first.palette.recipe(proportions)
    }

    fn check_palette(self, other: Self) -> Result<(), PaletteError> {
        if self.palette.fingerprint == other.palette.fingerprint {
            Ok(())
        } else {
            Err(PaletteError::PaletteMismatch)
        }
    }

    /// K-M reflectance with any declared empirical pair correction, on this grid.
    pub fn reflectance(&self) -> [f64; B] {
        let mut controls = [0.; 4];
        if !self.palette.pair_controls.is_empty() {
            let mut pair = 0;
            for i in 0..N {
                for j in i + 1..N {
                    let weight = 4. * self.proportions[i] * self.proportions[j];
                    for (a, value) in controls.iter_mut().zip(self.palette.pair_controls[pair]) {
                        *a += weight * value;
                    }
                    pair += 1;
                }
            }
        }
        std::array::from_fn(|band| {
            let mut k = 0.;
            let mut s = 0.;
            for paint in 0..N {
                k += self.proportions[paint] * self.palette.k[band][paint];
                s += self.proportions[paint] * self.palette.s[band][paint];
            }
            let r = crate::kubelka_munk::reflectance(k / s);
            if self.palette.pair_controls.is_empty() {
                return r;
            }
            let t = band as f64 / (B - 1) as f64;
            let basis = [
                (1. - t).powi(3),
                3. * t * (1. - t).powi(2),
                3. * t * t * (1. - t),
                t.powi(3),
            ];
            let shift: f64 = controls.iter().zip(basis).map(|(a, b)| a * b).sum();
            if shift == 0. || r == 0. || r == 1. {
                return r;
            }
            let x = r.ln() - (-r).ln_1p() + shift;
            if x >= 0. {
                1. / (1. + (-x).exp())
            } else {
                let e = x.exp();
                e / (1. + e)
            }
        })
    }

    /// Raw linear sRGB for diagnostics; values may be outside display gamut.
    pub fn decode_linear(&self) -> [f64; 3] {
        let mut rgb = [0.; 3];
        for (r, weights) in self.reflectance().iter().zip(&self.palette.rgb) {
            for (value, weight) in rgb.iter_mut().zip(weights) {
                *value += r * weight;
            }
        }
        rgb
    }

    /// Display sRGB through the existing neutral-axis gamut map. This does not
    /// modify the recipe or add a color residual to its material.
    pub fn decode(&self) -> Color {
        Color::from_linear_gamut_mapped(self.decode_linear())
    }

    /// Versioned recipe payload. Four-paint recipes preserve OPR1 bytes;
    /// other sizes use OPR2 with an explicit count and palette identity.
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut out = Vec::with_capacity(40 + 8 * N);
        out.extend_from_slice(if N == 4 { RECIPE_MAGIC } else { b"OPR2" });
        if N != 4 {
            out.extend_from_slice(&(N as u32).to_le_bytes());
        }
        out.extend_from_slice(&self.palette.fingerprint);
        for v in self.proportions {
            out.extend_from_slice(&v.to_le_bytes());
        }
        out
    }
}

impl<const B: usize> RecipeN<'_, 4, B> {
    /// Original fixed-size OPR1 API, unchanged for four-paint callers.
    pub fn to_le_bytes(&self) -> [u8; RECIPE_BYTES] {
        let mut out = [0; RECIPE_BYTES];
        out[..4].copy_from_slice(RECIPE_MAGIC);
        out[4..36].copy_from_slice(&self.palette.fingerprint);
        for (i, value) in self.proportions.iter().enumerate() {
            out[36 + i * 8..44 + i * 8].copy_from_slice(&value.to_le_bytes());
        }
        out
    }
}

fn normalize<const N: usize>(amounts: [f64; N]) -> Result<[f64; N], PaletteError> {
    if amounts.iter().any(|v| !v.is_finite() || *v < 0.) {
        return Err(PaletteError::InvalidAmounts);
    }
    let scale = amounts.iter().copied().fold(0., f64::max);
    if scale == 0. {
        return Err(PaletteError::InvalidAmounts);
    }
    let scaled = amounts.map(|v| v / scale);
    let total: f64 = scaled.iter().sum();
    Ok(scaled.map(|v| v / total))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn constant_optics_have_analytic_reflectance_and_strength() {
        // A and B have the same pure K/S=1 but B has 100x optical strength.
        // Their equal-amount white tints must differ even though pure colors match.
        let palette = Palette {
            id: Cow::Borrowed("analytic-test"),
            fingerprint: [0; 32],
            names: ["a", "b", "white", "duplicate-white"].map(Cow::Borrowed),
            amount_basis: AmountBasis::Relative,
            provenance: Cow::Borrowed("Analytic test fixture"),
            k: [[1., 100., 0., 0.]; SAMPLES],
            s: [[1., 100., 1., 1.]; SAMPLES],
            rgb: data::RGB,
            pair_controls: Vec::new(),
        };
        let a = palette.paint("a").unwrap();
        let b = palette.paint("b").unwrap();
        let white = palette.paint("white").unwrap();
        let expected = 2. - 3_f64.sqrt();
        for r in a.reflectance() {
            assert!((r - expected).abs() < 1e-15);
        }
        assert_eq!(a.reflectance(), b.reflectance());
        let light = a.interpolate(white, 0.5).unwrap();
        let strong = b.interpolate(white, 0.5).unwrap();
        assert!((light.reflectance()[0] - (1.5 - 1.25_f64.sqrt())).abs() < 1e-15);
        assert!(light.reflectance()[0] > strong.reflectance()[0]);
        assert!(a
            .interpolate(synthetic_four().paint("red").unwrap(), 0.)
            .is_err());
        assert!(
            Recipe::weighted(&[(a, 1.), (synthetic_four().paint("red").unwrap(), 0.)]).is_err()
        );
        assert_eq!(
            synthetic_four()
                .recipe_from_bytes(&a.to_le_bytes())
                .unwrap_err(),
            PaletteError::PaletteMismatch
        );
    }
}
