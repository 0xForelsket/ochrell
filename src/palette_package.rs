//! Checked optical packages: OPP1/2 compatibility and OPP3 native-window models.
use super::*;
const MAX_PACKAGE_BYTES: usize = 65_536;

fn projection<const B: usize>() -> Result<[[f64; 3]; B], PaletteError> {
    match B {
        81 => Ok(std::array::from_fn(|i| data::RGB[i])),
        31 => Ok(std::array::from_fn(|i| window::RGB[i])),
        _ => Err(PaletteError::UnsupportedGrid),
    }
}

impl<const N: usize, const B: usize> PaletteN<N, B> {
    /// Import optics on a supported grid. K is in [0,1e100], S in [1e-100,1e100].
    /// B=81 uses 380-780/5 nm; B=31 uses a windowed 400-700/10 nm preview.
    pub fn from_optics(
        metadata: PaletteMetadataN<'_, N>,
        k: [[f64; N]; B],
        s: [[f64; N]; B],
    ) -> Result<Self, PaletteError> {
        Self::from_optics_with_pair_correction(metadata, k, s, Vec::new())
    }

    /// Optional empirical reflectance-logit corrections, not physical K/S.
    /// Four cubic Bernstein controls per pair, ordered (0,1),(0,2),...,(N-2,N-1),
    /// each in [-0.8,0.8]. Empty controls select plain opaque K-M.
    pub fn from_optics_with_pair_correction(
        metadata: PaletteMetadataN<'_, N>,
        k: [[f64; N]; B],
        s: [[f64; N]; B],
        pair_controls: Vec<[f64; 4]>,
    ) -> Result<Self, PaletteError> {
        if !(1..=MAX_PAINTS).contains(&N) {
            return Err(PaletteError::InvalidPalette);
        }
        let rgb = projection::<B>()?;
        let text_ok = |s: &str, max: usize| {
            !s.trim().is_empty() && s.len() <= max && !s.chars().any(char::is_control)
        };
        if !text_ok(metadata.id, 128)
            || !text_ok(metadata.provenance, 4096)
            || metadata.paint_names.iter().any(|n| !text_ok(n, 64))
            || (0..N)
                .any(|i| (i + 1..N).any(|j| metadata.paint_names[i] == metadata.paint_names[j]))
            || k.iter()
                .flatten()
                .any(|v| !v.is_finite() || !(0. ..=1e100).contains(v))
            || s.iter()
                .flatten()
                .any(|v| !v.is_finite() || !(1e-100..=1e100).contains(v))
            || (!pair_controls.is_empty() && pair_controls.len() != N * (N - 1) / 2)
            || pair_controls
                .iter()
                .flatten()
                .any(|v| !v.is_finite() || !(-0.8..=0.8).contains(v))
        {
            return Err(PaletteError::InvalidPalette);
        }
        let mut p = Self {
            id: Cow::Owned(metadata.id.to_owned()),
            names: metadata.paint_names.map(|s| Cow::Owned(s.to_owned())),
            amount_basis: metadata.amount_basis,
            provenance: Cow::Owned(metadata.provenance.to_owned()),
            k,
            s,
            rgb,
            pair_controls,
            fingerprint: [0; 32],
        };
        let builtin = synthetic_four();
        p.fingerprint = if N == 4
            && B == 81
            && p.pair_controls.is_empty()
            && p.id == builtin.id
            && p.names.iter().eq(builtin.names.iter())
            && p.amount_basis == builtin.amount_basis
            && p.provenance == builtin.provenance
            && same_bits(&p.k, &builtin.k)
            && same_bits(&p.s, &builtin.s)
        {
            builtin.fingerprint
        } else {
            crate::sha256::digest(&p.package_body())
        };
        Ok(p)
    }

    fn package_body(&self) -> Vec<u8> {
        let modern = B != 81 || !self.pair_controls.is_empty();
        let mut out = Vec::new();
        out.extend_from_slice(if modern {
            b"OPP3"
        } else if N == 4 {
            b"OPP1"
        } else {
            b"OPP2"
        });
        if modern || N != 4 {
            out.extend_from_slice(&(N as u32).to_le_bytes());
        }
        let (start, step, _) = self.spectral_grid();
        for value in [
            B as u32,
            start as u32,
            step as u32,
            match self.amount_basis {
                AmountBasis::Relative => 0,
                AmountBasis::Mass => 1,
                AmountBasis::Volume => 2,
            },
        ] {
            out.extend_from_slice(&value.to_le_bytes());
        }
        if modern {
            out.extend_from_slice(&u32::from(!self.pair_controls.is_empty()).to_le_bytes());
        }
        for value in std::iter::once(self.id())
            .chain(std::iter::once(self.provenance()))
            .chain(self.paint_names())
        {
            out.extend_from_slice(&(value.len() as u32).to_le_bytes());
            out.extend_from_slice(value.as_bytes());
        }
        for v in self
            .k
            .iter()
            .flatten()
            .chain(self.s.iter().flatten())
            .chain(self.rgb.iter().flatten())
        {
            out.extend_from_slice(&v.to_le_bytes());
        }
        if modern {
            out.extend_from_slice(&(self.pair_controls.len() as u32).to_le_bytes());
            for v in self.pair_controls.iter().flatten() {
                out.extend_from_slice(&v.to_le_bytes());
            }
        }
        out
    }

