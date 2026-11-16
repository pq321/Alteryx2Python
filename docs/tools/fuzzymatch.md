# FuzzyMatch

- Inputs: `Input`.
- Outputs: `Output`.
- Supports pair output for WholeField, Digits and DigitsReverse keys without
  a secondary scoring algorithm. It also supports cross-source pairs and the
  optional score in this profile.
- Four native Designer cases cover WholeField and DigitsReverse keys in Merge
  and Purge modes, including case differences and trailing spaces.
- Phonetic keys, Jaro/TF-IDF scoring, generated-key output, unmatched rows
  and group suppression still need native calibration.
