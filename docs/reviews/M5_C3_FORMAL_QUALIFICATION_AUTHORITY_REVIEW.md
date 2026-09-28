# M5 C3 Formal Qualification Authority Review

## Identity

- Tracking issue: #136
- Change class: C3 — formal qualification semantic contract
- Candidate authority: `M5_FORMAL_QUALIFICATION_AUTHORITY` v1.0.0
- Candidate authority SHA-256: `e3dd1fafa9c65d6c9a85dfb7172d60adef3e9c17893e3b546b962275c42c01b1`
- Parent protected-main SHA: `de5dfb528156428eee93ce4d022350382cbf4127`
- Parent baseline lock SHA-256: `8bc1834502561992e9aef64d73186c7854ef293e4ec57f658b4e9f72828e0cab`
- DB schema: 1.6.0 unchanged
- Controlled artifact count: 23 → 24

## Decisions frozen

1. P1-only M5 qualification; P2-P6 remain inactive.
2. Exact four mandatory certification profiles from PLATFORM_COMPATIBILITY_REGISTRY.
3. Qualification host minimum: x86_64, 4 logical CPU, 8 GiB RAM, 20 GiB free SSD/enterprise block storage.
4. Deterministic `M5_P1_QUALIFICATION_WORKLOAD_V1`: 50 synthetic sessions, 116 P1 metrics, 104 longitudinal metrics, 5,800 observations, 5,200 longitudinal points, 1,000 API queries.
5. Exact desktop/service latency, throughput, wall-time, CPU/RSS/storage and zero-error thresholds.
6. CycloneDX 1.6 + exact lock/native manifest; zero unwaived Critical/High/Medium vulnerabilities. Medium may be waived for at most 90 days with explicit security+release approval.
7. M5 package artifacts are offline runtime bundles. Target machines may not require a project venv, uv, Python, or network access.
8. Native platform code signing is not mandatory in M5 v1 because no enterprise PKI authority is frozen; SHA-256 manifests, exact protected-main provenance and release signoff are mandatory.
9. First M5 release may mark prior-version upgrade as explicit N/A only when no earlier accepted M5 release exists; failed-install rollback is still mandatory. Subsequent releases must support the immediate prior accepted release on the same profile.
10. Backup/restore RPO for committed published Releases is 0 seconds; restore RTO maximum is 1,800 seconds; one-byte corruption must fail before target mutation.
11. Formal release requires all four profile PASS evidence, exact candidate identity, no current/latest substitution, unexpired waivers, and three distinct signoff roles: RELEASE_MANAGER, INDEPENDENT_QA, SECURITY_APPROVER.
12. Formal M5-qualified claim remains forbidden until protected-main M5 Exit GO.

## Non-goals

- no change to P1 Metric/Stage/DTO/business formulas;
- no P2-P6 admission;
- no DB schema or shadow schema;
- no relaxation of immutable Release/replay/knowledge-time behavior.

## Adoption gate

This authority is inactive until the exact candidate passes Hosted CI, merges with expected-head protection, and the actual merge SHA passes protected-main CI. #136 closes only after that evidence.
