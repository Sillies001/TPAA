# ADR-M0-008 — Structured Logging / Telemetry

- **Status:** CLOSED
- **Decision date:** 2026-09-23
- **Owner role:** WS-SECURITY / WS-DEVOPS technical lead
- **Milestone:** M0 Engineering Bootstrap
- **Authority:** SDIB-1.0 §33–§35, §17; Appendix T
- **Machine policy:** `tools/security/OBSERVABILITY_POLICY.json`

## Decision

TPAA freezes a **stdlib `logging` based structured-observability facade with NDJSON records** for M0.

1. Application code emits through TPAA-owned helpers, not formatter-specific calls scattered through Domain/Application code.
2. Each log/audit record has a system UTC timestamp distinct from optional business/session time. `session_time_us` remains a governed decimal string and is never substituted for the log timestamp.
3. Standard correlation fields are `request_id`, `job_id`, `session_id`, `release_id`, `component`, `product_version`, and `reason_code`; absent values are explicit null/omitted according to the facade contract.
4. Structured logs are UTF-8 newline-delimited JSON with stable key naming. Human console rendering may differ, but machine evidence uses the structured form.
5. Secret-bearing field names are rejected/redacted before serialization. Desktop bearer tokens, credentials, authorization headers, cookies, private keys and secret environment/config values must not be emitted.
6. M0 telemetry freezes an internal counter/timing/event interface only. No Prometheus/OpenTelemetry backend is a runtime requirement at M0; exporters can be added behind the interface later without changing business semantics.
7. Business insufficiency/status codes and system failures are distinct classifications. Logging must not turn N_A/INSUFFICIENT into exceptions or vice versa.
8. Logs, metrics timestamps, hostnames and PIDs are diagnostic/physical data and do not participate in logical product hashes.

## Rationale

The standard library is available on every governed Python profile and is sufficient to freeze record semantics before selecting an operations backend. Owning the schema prevents a future logging vendor from becoming a Domain contract.

## Alternatives considered

- **OpenTelemetry SDK as mandatory M0 runtime dependency:** rejected; backend/exporter topology is not yet an M0 product requirement.
- **Plain text free-form logs:** rejected because audit/correlation and machine evidence require structured fields.
- **Use Session Time as log time:** rejected; SDIB requires strict separation between business time and system/logging time.

## Verification / evidence

- `tools/security/OBSERVABILITY_POLICY.json`
- structured audit/log tests under M0-SEC-002/004
- secret redaction/fail-closed tests
- build/test evidence containing correlation fields without credentials

## Reopen conditions

Reopen when an approved operations profile mandates a telemetry backend/protocol, when retention/privacy requirements change the record boundary, or when structured record fields require a semantic governance update.
