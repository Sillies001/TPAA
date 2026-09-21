# M0-CORE-005 — Architecture Dependency Test

**Status:** COMPLETE
**Baseline:** SDIB-1.0
**Source contract:** §7.1 and Appendix E
**Depends on:** M0-CORE-001 through M0-CORE-004

## 1. Objective

Implement a vendor-neutral, standard-library-only static architecture gate that automatically
rejects Python import dependencies violating the SDIB package/layer contract.

The minimum acceptance is exact:

1. lower layers MUST NOT depend on `tpaa_gui` or `tpaa_api`;
2. business-core packages MUST NOT directly depend on `tpaa_platform` implementation.

The gate also encodes concrete import-level prohibitions from SDIB Appendix E where they can be
verified without interpreting business behavior.

## 2. Authority and non-authority

SDIB-1.0 remains the architecture authority. `ARCHITECTURE_POLICY.json` is an executable projection
of §7.1 / Appendix E, not a new product authority.

If implementation discovers a conflict between the executable policy and SDIB intent, the code
MUST NOT silently weaken or invent architecture semantics. The conflict must be resolved in the
appropriate SDIB/ADR layer first.

## 3. Scanner design

The scanner:

- walks Python source below `src/`;
- parses source with `ast`, failing closed on parse errors;
- resolves absolute and relative static imports;
- recognizes literal `importlib.import_module(...)` and `__import__(...)` dependencies;
- evaluates dependencies against the machine-readable architecture policy;
- emits deterministic, sorted violations containing file, line, source package, imported module,
  reason code and policy rule.

No third-party dependency is permitted for the architecture gate itself.

## 4. Executable rules

### 4.1 Lower-layer transport reversal

All governed packages below transport MUST NOT import `tpaa_api` or `tpaa_gui`.

Reason code: `LOWER_LAYER_TRANSPORT_DEPENDENCY`.

### 4.2 Business-core platform implementation leakage

The governed business-core packages MUST NOT import `tpaa_platform` directly. OS/native behavior is
consumed through narrow ports/protocols rather than implementation imports.

Reason code: `BUSINESS_CORE_PLATFORM_IMPLEMENTATION_DEPENDENCY`.

### 4.3 Appendix-E first-party edges

Concrete reverse/cross-layer dependencies that are unambiguously represented by package imports are
encoded as `forbidden_first_party_edges` in the policy.

Reason code: `FORBIDDEN_FIRST_PARTY_DEPENDENCY`.

### 4.4 Framework/DB leakage

Where Appendix E explicitly forbids GUI toolkit, transport framework or concrete DB-driver leakage,
well-known import module prefixes are blocked.

Reason code: `FORBIDDEN_EXTERNAL_DEPENDENCY`.

### 4.5 Generated runtime purity

`tpaa_generated` may import Python stdlib and itself only. Product services, DB drivers, GUI/API and
other project implementation packages are rejected.

Reason code: `GENERATED_NON_STDLIB_DEPENDENCY` or a more specific first-party rule.

## 5. Deliberate semantic boundary

The following Appendix-E statements are NOT claimed to be fully proven by an import scanner alone:

- whether Observation code *recomputes* Metric/World rather than consuming published staging;
- whether a Metric implementation uses a semantic `current/latest` shortcut;
- whether Storage code contains business inference despite importing only permitted primitives;
- whether Platform code embeds business rules without importing a domain package.

These remain subject to focused contract/semantic tests and code review as the corresponding modules
are implemented. M0-CORE-005 does not report these as automated PASS.

## 6. Developer command

The repository exposes one implementation for local and later CI use:

```text
python tools/dev/tpaa_dev.py verify-architecture
```

External CI providers MUST invoke this command rather than reimplementing dependency rules.

## 7. Tests

Unit tests cover:

- static `import` and `from ... import ...` detection;
- relative import resolution;
- literal dynamic-import detection;
- parse-error fail-closed behavior;
- generated non-stdlib rejection;
- deterministic violation ordering.

Contract tests cover:

- the current repository passes;
- lower-layer → GUI/API fault injection fails;
- business-core → `tpaa_platform` fault injection fails;
- API → concrete Storage fault injection fails;
- forbidden external framework/DB imports fail;
- unified developer command is implemented.

## 8. Completion criteria

M0-CORE-005 is COMPLETE only when:

1. the current repository has zero architecture violations;
2. minimum acceptance fault injections are rejected;
3. Appendix-E concrete import rules are machine-readable and tested;
4. the unified developer command returns non-zero on any violation;
5. M0-CORE-001 through M0-CORE-004 regression remains PASS;
6. a clean-clone run produces the same result.

## 9. Implementation feedback

The first test implementation exposed an important fail-closed detail: first-party package identity
must not be inferred only from directories currently present under `src/`. A partial tree could then
misclassify a prohibited import such as `tpaa_gui` as an arbitrary external module. The final scanner
therefore unions discovered packages with all first-party package identities frozen in the policy.

No ADR or Canonical/Baseline change was required by this task. The governing dependency semantics
were already explicit in SDIB-1.0 §7.1 / Appendix E.
