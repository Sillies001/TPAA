# TPAA Definition of Done

This repository policy implements SDIB-1.0.1 §32 and M0-GOV-004.

## Pull Request DoD

A PR is merge-ready only when its declared scope has:

- M / Primary WS / related P / Stage classification as applicable;
- authority references and change class;
- implementation, tests, docs and generated projections aligned;
- no undeclared Canonical/DTO/Metric/Stage semantic fork;
- unit/contract and applicable Golden/replay/migration tests GREEN;
- required Windows/Linux gates GREEN;
- security/data impact evaluated;
- replay/migration/Release impact stated;
- observability sufficient to diagnose controlled failure;
- evidence traceable to source revision and authority.

## Feature DoD

In addition to PR DoD, the controlling backlog acceptance statement is demonstrated by a machine/reviewable Gate. Reserved or placeholder commands never count as completion.

## Milestone DoD

Milestone completion requires every mandatory Exit Gate, hosted platform evidence, build/package manifest, SBOM/license/native dependency evidence, reproducible cold-start, and explicit review of every deferred item. A later milestone capability may not be used to paper over an incomplete earlier Exit Gate.

M0 completion is an engineering-substrate claim only; it never admits P1 capability.
