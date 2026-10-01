//! Checked OPP1 (four paints) and OPP2 (explicit paint count) packages; child module of palette.
use super::*;

const MAX_PACKAGE_BYTES: usize = 65_536;

impl<const N: usize> PaletteN<N> {
    /// Import 1-16 materials on the fixed 81-band reference grid. K must be in
    /// [0,1e100], S in [1e-100,1e100]. These broad numerical bounds keep all
    /// supported mixtures finite; they are not physical coefficient units.
    pub fn from_optics(
        metadata: PaletteMetadataN<'_, N>,
        k: [[f64; N]; SAMPLES],
        s: [[f64; N]; SAMPLES],
    ) -> Result<Self, PaletteError> {
        let text_ok = |s: &str, max: usize| {
            !s.trim().is_empty() && s.len() <= max && !s.chars().any(char::is_control)
        };
        if !(1..=MAX_PAINTS).contains(&N)
            || !text_ok(metadata.id, 128)
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
            rgb: data::RGB,
            fingerprint: [0; 32],
        };
        // Preserve identities of the already-published built-in OPR1/OPL1 data.
        let builtin = synthetic_four();
        p.fingerprint = if N == 4
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
        let mut out = Vec::new();
        out.extend_from_slice(if N == 4 { b"OPP1" } else { b"OPP2" });
        if N != 4 {
            out.extend_from_slice(&(N as u32).to_le_bytes());
        }
        for value in [
            SAMPLES as u32,
            START_NM as u32,
            STEP_NM as u32,
            match self.amount_basis {
                AmountBasis::Relative => 0,
                AmountBasis::Mass => 1,
                AmountBasis::Volume => 2,
            },
        ] {
            out.extend_from_slice(&value.to_le_bytes());
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
        out
    }

    /// Full optical definition, including names, amount convention, attribution,
    /// exact projection and trailing SHA-256 checksum. No LUT is embedded.
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut out = self.package_body();
        let hash = crate::sha256::digest(&out);
        out.extend_from_slice(&hash);
        out
    }

    pub fn from_bytes(bytes: &[u8]) -> Result<Self, PaletteError> {
        if !(1..=MAX_PAINTS).contains(&N)
            || bytes.len() < 52
            || bytes.len() > MAX_PACKAGE_BYTES
            || (N == 4 && &bytes[..4] != b"OPP1")
            || (N != 4 && &bytes[..4] != b"OPP2")
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
        if N != 4 && reader.u32()? as usize != N {
            return Err(PaletteError::InvalidPalette);
        }
        if [reader.u32()?, reader.u32()?, reader.u32()?]
            != [SAMPLES as u32, START_NM as u32, STEP_NM as u32]
        {
            return Err(PaletteError::UnsupportedGrid);
        }
        let basis = match reader.u32()? {
            0 => AmountBasis::Relative,
            1 => AmountBasis::Mass,
            2 => AmountBasis::Volume,
            _ => return Err(PaletteError::InvalidPalette),
        };
        let id = reader.text(128)?;
        let provenance = reader.text(4096)?;
        let mut names = [""; N];
        for name in &mut names {
            *name = reader.text(64)?;
        }
        let mut k = [[0.; N]; SAMPLES];
        let mut s = k;
        let mut rgb = [[0.; 3]; SAMPLES];
        for value in k
            .iter_mut()
            .flatten()
            .chain(s.iter_mut().flatten())
            .chain(rgb.iter_mut().flatten())
        {
            *value = reader.f64()?;
        }
        if reader.position != reader.bytes.len() {
            return Err(PaletteError::InvalidPalette);
        }
        if !same_bits(&rgb, &data::RGB) {
            return Err(PaletteError::UnsupportedGrid);
        }
        Self::from_optics(
            PaletteMetadataN {
                id,
                paint_names: names,
                amount_basis: basis,
                provenance,
            },
            k,
            s,
        )
    }
}

fn same_bits<const N: usize, const M: usize>(
    a: &[[f64; N]; SAMPLES],
    b: &[[f64; M]; SAMPLES],
) -> bool {
    N == M
        && a.iter()
            .flatten()
            .zip(b.iter().flatten())
            .all(|(a, b)| a.to_bits() == b.to_bits())
}

#[cfg(test)]
mod tests {
    use super::*;
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
