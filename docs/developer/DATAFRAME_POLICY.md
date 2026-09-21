# DataFrame / Flight-Data Computation Policy

For TPAA airborne-data processing, metric calculation and columnar/time-series analysis, **Polars is the default DataFrame/query engine**.

Rules:

1. Prefer Polars expressions, lazy scans, streaming execution, window functions and columnar aggregation for flight-data workloads.
2. Do not add Pandas as a default dependency or create Polars↔Pandas conversions merely for implementation convenience.
3. NumPy/SciPy or domain-specific numerical libraries may be used when the required algorithm is not naturally expressed in Polars.
4. Pandas may be introduced only for a concrete interoperability/algorithm requirement, with the dependency and conversion boundary documented in the implementing change.
5. The actual Polars runtime version enters `uv.lock` when the first implementation task requiring it is admitted; this toolchain-bootstrap increment does not create an unused production dependency.

This policy does not make Polars a Canonical business authority. Metric formulas, input bindings, value kinds, Stage semantics and reason/status codes remain governed by the frozen machine-readable baseline.
