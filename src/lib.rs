//! Ochrell: independent RGB pigment mixing using synthetic spectral Kubelka–Munk optics.
//!
//! ```
//! use ochrell::{Color, mix};
//! let green = mix(Color::srgb8(255,220,0), Color::srgb8(20,70,255), 0.5);
//! assert!(green.channels()[1] > green.channels()[0]);
//! ```
#![forbid(unsafe_code)]
pub mod color;
pub mod compact;
pub mod conversion;
mod generated;
pub mod kubelka_munk;
pub mod latent;
pub mod lut;
pub mod mixing;
pub mod optical;
mod optical_generated;
pub mod palette;
mod palette_generated;
pub mod palette_lut;
pub mod pigment;
pub mod spectrum;
pub use color::{Color, MixError};
pub use optical::{mix, mix_weighted, FastPigmentMixer, PigmentMixer, ReferenceSpectralMixer};
pub use optical::{Latent, ReferenceLatent};
/// Frozen v0.1 finite-palette model, kept for reproducible comparisons.
pub mod legacy {
    pub use crate::latent::{Latent, ReferenceLatent};
    pub use crate::mixing::*;
}
