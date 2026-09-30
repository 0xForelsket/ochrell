//! Opt-in, palette-bound four-material reference mixing.
//!
//! This first version exposes an independent synthetic palette, not measured
//! paint or a replacement for the root RGB mixer. It has no LUT or RGB residual.
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

/// Coefficients must have been calibrated consistently with the chosen amount basis.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum AmountBasis {
    Relative,
    Mass,
    Volume,
}

/// Human-readable identity and attribution stored with custom optical data.
pub struct PaletteMetadata<'a> {
    pub id: &'a str,
    pub paint_names: [&'a str; PAINT_COUNT],
    pub amount_basis: AmountBasis,
    pub provenance: &'a str,
}

const BUILTIN_PROVENANCE: &str = "Original independent synthetic smoothstep spectra; CIE-derived D65 projection. See data/README.md.";

pub const PAINT_COUNT: usize = 4;
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
                "recipe must contain four finite nonnegative proportions summing to one"
            }
            Self::InvalidFormat => "expected an OPR1 recipe with exactly 68 bytes",
            Self::InvalidPalette => "invalid palette metadata or optical coefficients",
            Self::UnsupportedGrid => "palette requires 81 bands at 380-780 nm / 5 nm and the supported CIE/D65 projection",
            Self::InvalidChecksum => "palette package checksum does not match",
            Self::InvalidTarget => "target linear RGB must be finite and in [0, 1]",
            Self::InvalidMetric => "color metric produced a nonfinite value",
        })
    }
}
impl std::error::Error for PaletteError {}

/// An immutable, owned or built-in four-material reference definition.
///
/// Its generated fingerprint identifies paint order, optical coefficients and
/// color projection. Changing the reference requires a new identity.
#[derive(Clone, Debug)]
pub struct Palette {
    id: Cow<'static, str>,
    fingerprint: [u8; 32],
    names: [Cow<'static, str>; PAINT_COUNT],
    amount_basis: AmountBasis,
    provenance: Cow<'static, str>,
    k: [[f64; PAINT_COUNT]; SAMPLES],
    s: [[f64; PAINT_COUNT]; SAMPLES],
    rgb: [[f64; 3]; SAMPLES],
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
};

/// The built-in independent synthetic reference. No allocation or startup fit.
pub fn synthetic_four() -> &'static Palette {
    &SYNTHETIC_FOUR
}

impl Palette {
    pub fn id(&self) -> &str {
        &self.id
    }

    pub fn fingerprint(&self) -> [u8; 32] {
        self.fingerprint
    }

    /// Order used by `recipe` and stored concentration arrays.
    pub fn paint_names(&self) -> [&str; PAINT_COUNT] {
        std::array::from_fn(|i| self.names[i].as_ref())
    }
    pub fn amount_basis(&self) -> AmountBasis {
        self.amount_basis
    }
    pub fn provenance(&self) -> &str {
        &self.provenance
    }
    pub fn absorption(&self) -> &[[f64; PAINT_COUNT]; SAMPLES] {
        &self.k
    }
    pub fn scattering(&self) -> &[[f64; PAINT_COUNT]; SAMPLES] {
        &self.s
    }

    pub fn paint(&self, name: &str) -> Result<Recipe<'_>, PaletteError> {
        let index = self
            .names
            .iter()
            .position(|candidate| *candidate == name)
            .ok_or(PaletteError::UnknownPaint)?;
        let mut proportions = [0.; PAINT_COUNT];
        proportions[index] = 1.;
        Ok(Recipe {
            palette: self,
            proportions,
        })
    }

    /// Normalize amounts in `paint_names()` order without changing materials.
    ///
    /// Units are relative synthetic amounts for the built-in palette, not grams
    /// or paint volume. Zero components are allowed, but the total must be positive.
    pub fn recipe(&self, amounts: [f64; PAINT_COUNT]) -> Result<Recipe<'_>, PaletteError> {
        Ok(Recipe {
            palette: self,
            proportions: normalize(amounts)?,
        })
    }

    /// Restore an exact recipe; never normalize, repair or remap saved values.
    ///
    /// The fingerprint is a compatibility identifier, not a checksum of the
    /// recipe payload. Hosts needing corruption detection must checksum storage.
    pub fn recipe_from_bytes(&self, bytes: &[u8]) -> Result<Recipe<'_>, PaletteError> {
        if bytes.len() != RECIPE_BYTES || &bytes[..4] != RECIPE_MAGIC {
            return Err(PaletteError::InvalidFormat);
        }
        if bytes[4..36] != self.fingerprint {
            return Err(PaletteError::PaletteMismatch);
        }
        let proportions = std::array::from_fn(|i| {
            f64::from_le_bytes(bytes[36 + 8 * i..44 + 8 * i].try_into().unwrap())
        });
        if proportions
            .iter()
            .any(|v| !v.is_finite() || !(0. ..=1.).contains(v))
            || (proportions.iter().sum::<f64>() - 1.).abs() > SUM_TOLERANCE
        {
            return Err(PaletteError::InvalidRecipe);
        }
        Ok(Recipe {
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
pub struct Recipe<'a> {
    palette: &'a Palette,
    proportions: [f64; PAINT_COUNT],
}

impl<'a> Recipe<'a> {
    pub fn palette(&self) -> &'a Palette {
        self.palette
    }

    pub fn proportions(&self) -> [f64; PAINT_COUNT] {
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
        let mut proportions = [0.; PAINT_COUNT];
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

    /// Infinite-thickness reflectance on the declared reference grid.
    pub fn reflectance(&self) -> [f64; SAMPLES] {
        std::array::from_fn(|band| {
            let mut k = 0.;
            let mut s = 0.;
            for paint in 0..PAINT_COUNT {
                k += self.proportions[paint] * self.palette.k[band][paint];
                s += self.proportions[paint] * self.palette.s[band][paint];
            }
            crate::kubelka_munk::reflectance(k / s)
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

    /// Portable recipe payload, including format and exact palette identity.
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

fn normalize(amounts: [f64; PAINT_COUNT]) -> Result<[f64; PAINT_COUNT], PaletteError> {
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
