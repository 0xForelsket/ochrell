//! Checked OPP1 optical palette packages; child module of palette.
use super::*;

const MAX_PACKAGE_BYTES: usize = 16_384;

impl Palette {
    /// Import four materials on the fixed 81-band reference grid. K must be in
    /// [0,1e100], S in [1e-100,1e100]. These broad numerical bounds keep all
    /// supported mixtures finite; they are not physical coefficient units.
    pub fn from_optics(
        metadata: PaletteMetadata<'_>,
        k: [[f64; PAINT_COUNT]; SAMPLES],
        s: [[f64; PAINT_COUNT]; SAMPLES],
    ) -> Result<Self, PaletteError> {
        let text_ok = |s: &str, max: usize| {
            !s.trim().is_empty() && s.len() <= max && !s.chars().any(char::is_control)
        };
        if !text_ok(metadata.id, 128)
            || !text_ok(metadata.provenance, 4096)
            || metadata.paint_names.iter().any(|n| !text_ok(n, 64))
            || (0..4)
                .any(|i| (i + 1..4).any(|j| metadata.paint_names[i] == metadata.paint_names[j]))
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
        p.fingerprint = if p.id == builtin.id
            && p.names == builtin.names
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
        out.extend_from_slice(b"OPP1");
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
        if bytes.len() < 52 || bytes.len() > MAX_PACKAGE_BYTES || &bytes[..4] != b"OPP1" {
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
        let names = [
            reader.text(64)?,
            reader.text(64)?,
            reader.text(64)?,
            reader.text(64)?,
        ];
        let mut k = [[0.; 4]; SAMPLES];
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
            PaletteMetadata {
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

fn same_bits<const N: usize>(a: &[[f64; N]; SAMPLES], b: &[[f64; N]; SAMPLES]) -> bool {
    a.iter()
        .flatten()
        .zip(b.iter().flatten())
        .all(|(a, b)| a.to_bits() == b.to_bits())
}

#[cfg(test)]
mod tests {
    use super::*;
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
