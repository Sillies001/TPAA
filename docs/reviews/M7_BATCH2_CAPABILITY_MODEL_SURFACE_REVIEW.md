# M7 Batch 2 — Capability Model / Surface / Golden Replay Review

## Identity

- Program: #149
- Batch tracker: #174
- Parent protected-main SHA: `ebfb99afbb86cf1fc857d03d746afa6e774a4626`
- Parent protected-main Run: #501 / `36726742843` / 14 of 14 PASS
- Adopted P3 authority: `P3_CAPABILITY_TWIN_AUTHORITY:1.0.0`
- Adopted execution profile: `P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL:1.0.0`
- DB schema: 1.6.0 unchanged

## Batch scope

This batch implements only:

- M7-CAP-001 — deterministic capability-model training-set materialization;
- M7-CAP-002 — governed capability-model execution and validation provenance;
- M7-CAP-003 — capability-surface generation and validity-domain product;
- M7-TST-002 — synthetic fixture family;
- M7-TST-003 — deterministic Golden/replay qualification.

It does not publish aircraft twin revisions, emit P3 final estimates, expose API/GUI products, admit P3, or activate P4-P6.

## Training snapshot

The training dataset snapshot is a frozen `registry.dataset_snapshot` projection with schema `TPAA_P3_MODEL_TRAINING_V1`.

Identity includes:

- exact adopted authority/profile SHA;
- exact lifecycle segment snapshot/hash;
- exact validation snapshot/hash;
- exact P2 estimate IDs and immutable P2/P1 release/observation provenance;
- exact attribution-run ID;
- exact configuration snapshot ID/hash;
- exact session/episode/session-order;
- adjusted value and uncertainty;
- exact knowledge-time cutoff.

Ordering is `SESSION_ORDER_ASC_THEN_ESTIMATE_ID_ASC`; input order cannot alter the dataset hash.

## Model execution

Profile v1 remains AIRCRAFT-only. It does not pool aircraft into an aircraft-model population estimate.

Validation is the adopted temporal last-point holdout:

1. require at least four exact eligible P2 points;
2. hold out the final session-order point;
3. fit OLS to the governed 3..5-point prefix;
4. compute prefix unscaled MAD;
5. accept only when
   `abs(predicted-heldout) <= training MAD + heldout P2 half-width`;
6. validation failure blocks model publication;
7. after validation PASS, refit the last up-to-five points including heldout.

Final model state also computes the governed EWMA alpha=1/3, current value, stability MAD and conservative P3 uncertainty half-width `max(final MAD, max P2 half-width)`.

Computed float identity is additionally bound by IEEE-754 binary64 big-endian hex in the deterministic model identity hash material; those helper encodings are not added to the frozen model-artifact field set.

## Capability model product

The model maps exactly to existing DB 1.6.0 `capability.capability_model`.

- subject_type = AIRCRAFT;
- subject_id = exact aircraft ID;
- model_spec/plugin/profile identities are exact adopted values;
- status = VALIDATED only after holdout PASS;
- model artifact URI is deterministic `tpaa-object://p3-capability/models/<model_id>.json`;
- artifact hash is SHA-256 over canonical artifact bytes;
- published_at remains null in Batch 2;
- no current/latest/default alias is created.

## Capability surface

The surface maps exactly to DB 1.6.0 `capability.capability_surface`.

- semantics: `REFERENCE_CONDITION_LONGITUDINAL_SESSION_ORDER`;
- axis: SESSION_ORDER;
- domain: only the final-refit observed session-order interval;
- extrapolation: forbidden;
- in-domain rows contain model value and governed uncertainty bounds;
- out-of-domain evaluation returns `OUT_OF_DOMAIN` and null value/bounds;
- dataset URI is deterministic `tpaa-object://p3-capability/surfaces/<surface_id>.json`;
- dataset bytes and SHA are deterministic.

No separate uncertainty dataset is required for profile v1 because each canonical surface row already carries exact uncertainty bounds; the optional Core field remains null.

## Managed-object proof

The contract tests physically pass model and surface bytes through the existing `LocalSealedObjectFlow` staging → verification → sealing path. The resulting object is then validated against P3 authority as:

- exact managed URI;
- exact SHA-256;
- sealed=true;
- gc_state=ACTIVE;
- deleted_at=null.

Tampered hash binding fails closed.

## Synthetic and Golden coverage

The static Golden fixture `tests/fixtures/m7/p3_capability_model_golden.json` freezes:

- segment hash;
- validation snapshot hash;
- training dataset hash;
- validation metrics;
- final intercept/slope/current/EWMA/MAD/uncertainty;
- model artifact SHA;
- UUIDv5 model identity;
- surface dataset SHA;
- UUIDv5 surface identity;
- in-domain surface rows.

The same logical inputs replayed in reverse caller order must reproduce the same training hash, artifact bytes, model identity, surface bytes and surface identity.

Additional negatives cover validation failure, out-of-domain evaluation and managed-object hash mismatch.

## Evidence-strength boundary

Profile v1's `independent_aircraft_count=1` is intentional AIRCRAFT-level evidence. Multiple aircraft are not pooled by this batch. Aircraft-model population inference and the stronger `INTRINSIC_CAPABILITY_ESTIMATE` wording remain unsupported and require later separately governed evidence/profile authority.

## Completion gate

This review is candidate evidence only. M7 Batch 2 is COMPLETE only after:

1. exact PR head Hosted CI 14/14 PASS;
2. guarded merge with expected head SHA;
3. actual merge parent verification;
4. protected-main exact merge-SHA push CI 14/14 PASS.

P3 remains NOT ADMITTED until protected-main M7 Exit GO.
