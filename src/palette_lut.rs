//! Prepared, palette-bound forward decoding. Material recipes remain unchanged.
//!
//! The table interpolates raw linear RGB; gamut mapping happens afterwards.
//! See `docs/palette-lut-plan.md` for coordinates and experimental error budgets.
//!
//! ```
//! use ochrell::{palette::synthetic_four, palette_lut::PaletteLut};
//! let palette = synthetic_four();
//! let lut = PaletteLut::build(palette, 65).unwrap();
//! let paint = palette.recipe([1., 0., 1., 0.]).unwrap();
//! let color = lut.decode(&paint).unwrap();
//! let bytes = lut.to_bytes();
//! let loaded = PaletteLut::from_bytes(palette, &bytes).unwrap();
//! assert_eq!(color, loaded.decode(&paint).unwrap());
//! ```

use crate::{
    palette::{Palette, Recipe},
    Color,
};
use std::borrow::Cow;

pub const MAX_RESOLUTION: usize = 129;
const HEADER: usize = 44;
const MAGIC: &[u8; 4] = b"OPL1";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LutMapping {
    /// Original cumulative coordinates. Retained as a comparison candidate.
    Uniform,
    /// Cosine-spaced cumulative coordinates. Retained as a comparison candidate.
    EdgeFocused,
    /// Square-root recipe coordinates, then a uniform cumulative grid.
    RecipeSqrt,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LutError {
    InvalidResolution,
    PaletteMismatch,
    InvalidFormat,
    InvalidChecksum,
    NonFinite,
    InvalidKnots,
}

impl core::fmt::Display for LutError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        f.write_str(match self {
            Self::InvalidResolution => "palette LUT resolution must be between 2 and 129",
            Self::PaletteMismatch => "palette LUT and recipe identities do not match",
            Self::InvalidFormat => "invalid OPL1 table format or length",
            Self::InvalidChecksum => "palette LUT checksum does not match",
            Self::NonFinite => "palette LUT contains a nonfinite channel",
            Self::InvalidKnots => "palette LUT knots must increase strictly from zero to one",
        })
    }
}
impl std::error::Error for LutError {}

/// Explicitly prepared forward decoder. Building allocates and evaluates the
/// reference; querying is allocation-free and does not alter the recipe.
#[derive(Debug)]
pub struct PaletteLut<'a> {
    palette: Cow<'a, Palette>,
    resolution: usize,
    mapping: LutMapping,
    knots: Vec<f64>,
    values: Vec<[f32; 3]>,
}

impl<'a> PaletteLut<'a> {
    pub fn build(palette: &'a Palette, resolution: usize) -> Result<Self, LutError> {
        Self::build_with_mapping(palette, resolution, LutMapping::RecipeSqrt)
    }

    pub fn build_with_mapping(
        palette: &'a Palette,
        resolution: usize,
        mapping: LutMapping,
    ) -> Result<Self, LutError> {
        let count = node_count(resolution)?;
        let mut knots: Vec<_> = (0..resolution)
            .map(|i| {
                let t = i as f64 / (resolution - 1) as f64;
                match mapping {
                    LutMapping::Uniform | LutMapping::RecipeSqrt => t,
                    LutMapping::EdgeFocused => (1. - (std::f64::consts::PI * t).cos()) * 0.5,
                }
            })
            .collect();
        knots[0] = 0.;
        knots[resolution - 1] = 1.;
        let mut lut = Self {
            palette: Cow::Borrowed(palette),
            resolution,
            mapping,
            knots,
            values: vec![[0.; 3]; count],
        };
        for u in 0..resolution {
            for v in u..resolution {
                for w in v..resolution {
                    let coordinates = [
                        lut.knots[u],
                        lut.knots[v] - lut.knots[u],
                        lut.knots[w] - lut.knots[v],
                        1. - lut.knots[w],
                    ];
                    let amounts = if mapping == LutMapping::RecipeSqrt {
                        coordinates.map(|v| v * v)
                    } else {
                        coordinates
                    };
                    let recipe = palette
                        .recipe(amounts)
                        .expect("ordered grid produces a nonempty valid recipe");
                    let rgb = recipe.decode_linear().map(|value| value as f32);
                    if rgb.iter().any(|v| !v.is_finite()) {
                        return Err(LutError::NonFinite);
                    }
                    let index = lut.index([u, v, w]);
                    lut.values[index] = rgb;
                }
            }
        }
        Ok(lut)
    }

