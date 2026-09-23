# M0_BASIC_TRANSPORT_V1

This bundle is an M0 **framework-smoke fixture**, not a production Metric Golden and not an
M1 synthetic vertical-slice bundle.

It exercises the frozen test harness contracts required before M1:

- fixture id/version and exact input/expected hashes;
- Context/Stage/Profile reference fields;
- NUMERIC/TEXT/BOOLEAN/STRUCTURED transport behavior;
- Session Time represented as a decimal string beyond the JavaScript safe-integer range;
- exact logical products plus one shared numeric tolerance;
- replay binding to frozen refs while current refs intentionally differ;
- deterministic missing/corrupt/version-mismatch/insufficient failure paths.

The expected logical product is checked in independently of the runtime output. The fixture
lifecycle is **REVIEWED**, not `APPROVED_GOLDEN`: this checkpoint does not claim an independent
Metric-mathematics approval. Promotion to `APPROVED_GOLDEN` requires the independent review
discipline in SDIB-1.0 Appendix O and is intentionally not fabricated by the harness.
