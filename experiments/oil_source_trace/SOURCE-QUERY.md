# Unsent technical query: supplement and Figure 6 alignment

Draft only; not sent.

Subject: Reproducing Figure 6 from the supplement to Sensors 2021, 21, 2471

I am investigating the public supplementary measurements accompanying
"Comparison of Imaging Models for Spectral Unmixing in Oil Painting"
(DOI 10.3390/s21072471). Thank you for making the data available.

I obtained the supplement through Europe PMC. The inner ZIP SHA-256 is
6d8cec6fb4fff5d4c24d18d1783422da8ef955d3e7ba7263179a84ed6c9b683e.
Both spreadsheets contain 175 matching sample labels. Two independent readers
agree on every numerical value and label.

I would appreciate clarification on two points:

1. Do the headers in `mockups_reflectance.xlsx` directly identify the spectra in
   their columns, in the same order as `mockups_concentration.xlsx`? The column
   headed W (AI, with wavelengths in A) has reflectance 0.11205 at 548.99 nm,
   while the concentration table identifies W as 100% Kremer White. Is there a
   scan-to-sample mapping, additional calibration step, or updated supplement
   that should be used?
2. Which endmember spectra and preprocessing reproduce Figure 6's forward-model
   comparison? Using the columns labelled as the seven pure pigments, the given
   fractions, and ten discarded bands per edge gives mean MSE 0.02205683 for M1
   and 0.02294931 for M2 over all 175 samples. Figure 6 appears to show about
   0.02035 and 0.00704, respectively. Nominal exact ratios, the full spectral
   interval, and exclusion of the seven pure samples do not resolve the ordering.

We have left the source files unchanged, retained the unsuccessful reproduction,
and have not inferred a corrected ordering from colors or model error. A sample
map, the exact reference endmembers, or the original Figure 6 calculation inputs
would help determine whether our interpretation is missing a step.