    pub fn resolution(&self) -> usize {
        self.resolution
    }
    /// Dense nodes and knots; excludes palette, Vec metadata and header.
    pub fn payload_bytes(&self) -> usize {
        self.values.len() * 12 + self.knots.len() * 8
    }
    pub fn mapping(&self) -> LutMapping {
        self.mapping
    }
    pub fn palette(&self) -> &Palette {
        &self.palette
    }
    /// Own the palette and table for hosts whose mixer must have a static lifetime.
    pub fn into_owned(self) -> PaletteLut<'static> {
        PaletteLut {
            palette: Cow::Owned(self.palette.into_owned()),
            resolution: self.resolution,
            mapping: self.mapping,
            knots: self.knots,
            values: self.values,
        }
    }

    pub fn decode_linear(&self, recipe: &Recipe<'_>) -> Result<[f64; 3], LutError> {
        if self.palette.fingerprint() != recipe.palette().fingerprint() {
            return Err(LutError::PaletteMismatch);
        }
        let original = recipe.proportions();
        let [a, b, c, d] = if self.mapping == LutMapping::RecipeSqrt {
            original.map(f64::sqrt)
        } else {
            original
        };
        // Accepted saved recipes may differ from unit sum by the reference's
        // tolerance. Normalize coordinates without mutating material bytes.
        let total = a + b + c + d;
        let coordinates = [a / total, (a + b) / total, (a + b + c) / total];
        let (base, fractions): ([usize; 3], [f64; 3]) = match self.mapping {
            LutMapping::Uniform | LutMapping::RecipeSqrt => {
                let scaled = coordinates.map(|v| v.clamp(0., 1.) * (self.resolution - 1) as f64);
                let base = scaled.map(|v| (v.floor() as usize).min(self.resolution - 2));
                (base, std::array::from_fn(|i| scaled[i] - base[i] as f64))
            }
            LutMapping::EdgeFocused => {
                let base = coordinates.map(|v| {
                    self.knots
                        .partition_point(|k| *k <= v)
                        .saturating_sub(1)
                        .min(self.resolution - 2)
                });
                let fractions = std::array::from_fn(|i| {
                    ((coordinates[i] - self.knots[base[i]])
                        / (self.knots[base[i] + 1] - self.knots[base[i]]))
                        .clamp(0., 1.)
                });
                (base, fractions)
            }
        };
        let mut order = [0, 1, 2];
        // Fixed three-element sorting network: descending fractional position.
        if fractions[order[0]] < fractions[order[1]] {
            order.swap(0, 1);
        }
        if fractions[order[1]] < fractions[order[2]] {
            order.swap(1, 2);
        }
        if fractions[order[0]] < fractions[order[1]] {
            order.swap(0, 1);
        }
        let [x, y, z] = order.map(|i| fractions[i]);
        let weights = [1. - x, x - y, y - z, z];
        let mut vertex = base;
        let mut output = [0.; 3];
        for (corner, weight) in weights.into_iter().enumerate() {
            if corner > 0 {
                vertex[order[corner - 1]] += 1;
            }
            let value = self.values[self.index(vertex)];
            for ch in 0..3 {
                output[ch] += weight * value[ch] as f64;
            }
        }
        Ok(output)
    }

    pub fn decode(&self, recipe: &Recipe<'_>) -> Result<Color, LutError> {
        Ok(Color::from_linear_gamut_mapped(self.decode_linear(recipe)?))
    }

    fn index(&self, [u, v, w]: [usize; 3]) -> usize {
        (u * self.resolution + v) * self.resolution + w
    }

    /// OPL1: magic, palette SHA-256, u32 resolution, u32 mapping (0/1/2), f64 knots, f32 RGB nodes,
    /// then CRC-32/ISO-HDLC of all preceding bytes. Cube order is u,v,w (w fastest).
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut out = Vec::with_capacity(HEADER + self.payload_bytes() + 4);
        out.extend_from_slice(MAGIC);
        out.extend_from_slice(&self.palette.fingerprint());
        out.extend_from_slice(&(self.resolution as u32).to_le_bytes());
        out.extend_from_slice(
            &(match self.mapping {
                LutMapping::Uniform => 0_u32,
                LutMapping::EdgeFocused => 1,
                LutMapping::RecipeSqrt => 2,
            })
            .to_le_bytes(),
        );
        for value in &self.knots {
            out.extend_from_slice(&value.to_le_bytes());
        }
        for row in &self.values {
            for value in row {
                out.extend_from_slice(&value.to_le_bytes());
            }
        }
        out.extend_from_slice(&crc32(&out).to_le_bytes());
        out
    }

    pub fn from_bytes(palette: &'a Palette, bytes: &[u8]) -> Result<Self, LutError> {
        if bytes.len() < HEADER + 4 || &bytes[..4] != MAGIC {
            return Err(LutError::InvalidFormat);
        }
        if bytes[4..36] != palette.fingerprint() {
            return Err(LutError::PaletteMismatch);
        }
        let resolution = u32::from_le_bytes(bytes[36..40].try_into().unwrap()) as usize;
        let count = node_count(resolution)?;
        let mapping = match u32::from_le_bytes(bytes[40..44].try_into().unwrap()) {
            0 => LutMapping::Uniform,
            1 => LutMapping::EdgeFocused,
            2 => LutMapping::RecipeSqrt,
            _ => return Err(LutError::InvalidFormat),
        };
        let data_start = HEADER + resolution * 8;
        let expected = data_start + count * 12 + 4;
        if bytes.len() != expected {
            return Err(LutError::InvalidFormat);
        }
        let checksum = u32::from_le_bytes(bytes[expected - 4..].try_into().unwrap());
        if crc32(&bytes[..expected - 4]) != checksum {
            return Err(LutError::InvalidChecksum);
        }
        let knots: Vec<_> = bytes[HEADER..data_start]
            .chunks_exact(8)
            .map(|v| f64::from_le_bytes(v.try_into().unwrap()))
            .collect();
        if knots[0] != 0.
            || knots[resolution - 1] != 1.
            || knots.iter().any(|v| !v.is_finite())
            || knots.windows(2).any(|p| p[0] >= p[1])
        {
            return Err(LutError::InvalidKnots);
        }
        if mapping != LutMapping::EdgeFocused
            && knots
                .iter()
                .enumerate()
                .any(|(i, v)| *v != i as f64 / (resolution - 1) as f64)
        {
            return Err(LutError::InvalidKnots);
        }
        let mut values = Vec::with_capacity(count);
        for chunk in bytes[data_start..expected - 4].chunks_exact(12) {
            let row = std::array::from_fn(|i| {
                f32::from_le_bytes(chunk[i * 4..i * 4 + 4].try_into().unwrap())
            });
            if row.iter().any(|v| !v.is_finite()) {
                return Err(LutError::NonFinite);
            }
            values.push(row);
        }
        Ok(Self {
            palette: Cow::Borrowed(palette),
            resolution,
            mapping,
            knots,
            values,
        })
    }
}