    /// Exact optical definition, projection, model kind and controls, then SHA-256.
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut out = self.package_body();
        let hash = crate::sha256::digest(&out);
        out.extend_from_slice(&hash);
        out
    }

    pub fn from_bytes(bytes: &[u8]) -> Result<Self, PaletteError> {
        if !(1..=MAX_PAINTS).contains(&N) || bytes.len() < 52 || bytes.len() > MAX_PACKAGE_BYTES {
            return Err(PaletteError::InvalidPalette);
        }
        let expected_rgb = projection::<B>()?;
        let modern = &bytes[..4] == b"OPP3";
        if !modern
            && (B != 81 || (N == 4 && &bytes[..4] != b"OPP1") || (N != 4 && &bytes[..4] != b"OPP2"))
        {
            return Err(PaletteError::InvalidPalette);
        }
        let end = bytes.len() - 32;
        if crate::sha256::digest(&bytes[..end]) != bytes[end..] {
            return Err(PaletteError::InvalidChecksum);
        }
        let mut reader = Reader {
            bytes: &bytes[4..end],
            position: 0,
        };
        if (modern || N != 4) && reader.u32()? as usize != N {
            return Err(PaletteError::InvalidPalette);
        }
        let expected_grid = if B == 31 { [31, 400, 10] } else { [81, 380, 5] };
        if [reader.u32()?, reader.u32()?, reader.u32()?] != expected_grid {
            return Err(PaletteError::UnsupportedGrid);
        }
        let basis = match reader.u32()? {
            0 => AmountBasis::Relative,
            1 => AmountBasis::Mass,
            2 => AmountBasis::Volume,
            _ => return Err(PaletteError::InvalidPalette),
        };
        let model = if modern { reader.u32()? } else { 0 };
        if model > 1 {
            return Err(PaletteError::InvalidPalette);
        }
        let id = reader.text(128)?;
        let provenance = reader.text(4096)?;
        let mut names = [""; N];
        for name in &mut names {
            *name = reader.text(64)?;
        }
        let mut k = [[0.; N]; B];
        let mut s = k;
        let mut rgb = [[0.; 3]; B];
        for value in k
            .iter_mut()
            .flatten()
            .chain(s.iter_mut().flatten())
            .chain(rgb.iter_mut().flatten())
        {
            *value = reader.f64()?;
        }
        if !same_bits(&rgb, &expected_rgb) {
            return Err(PaletteError::UnsupportedGrid);
        }
        let mut controls = Vec::new();
        if modern {
            let count = reader.u32()? as usize;
            if count != if model == 1 { N * (N - 1) / 2 } else { 0 } {
                return Err(PaletteError::InvalidPalette);
            }
            for _ in 0..count {
                controls.push([reader.f64()?, reader.f64()?, reader.f64()?, reader.f64()?]);
            }
        }
        if reader.position != reader.bytes.len() {
            return Err(PaletteError::InvalidPalette);
        }
        let p = Self::from_optics_with_pair_correction(
            PaletteMetadataN {
                id,
                paint_names: names,
                amount_basis: basis,
                provenance,
            },
            k,
            s,
            controls,
        )?;
        // Enforce a canonical header/model representation, including legacy bytes.
        if p.package_body() != bytes[..end] {
            return Err(PaletteError::InvalidPalette);
        }
        Ok(p)
    }
}

