//! Reproducible RGB -> simplex concentration tables, tetrahedral or trilinear.
use crate::{Color, MixError};
#[derive(Clone, Debug)]
pub struct Lut {
    resolution: usize,
    values: Vec<[f32; 8]>,
}
impl Lut {
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, MixError> {
        if bytes.len() < 8 || &bytes[0..4] != b"PMX1" {
            return Err(MixError::InvalidLut);
        }
        let n = u32::from_le_bytes(bytes[4..8].try_into().unwrap()) as usize;
        if !(2..=129).contains(&n) || bytes.len() != 8 + 32 * n * n * n {
            return Err(MixError::InvalidLut);
        }
        let mut values = Vec::with_capacity(n * n * n);
        for chunk in bytes[8..].chunks_exact(32) {
            let mut v = [0.; 8];
            for i in 0..8 {
                v[i] = f32::from_le_bytes(chunk[i * 4..i * 4 + 4].try_into().unwrap());
            }
            if v.iter().any(|x| !x.is_finite() || *x < 0.)
                || (v.iter().sum::<f32>() - 1.).abs() > 1e-4
            {
                return Err(MixError::InvalidLut);
            }
            values.push(v)
        }
        Ok(Self {
            resolution: n,
            values,
        })
    }
    pub fn generate(n: usize) -> Result<Self, MixError> {
        if !(2..=129).contains(&n) {
            return Err(MixError::InvalidLut);
        }
        let mut values = Vec::with_capacity(n * n * n);
        for r in 0..n {
            for g in 0..n {
                for b in 0..n {
                    let c = [
                        r as f64 / (n - 1) as f64,
                        g as f64 / (n - 1) as f64,
                        b as f64 / (n - 1) as f64,
                    ];
                    values.push(crate::latent::invert(c).map(|x| x as f32));
                }
            }
        }
        Ok(Self {
            resolution: n,
            values,
        })
    }
    pub fn to_bytes(&self) -> Vec<u8> {
        let mut b = b"PMX1".to_vec();
        b.extend((self.resolution as u32).to_le_bytes());
        for v in &self.values {
            for x in v {
                b.extend(x.to_le_bytes())
            }
        }
        b
    }
    pub fn resolution(&self) -> usize {
        self.resolution
    }
    pub fn memory_bytes(&self) -> usize {
        self.values.len() * 32
    }
    #[inline]
    fn at(&self, c: [usize; 3]) -> [f32; 8] {
        self.values[(c[0] * self.resolution + c[1]) * self.resolution + c[2]]
    }
    #[inline]
    pub fn lookup(&self, c: Color) -> [f32; 8] {
        self.lookup_impl(c, false)
    }
    pub fn lookup_trilinear(&self, c: Color) -> [f32; 8] {
        self.lookup_impl(c, true)
    }
    fn lookup_impl(&self, c: Color, tri: bool) -> [f32; 8] {
        let n = self.resolution - 1;
        let p = c.channels().map(|x| x * n as f32);
        let base = p.map(|x| (x.floor() as usize).min(n - 1));
        let f = std::array::from_fn::<_, 3, _>(|i| p[i] - base[i] as f32);
        let mut out = [0.; 8];
        if tri {
            for mask in 0..8 {
                let v = self.at(std::array::from_fn(|i| base[i] + ((mask >> i) & 1)));
                let w = (0..3)
                    .map(|i| {
                        if mask & (1 << i) != 0 {
                            f[i]
                        } else {
                            1. - f[i]
                        }
                    })
                    .product::<f32>();
                for j in 0..8 {
                    out[j] += v[j] * w
                }
            }
        } else {
            let mut order = [0, 1, 2];
            order.sort_by(|a, b| f[*b].total_cmp(&f[*a]));
            let a = f[order[0]];
            let b = f[order[1]];
            let c = f[order[2]];
            let weights = [1. - a, a - b, b - c, c];
            let mut coord = base;
            for k in 0..4 {
                let v = self.at(coord);
                for j in 0..8 {
                    out[j] += v[j] * weights[k]
                }
                if k < 3 {
                    coord[order[k]] += 1
                }
            }
        }
        out
    }
}