fn node_count(resolution: usize) -> Result<usize, LutError> {
    if !(2..=MAX_RESOLUTION).contains(&resolution) {
        return Err(LutError::InvalidResolution);
    }
    Ok(resolution * resolution * resolution)
}

fn crc32(bytes: &[u8]) -> u32 {
    let mut crc = !0_u32;
    for byte in bytes {
        crc ^= *byte as u32;
        for _ in 0..8 {
            crc = (crc >> 1) ^ (0xedb88320_u32 & (0_u32.wrapping_sub(crc & 1)));
        }
    }
    !crc
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::palette::synthetic_four;

    #[test]
    fn affine_interpolation_covers_the_ordered_simplex() {
        for mapping in [
            LutMapping::Uniform,
            LutMapping::EdgeFocused,
            LutMapping::RecipeSqrt,
        ] {
            let mut lut = PaletteLut::build_with_mapping(synthetic_four(), 5, mapping).unwrap();
            for u in 0..5 {
                for v in u..5 {
                    for w in v..5 {
                        let index = lut.index([u, v, w]);
                        lut.values[index] = [
                            (lut.knots[u] - 0.25) as f32,
                            (lut.knots[v] / 2. + 0.5) as f32,
                            (lut.knots[w] + 0.25) as f32,
                        ];
                    }
                }
            }
            for a in 0..=13 {
                for b in 0..=13 - a {
                    for c in 0..=13 - a - b {
                        let recipe = synthetic_four()
                            .recipe([a as f64, b as f64, c as f64, (13 - a - b - c) as f64])
                            .unwrap();
                        let mut p = recipe.proportions();
                        if mapping == LutMapping::RecipeSqrt {
                            p = p.map(f64::sqrt);
                            let sum = p.iter().sum::<f64>();
                            p = p.map(|v| v / sum);
                        }
                        let rgb = lut.decode_linear(&recipe).unwrap();
                        let expected = [
                            p[0] - 0.25,
                            (p[0] + p[1]) / 2. + 0.5,
                            p[0] + p[1] + p[2] + 0.25,
                        ];
                        for (a, b) in rgb.into_iter().zip(expected) {
                            assert!((a - b).abs() < 1e-7);
                        }
                    }
                }
            }
        }
    }

    #[test]
    fn invalid_knots_are_rejected_even_with_a_valid_checksum() {
        let p = synthetic_four();
        for mapping in [
            LutMapping::Uniform,
            LutMapping::EdgeFocused,
            LutMapping::RecipeSqrt,
        ] {
            let original = PaletteLut::build_with_mapping(p, 3, mapping)
                .unwrap()
                .to_bytes();
            for bad in [0., 1., f64::NAN, f64::INFINITY] {
                let mut bytes = original.clone();
                bytes[HEADER + 8..HEADER + 16].copy_from_slice(&bad.to_le_bytes());
                let end = bytes.len() - 4;
                let checksum = crc32(&bytes[..end]).to_le_bytes();
                bytes[end..].copy_from_slice(&checksum);
                assert_eq!(
                    PaletteLut::from_bytes(p, &bytes).unwrap_err(),
                    LutError::InvalidKnots
                );
            }
        }
    }

    #[test]
    fn import_checks_checksum_and_nonfinite_payloads() {
        assert_eq!(crc32(b"123456789"), 0xcbf43926);
        let palette = synthetic_four();
        let mut bytes = PaletteLut::build(palette, 2).unwrap().to_bytes();
        bytes[HEADER + 16..HEADER + 20].copy_from_slice(&f32::NAN.to_le_bytes());
        assert_eq!(
            PaletteLut::from_bytes(palette, &bytes).unwrap_err(),
            LutError::InvalidChecksum
        );
        let end = bytes.len() - 4;
        let checksum = crc32(&bytes[..end]).to_le_bytes();
        bytes[end..].copy_from_slice(&checksum);
        assert_eq!(
            PaletteLut::from_bytes(palette, &bytes).unwrap_err(),
            LutError::NonFinite
        );
    }
}