fn same_bits<const R: usize, const N: usize, const T: usize, const M: usize>(
    a: &[[f64; N]; R],
    b: &[[f64; M]; T],
) -> bool {
    R == T
        && N == M
        && a.iter()
            .flatten()
            .zip(b.iter().flatten())
            .all(|(a, b)| a.to_bits() == b.to_bits())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn native_packages_reject_unknown_model_projection_and_controls() {
        let p = PaletteN::<8, 31>::from_optics_with_pair_correction(
            PaletteMetadataN {
                id: "native",
                paint_names: ["a", "b", "c", "d", "e", "f", "g", "h"],
                amount_basis: AmountBasis::Mass,
                provenance: "Synthetic test",
            },
            [[1.; 8]; 31],
            [[1.; 8]; 31],
            vec![[0.1; 4]; 28],
        )
        .unwrap();
        let original = p.to_bytes();
        let end = original.len() - 32;
        for (offset, replacement) in [
            (24, 2_u32.to_le_bytes().to_vec()),
            (end - 8, 0.81_f64.to_le_bytes().to_vec()),
            (end - 28 * 32 - 4, u32::MAX.to_le_bytes().to_vec()),
            (end - 28 * 32 - 4 - 8, 0.0_f64.to_le_bytes().to_vec()),
        ] {
            let mut bad = original.clone();
            bad[offset..offset + replacement.len()].copy_from_slice(&replacement);
            let checksum = crate::sha256::digest(&bad[..end]);
            bad[end..].copy_from_slice(&checksum);
            assert!(PaletteN::<8, 31>::from_bytes(&bad).is_err());
        }
    }
    #[test]
    fn original_four_paint_package_bytes_are_unchanged() {
        // SHA-256 of the OPP1 package generated on 2026-09-30, before N-paint support.
        let hash = crate::sha256::digest(&synthetic_four().to_bytes());
        let hex: String = hash.iter().map(|b| format!("{b:02x}")).collect();
        assert_eq!(
            hex,
            "400e576d7b9fc508680a03706bb54f2742de29a618e990bf180f24d6aeb18d03"
        );
    }

    #[test]
    fn counted_packages_reject_rechecksummed_count_and_high_index_optics() {
        let p = PaletteN::<8>::from_optics(
            PaletteMetadataN {
                id: "eight-parser-test",
                paint_names: ["a", "b", "c", "d", "e", "f", "g", "h"],
                amount_basis: AmountBasis::Relative,
                provenance: "Synthetic constant test optics",
            },
            [[1.; 8]; SAMPLES],
            [[1.; 8]; SAMPLES],
        )
        .unwrap();
        let original = p.to_bytes();
        let end = original.len() - 32;
        for (offset, replacement) in [
            (4, 7_u32.to_le_bytes().to_vec()),
            (end - SAMPLES * 11 * 8 - 8, f64::NAN.to_le_bytes().to_vec()),
            (end - SAMPLES * 3 * 8 - 8, 0_f64.to_le_bytes().to_vec()),
        ] {
            let mut bad = original.clone();
            bad[offset..offset + replacement.len()].copy_from_slice(&replacement);
            let hash = crate::sha256::digest(&bad[..end]);
            bad[end..].copy_from_slice(&hash);
            assert!(PaletteN::<8>::from_bytes(&bad).is_err());
        }
    }
    #[test]
    fn checksummed_invalid_packages_are_rejected() {
        let original = synthetic_four().to_bytes();
        let end = original.len() - 32;
        // Unsupported grid, basis, oversized string, optical NaN, projection NaN.
        for (offset, replacement) in [
            (4, 41_u32.to_le_bytes().to_vec()),
            (16, 9_u32.to_le_bytes().to_vec()),
            (20, u32::MAX.to_le_bytes().to_vec()),
            (end - 81 * 11 * 8, f64::NAN.to_le_bytes().to_vec()),
            (end - 8, f64::NAN.to_le_bytes().to_vec()),
        ] {
            let mut bytes = original.clone();
            bytes[offset..offset + replacement.len()].copy_from_slice(&replacement);
            let hash = crate::sha256::digest(&bytes[..end]);
            bytes[end..].copy_from_slice(&hash);
            assert!(Palette::from_bytes(&bytes).is_err());
        }
    }
}

struct Reader<'a> {
    bytes: &'a [u8],
    position: usize,
}
impl<'a> Reader<'a> {
    fn take(&mut self, n: usize) -> Result<&'a [u8], PaletteError> {
        let end = self
            .position
            .checked_add(n)
            .ok_or(PaletteError::InvalidPalette)?;
        let slice = self
            .bytes
            .get(self.position..end)
            .ok_or(PaletteError::InvalidPalette)?;
        self.position = end;
        Ok(slice)
    }
    fn u32(&mut self) -> Result<u32, PaletteError> {
        Ok(u32::from_le_bytes(self.take(4)?.try_into().unwrap()))
    }
    fn f64(&mut self) -> Result<f64, PaletteError> {
        Ok(f64::from_le_bytes(self.take(8)?.try_into().unwrap()))
    }
    fn text(&mut self, max: usize) -> Result<&'a str, PaletteError> {
        let n = self.u32()? as usize;
        if n > max {
            return Err(PaletteError::InvalidPalette);
        }
        std::str::from_utf8(self.take(n)?).map_err(|_| PaletteError::InvalidPalette)
    }
}
