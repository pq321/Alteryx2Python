# Local statistics adapters

`statistics_extra` provides a bounded local profile for statistical macros. It
accepts `fields`, `target`, `group`, `seed` (plus `k`, `clusters`, and
`components`) and returns pandas evidence. Numeric fields must be present and
non-null. Clustering, neighbors, and MDS use scikit-learn; no native Alteryx
or R model/report binary equivalence is claimed. Native settings are retained
by the parser as normalized scalar values when available.
