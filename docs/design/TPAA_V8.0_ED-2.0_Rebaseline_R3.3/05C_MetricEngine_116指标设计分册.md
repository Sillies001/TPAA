# ED-2.0 分册 C：Metric Engine 与 116 项 P1 指标

**定义权声明：** 116 项指标与 661 个输入绑定分别只由 `canonical/P1_METRIC_CATALOG.json` 与 `canonical/METRIC_INPUT_AUTHORITY_MATRIX.json` 唯一定义；本分册为只读可审阅投影。
**配套解释说明：** `05C1_116指标设计意图_适用边界_区别联系与计算方法说明.md` 逐项解释“为什么有这个指标、适用于什么对象、与相邻指标怎样区分、结果如何解释”。其公式段为 Catalog 镜像，不拥有第二定义权。


## 1. 唯一权威

指标完整算法合同只存在于 `canonical/P1_METRIC_CATALOG.json`；输入绑定只存在于 `canonical/METRIC_INPUT_AUTHORITY_MATRIX.json`。本分册中的表格与逐项说明均由当前 Catalog 生成，不拥有独立定义权。

## 2. 统一执行合同

Metric Engine 输入为 exact Context refs、World/Event/Relation refs、Evidence refs、subject identity 和 frozen profile parameters。普通 Metric 不直接读 raw source。

算法 identity 由 `algorithm_id + algorithm_version` 固定；Profile 不能选择公式/估计器/滤波拓扑/坐标定义/event semantics/output schema。非 raw dependency 必须绑定 operator/constant/upstream contract/state machine registry。

## 3. Typed Result

NUMERIC/TEXT/BOOLEAN/STRUCTURED 映射唯一值槽；VALID 时恰好填充与 value_kind 对应的值。STRUCTURED 绑定单一 JSON Schema；Session Time 在 structured JSON 内使用 decimal-string。

## 4. Observation Routing

- Aircraft performance → AIRCRAFT_CAP_L1_OBSERVATION / CAPABILITY_OBSERVATION；
- Mission-system performance → SYSTEM_PERFORMANCE_OBSERVATION；
- Reference/alignment quality → QUALITY_EVIDENCE_ONLY / METRIC_INSTANCE_EVIDENCE_ONLY。

## 5. P1 Longitudinal Eligibility

只有 `value_kind=NUMERIC && p1_longitudinal_trend_eligibility=true` 的指标进入 numeric longitudinal。当前 104 项：Aircraft 33，Mission-System 71。该能力在项目里程碑 M4 / `WS-LONGITUDINAL` 中闭合；这不是新的 P 能力层。


## 5A. Metric Family Applicability

R3.3 由 Catalog 的 `family_applicability_contracts` 冻结产品层适用性：SNS=RADAR measurement；PSV=IRST/EO；ESM=RWR/ESM；DL=DATALINK；FUS=FUSION；TRK/ID 按 Track / Association-Identification 产品能力适用。Applicability Gate 必须先于 input resolution；不适用对象即使字段偶然齐全也不得强行计算。

## 6. 116 项总表

| Code | Name | Family | Subject | Value | Delivery M | Delivery Batch | P1 Trend | Route |
|---|---|---|---|---|---|---|---|---|
| P1-QA-001 | REFERENCE_RELATIVE_STATE | REFERENCE_TRUTH | TARGET_PAIR | STRUCTURED | M2 | P1_FOUNDATION_32 | NO | METRIC_INSTANCE_EVIDENCE_ONLY |
| P1-QA-002 | REFERENCE_TRUTH_UNCERTAINTY | REFERENCE_TRUTH | TARGET_PAIR | STRUCTURED | M2 | P1_FOUNDATION_32 | NO | METRIC_INSTANCE_EVIDENCE_ONLY |
| P1-QA-006 | MEASUREMENT_ERROR_DECOMPOSITION | REFERENCE_TRUTH | MISSION_SYSTEM_INSTANCE | STRUCTURED | M2 | P1_FOUNDATION_32 | NO | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-QA-003 | SENSOR_TIME_OFFSET_OBSERVED | TIME_ALIGNMENT | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-QA-004 | SENSOR_TO_INS_LATENCY_OBSERVED | TIME_ALIGNMENT | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-QA-005 | INTERPOLATION_AGE_OBSERVED | TIME_ALIGNMENT | TARGET_PAIR | NUMERIC | M2 | P1_FOUNDATION_32 | NO | METRIC_INSTANCE_EVIDENCE_ONLY |
| P1-QA-007 | OWNSHIP_INS_TIME_UNCERTAINTY | TIME_ALIGNMENT | AIRCRAFT | NUMERIC | M2 | P1_FOUNDATION_32 | NO | METRIC_INSTANCE_EVIDENCE_ONLY |
| P1-QA-008 | TARGET_INS_TIME_UNCERTAINTY | TIME_ALIGNMENT | TARGET_PAIR | NUMERIC | M2 | P1_FOUNDATION_32 | NO | METRIC_INSTANCE_EVIDENCE_ONLY |
| P1-AIR-001 | MAX_ABS_BODY_ROLL_RATE_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M2 | P1_FOUNDATION_32 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-002 | MAX_NZ_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M2 | P1_FOUNDATION_32 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-003 | TRUE_HEADING_RATE_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M2 | P1_FOUNDATION_32 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-004 | SUSTAINED_TRUE_HEADING_RATE_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-005 | HORIZONTAL_TURN_RADIUS_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-006 | SUSTAINED_NZ_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-007 | TAS_MACH_ENVELOPE_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | STRUCTURED | M3 | P1_REMAINDER_84 | NO | CAPABILITY_OBSERVATION |
| P1-AIR-008 | MAX_ACCELERATION_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-009 | SUSTAINED_ACCELERATION_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-010 | ACCELERATION_TIME_BAND_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-011 | MAX_DECELERATION_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-012 | DECELERATION_TIME_BAND_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-013 | MAX_CLIMB_RATE_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-014 | SUSTAINED_CLIMB_RATE_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-015 | DIVE_ACCELERATION_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-022 | SUSTAINED_ROLL_RATE_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-023 | ROLL_TO_BANK_TIME_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-024 | NOSE_POINTING_RATE_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-025 | AOA_ENVELOPE_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | STRUCTURED | M3 | P1_REMAINDER_84 | NO | CAPABILITY_OBSERVATION |
| P1-AIR-026 | HIGH_AOA_DWELL_OBSERVED | AIRCRAFT_FLIGHT | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-016 | SPECIFIC_MECHANICAL_ENERGY_OBSERVED | AIRCRAFT_ENERGY | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-017 | SPECIFIC_ENERGY_RATE_OBSERVED | AIRCRAFT_ENERGY | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-018 | SPECIFIC_EXCESS_POWER_OBSERVED | AIRCRAFT_ENERGY | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-019 | ENERGY_RETENTION_OBSERVED | AIRCRAFT_ENERGY | AIRCRAFT | STRUCTURED | M3 | P1_REMAINDER_84 | NO | CAPABILITY_OBSERVATION |
| P1-AIR-020 | ENERGY_RECOVERY_TIME_OBSERVED | AIRCRAFT_ENERGY | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-021 | ENERGY_RECOVERY_RATE_OBSERVED | AIRCRAFT_ENERGY | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-038 | CLIMB_ENERGY_PARTITION_OBSERVED | AIRCRAFT_ENERGY | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-039 | DIVE_ENERGY_GAIN_OBSERVED | AIRCRAFT_ENERGY | AIRCRAFT | STRUCTURED | M3 | P1_REMAINDER_84 | NO | CAPABILITY_OBSERVATION |
| P1-AIR-027 | CONTROL_RESPONSE_DELAY_OBSERVED | AIRCRAFT_CONTROL_RESPONSE | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-035 | CONTROL_RESPONSE_GAIN_OBSERVED | AIRCRAFT_CONTROL_RESPONSE | AIRCRAFT | STRUCTURED | M3 | P1_REMAINDER_84 | NO | CAPABILITY_OBSERVATION |
| P1-AIR-036 | CONTROL_DEADBAND_OBSERVED | AIRCRAFT_CONTROL_RESPONSE | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-037 | RESPONSE_PERSISTENCE_OBSERVED | AIRCRAFT_CONTROL_RESPONSE | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-028 | CONTROL_INPUT_RATE_RMS | AIRCRAFT_HANDLING | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-029 | CONTROL_REVERSAL_COUNT | AIRCRAFT_HANDLING | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-030 | ATTITUDE_OSCILLATION_INDEX | AIRCRAFT_HANDLING | AIRCRAFT | STRUCTURED | M3 | P1_REMAINDER_84 | NO | CAPABILITY_OBSERVATION |
| P1-AIR-031 | JERK_RMS | AIRCRAFT_HANDLING | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-032 | FUEL_FLOW_OBSERVED | AIRCRAFT_PERSISTENCE | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-033 | FUEL_BURN_RATE_OBSERVED | AIRCRAFT_PERSISTENCE | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-AIR-034 | ENDURANCE_PROXY_OBSERVED | AIRCRAFT_PERSISTENCE | AIRCRAFT | NUMERIC | M3 | P1_REMAINDER_84 | YES | CAPABILITY_OBSERVATION |
| P1-SNS-001 | DETECTION_OPPORTUNITY_COVERAGE | SENSOR_DETECTION | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-002 | DETECTION_RATE_OBSERVED | SENSOR_DETECTION | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-003 | TIME_TO_FIRST_DETECTION | SENSOR_DETECTION | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-004 | FIRST_DETECTION_RANGE_OBSERVED | SENSOR_DETECTION | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-005 | RANGE_ERROR_BIAS | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-006 | RANGE_ERROR_RMSE | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-007 | RANGE_ERROR_P95 | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-008 | AZIMUTH_ERROR_BIAS | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-009 | AZIMUTH_ERROR_RMSE | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-010 | ELEVATION_ERROR_RMSE | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-011 | POSITION_3D_ERROR_RMSE | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-012 | RADIAL_VELOCITY_ERROR_RMSE | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-013 | CROSS_RANGE_ERROR_RMSE | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-014 | VERTICAL_ERROR_RMSE | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-015 | RANGE_ERROR_MAE | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-016 | RANGE_ERROR_P50 | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-017 | RANGE_ERROR_MAX_ABS | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-018 | AZIMUTH_ERROR_P95 | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-019 | ELEVATION_ERROR_BIAS | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-020 | ELEVATION_ERROR_P95 | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-SNS-021 | RADIAL_POSITION_ERROR_RMSE | SENSOR_ACCURACY | MISSION_SYSTEM_INSTANCE | NUMERIC | M2 | P1_FOUNDATION_32 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-TRK-001 | TRACK_INITIATION_TIME | TRACK_PERFORMANCE | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-TRK-002 | TRACK_POSITION_ERROR_RMSE | TRACK_PERFORMANCE | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-TRK-003 | TRACK_VELOCITY_ERROR_RMSE | TRACK_PERFORMANCE | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-TRK-004 | TRACK_CONTINUITY | TRACK_PERFORMANCE | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-TRK-005 | TRACK_DROP_COUNT | TRACK_PERFORMANCE | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-TRK-006 | TRACK_REACQUISITION_TIME | TRACK_PERFORMANCE | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-TRK-007 | TRACK_AGE | TRACK_PERFORMANCE | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ID-001 | ASSOCIATION_ACCURACY | ASSOCIATION_IDENTIFICATION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ID-002 | WRONG_ASSOCIATION_COUNT | ASSOCIATION_IDENTIFICATION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ID-003 | TRACK_SWAP_COUNT | ASSOCIATION_IDENTIFICATION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ID-004 | TRACK_SPLIT_COUNT | ASSOCIATION_IDENTIFICATION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ID-005 | TRACK_MERGE_COUNT | ASSOCIATION_IDENTIFICATION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ID-006 | DUPLICATE_TRACK_RATIO | ASSOCIATION_IDENTIFICATION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ID-007 | TRACK_IDENTITY_CONTINUITY | ASSOCIATION_IDENTIFICATION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ID-008 | IDENTIFICATION_ACCURACY | ASSOCIATION_IDENTIFICATION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ID-009 | FALSE_IDENTIFICATION_RATE | ASSOCIATION_IDENTIFICATION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ID-010 | UNKNOWN_DWELL_RATIO | ASSOCIATION_IDENTIFICATION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ID-011 | IDENTIFICATION_LATENCY | ASSOCIATION_IDENTIFICATION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ID-012 | IDENTIFICATION_STABILITY | ASSOCIATION_IDENTIFICATION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-PSV-001 | PASSIVE_LOS_ANGULAR_ERROR_RMSE | PASSIVE_SENSOR | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-PSV-002 | PASSIVE_LOS_RATE_ERROR_RMSE | PASSIVE_SENSOR | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-PSV-003 | PASSIVE_RANGE_ESTIMATE_ERROR_RMSE | PASSIVE_SENSOR | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-PSV-004 | PASSIVE_DETECTION_RATE | PASSIVE_SENSOR | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-PSV-005 | PASSIVE_TRACK_CONTINUITY | PASSIVE_SENSOR | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-PSV-006 | PASSIVE_REACQUISITION_TIME | PASSIVE_SENSOR | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-PSV-007 | PASSIVE_FALSE_TRACK_RATE | PASSIVE_SENSOR | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ESM-001 | EMITTER_DETECTION_RATE | RWR_ESM | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ESM-002 | EMITTER_BEARING_ERROR_RMSE | RWR_ESM | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ESM-003 | EMITTER_DETECTION_LATENCY | RWR_ESM | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ESM-004 | EMITTER_ASSOCIATION_ACCURACY | RWR_ESM | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ESM-005 | EMITTER_CLASSIFICATION_ACCURACY | RWR_ESM | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-ESM-006 | EMITTER_TRACK_CONTINUITY | RWR_ESM | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-DL-001 | MESSAGE_LATENCY | DATALINK | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-DL-002 | MESSAGE_JITTER | DATALINK | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-DL-003 | MESSAGE_LOSS_RATE | DATALINK | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-DL-004 | OUT_OF_ORDER_RATE | DATALINK | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-DL-005 | REMOTE_TRACK_AGE | DATALINK | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-DL-006 | REMOTE_TRACK_POSITION_ERROR_RMSE | DATALINK | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-DL-007 | REMOTE_TRACK_VELOCITY_ERROR_RMSE | DATALINK | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-DL-008 | REMOTE_TRACK_CONTINUITY | DATALINK | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-FUS-001 | FUSED_POSITION_ERROR_RMSE | SENSOR_FUSION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-FUS-002 | FUSED_VELOCITY_ERROR_RMSE | SENSOR_FUSION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-FUS-003 | FUSION_LATENCY | SENSOR_FUSION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-FUS-004 | FUSED_TRACK_CONTINUITY | SENSOR_FUSION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-FUS-005 | DUPLICATE_SUPPRESSION_RATE | SENSOR_FUSION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-FUS-006 | FUSION_ASSOCIATION_ACCURACY | SENSOR_FUSION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-FUS-007 | TRACK_HANDOVER_CONTINUITY | SENSOR_FUSION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |
| P1-FUS-008 | TRACK_HANDOVER_JUMP | SENSOR_FUSION | MISSION_SYSTEM_INSTANCE | NUMERIC | M3 | P1_REMAINDER_84 | YES | SYSTEM_PERFORMANCE_OBSERVATION |

## 7. 自动生成逐项合同镜像

### P1-QA-001 REFERENCE_RELATIVE_STATE

- Family: `REFERENCE_TRUTH`
- Subject: `TARGET_PAIR`
- Algorithm: `alg.tpaa.p1.qa.reference_relative_state@1.0.2`
- Semantic: `tpaa.p1.qa.reference_relative_state@1`
- Value kind/unit: `STRUCTURED` / `STRUCTURED`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `NO`
- Inputs: `own.position_ecef_m`, `target.position_ecef_m`, `own.velocity_ecef_mps`, `target.velocity_ecef_mps`, `own.attitude_quat`, `sensor_boresight_quat?`, `session_time_us`
- Window: pairwise aligned truth intervals
- Formula/contract: Publish exactly STRUCT_P1_QA_001_V1. Compute r_rel_ecef_m=p_target-p_own and v_rel_ecef_mps=v_target-v_own; range_m=||r_rel|| and range_rate_mps=(r_rel·v_rel)/||r_rel||. Transform r_rel into own-body to publish own_body_az_rad/own_body_el_rad. If sensor_boresight_quat is present and valid, also publish sensor_az_rad/sensor_el_rad and sensor_frame_status=AVAILABLE; otherwise both sensor angles are null and sensor_frame_status=NOT_CONFIGURED. The field set never changes.
- Validity: own/target identity resolved; aligned timestamps; positions finite; frame transform valid; range>0
- N/A: target/own truth unavailable or time alignment unresolved
- Evidence: own/target source artifact, time transforms, identity links, reference-relative-state series
- Golden: Synthetic two-aircraft ECEF trajectories with hand-computable range/az/el/range-rate including wrap and frame rotation.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-QA-002 REFERENCE_TRUTH_UNCERTAINTY

- Family: `REFERENCE_TRUTH`
- Subject: `TARGET_PAIR`
- Algorithm: `alg.tpaa.p1.qa.reference_truth_uncertainty@1.0.3`
- Semantic: `tpaa.p1.qa.reference_truth_uncertainty@1`
- Value kind/unit: `STRUCTURED` / `STRUCTURED`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `NO`
- Inputs: `own_position_uncertainty_ref`, `target_position_uncertainty_ref`, `own_attitude_uncertainty_ref`, `target_attitude_uncertainty_ref`, `time_alignment_uncertainty_ref`, `relative_state_jacobian`
- Window: same windows as P1-QA-001
- Formula/contract: Publish exactly STRUCT_P1_QA_002_V1. For every uncertainty_ref, consume CONTRACT_NAV_UNCERTAINTY_REPRESENTATION_V1. Convert COVARIANCE directly; convert SIGMA_1D to variance sigma^2; convert TWO_SIDED_HARD_BOUND ±b to variance b^2/3. Build P_inputs, propagate P_rel=J P_inputs J^T, then publish sigma_range_m, sigma_az_rad, sigma_el_rad and sigma_position_3d_m. No Evaluation Profile or manual fallback selects a representation or output field.
- Validity: all required uncertainty refs resolve to valid CONTRACT_NAV_UNCERTAINTY_REPRESENTATION_V1 records for the evaluation interval; units/frames compatible; relative_state_jacobian finite
- N/A: a required uncertainty representation/provenance is absent, invalid, unit/frame incompatible, or Jacobian unresolved
- Evidence: navigation quality metadata, alignment residuals, uncertainty profile, propagation trace
- Golden: Monte-Carlo/analytic covariance propagation fixture with known diagonal covariance and numeric tolerance.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-QA-006 MEASUREMENT_ERROR_DECOMPOSITION

- Family: `REFERENCE_TRUTH`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.qa.measurement_error_decomposition@1.0.3`
- Semantic: `tpaa.p1.qa.measurement_error_decomposition@1`
- Value kind/unit: `STRUCTURED` / `STRUCTURED`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `NO`
- Inputs: `residual_unit`, `error_domain`, `measurement_error`, `reference_uncertainty`, `alignment_uncertainty`, `sensor_measurement_uncertainty?`
- Window: all sensor/reference comparison windows
- Formula/contract: Publish exactly STRUCT_P1_QA_006_V1 with error_domain, residual_unit, raw_residual, reference_uncertainty, alignment_uncertainty, sensor_reported_uncertainty, normalized_residual and normalized_residual_status. raw_residual and uncertainty components are never algebraically subtracted. When sigma_ref, sigma_align and sigma_sensor are all finite and the combined denominator is >0, normalized_residual=raw_residual/sqrt(sigma_ref^2+sigma_align^2+sigma_sensor^2) and status=VALID; otherwise normalized_residual=null and status=INSUFFICIENT_UNCERTAINTY. Missing sensor uncertainty is represented as null, not by removing the field.
- Validity: residual and at least reference/alignment quality available
- N/A: reference quality invalid
- Evidence: residual sample, P1-QA-002, P1-QA-003/004/005, sensor quality flags
- Golden: Fixture where same residual under different truth uncertainty retains equal raw error but different normalized residual.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-QA-003 SENSOR_TIME_OFFSET_OBSERVED

- Family: `TIME_ALIGNMENT`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.qa.sensor_time_offset@1.0.4`
- Semantic: `tpaa.p1.qa.sensor_time_offset@2`
- Value kind/unit: `NUMERIC` / `us`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `sensor_timestamp_mapped_to_session_time_us`, `aligned_session_time_us`, `time_transform_id`
- Window: stable source-clock segment
- Formula/contract: Within each SM_CLOCK_SEGMENT_V1 stable clock segment, offset_us=aligned_session_time_us-sensor_timestamp_mapped_to_session_time_us. Primary Metric value=MEAN_V1(offset_us) arithmetic bias for that segment. RMS_V1(offset_us) RMSE and QUANTILE_HF7_V1(offset_us,0.95) P95 are mandatory diagnostic Evidence fields, not additional Metric values. One segment produces one MetricInstance/Observation with its exact time range; never aggregate samples across a clock-segment boundary before publication.
- Validity: sensor clock segment resolved; transform valid
- N/A: sensor has no timestamp or transform unresolved
- Evidence: source clock segment, time transform, matched sensor records
- Golden: Clock fixture with fixed +2000 us offset and reset segment; verify per-segment bias and no cross-reset mixing.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-QA-004 SENSOR_TO_INS_LATENCY_OBSERVED

- Family: `TIME_ALIGNMENT`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.qa.sensor_to_ins_latency@1.0.3`
- Semantic: `tpaa.p1.qa.sensor_to_ins_latency@2`
- Value kind/unit: `NUMERIC` / `us`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `sensor_measurement_effective_time_us`, `referenced_ownship_state_effective_time_us`
- Window: sensor measurement windows
- Formula/contract: latency_us=sensor_measurement_effective_time_us-referenced_ownship_state_effective_time_us. Primary Metric value=MEDIAN_V1(latency_us) over eligible samples; QUANTILE_HF7_V1 P95 latency is mandatory diagnostic Evidence. Never infer latency when timestamps have unresolved time bases.
- Validity: both effective times resolved to Session Time
- N/A: one or both effective times unresolved
- Evidence: sensor record, ownship canonical state, time transforms
- Golden: Fixture with known 40 ms producer delay and irregular samples; verify median/P95.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-QA-005 INTERPOLATION_AGE_OBSERVED

- Family: `TIME_ALIGNMENT`
- Subject: `TARGET_PAIR`
- Algorithm: `alg.tpaa.p1.qa.interpolation_age@1.0.2`
- Semantic: `tpaa.p1.qa.interpolation_age@2`
- Value kind/unit: `NUMERIC` / `us`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `NO`
- Inputs: `measurement_time_us`, `left_truth_time_us`, `right_truth_time_us`, `profile.max_gap_us`
- Window: measurement-to-reference matching
- Formula/contract: For every measurement, age_us=max(measurement_time_us-left_truth_time_us, right_truth_time_us-measurement_time_us). Samples with age_us>max_gap_us are ineligible. Primary Metric value=MEDIAN_V1(age_us); QUANTILE_HF7_V1(age_us,0.95) and max(age_us) are mandatory diagnostic Evidence. max_gap_us is the only metric-profile eligibility parameter.
- Validity: bracketing truth points exist and gap <= profile max_gap
- N/A: no valid bracketing points
- Evidence: measurement row, truth rows, interpolation profile
- Golden: Irregular truth samples with known bracketing ages and an over-gap case that must become N/A.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-QA-007 OWNSHIP_INS_TIME_UNCERTAINTY

- Family: `TIME_ALIGNMENT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.qa.ownship_ins_time_uncertainty@1.0.2`
- Semantic: `tpaa.p1.qa.ownship_ins_time_uncertainty@1`
- Value kind/unit: `NUMERIC` / `us`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `NO`
- Inputs: `ownship_nav_time_uncertainty_ref`, `ownship_clock_transform_residual_sigma_us`
- Window: reference-truth windows
- Formula/contract: Resolve ownship_nav_time_uncertainty_ref under CONTRACT_NAV_UNCERTAINTY_REPRESENTATION_V1. Use SIGMA_1D directly or convert TWO_SIDED_HARD_BOUND ±b to sigma=b/sqrt(3); COVARIANCE is permitted only as a 1x1 time-variance record. Combine independent source-clock and TimeTransform residual uncertainty as sigma_time_us=sqrt(sigma_source_us^2+sigma_transform_us^2).
- Validity: ownship time uncertainty ref and TimeTransform residual sigma resolve for the same interval with compatible units
- N/A: ownship uncertainty representation/provenance or TimeTransform residual uncertainty unavailable/invalid
- Evidence: ownship INS clock metadata + TimeTransform residuals
- Golden: Known ±500 us bound and transform residual fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-QA-008 TARGET_INS_TIME_UNCERTAINTY

- Family: `TIME_ALIGNMENT`
- Subject: `TARGET_PAIR`
- Algorithm: `alg.tpaa.p1.qa.target_ins_time_uncertainty@1.0.2`
- Semantic: `tpaa.p1.qa.target_ins_time_uncertainty@1`
- Value kind/unit: `NUMERIC` / `us`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `NO`
- Inputs: `target_nav_time_uncertainty_ref`, `target_clock_transform_residual_sigma_us`
- Window: reference-truth windows
- Formula/contract: Resolve target_nav_time_uncertainty_ref under CONTRACT_NAV_UNCERTAINTY_REPRESENTATION_V1. Use SIGMA_1D directly or convert TWO_SIDED_HARD_BOUND ±b to sigma=b/sqrt(3); COVARIANCE is permitted only as a 1x1 time-variance record. Combine independent source-clock and TimeTransform residual uncertainty as sigma_time_us=sqrt(sigma_source_us^2+sigma_transform_us^2).
- Validity: target time uncertainty ref and TimeTransform residual sigma resolve for the same interval with compatible units
- N/A: target uncertainty representation/provenance or TimeTransform residual uncertainty unavailable/invalid
- Evidence: target INS clock metadata + TimeTransform residuals
- Golden: Known ±800 us bound and transform residual fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-001 MAX_ABS_BODY_ROLL_RATE_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.max_abs_body_roll_rate@1.0.1`
- Semantic: `tpaa.p1.air.max_abs_body_roll_rate@1`
- Value kind/unit: `NUMERIC` / `rad/s`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `body_p_rad_s`, `session_time_us`, `quality_mask`, `profile.min_coverage`, `profile.max_gap_us`
- Window: approved maneuver/performance windows
- Formula/contract: max(abs(body_p_rad_s)) over validity-piece samples in the eligible window. The window is eligible only when valid covered duration/window duration >= min_coverage and no internal gap exceeds max_gap_us.
- Validity: body_p valid; eligible-window coverage >= min_coverage; no internal gap > max_gap_us; unit/frame known
- N/A: body angular-rate channel unavailable; coverage < min_coverage; or gap > max_gap_us
- Evidence: canonical body-rate rows, window definition, quality/validity events, evaluation profile id/version/hash with min_coverage/max_gap_us
- Golden: Synthetic constant/peak p series including high-pitch case; must not substitute Euler roll derivative.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-002 MAX_NZ_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.max_nz@1.0.1`
- Semantic: `tpaa.p1.air.max_nz@1`
- Value kind/unit: `NUMERIC` / `g`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `nz_g`, `session_time_us`, `quality_mask`
- Window: approved maneuver/performance windows
- Formula/contract: Primary Metric value = max(valid nz_g) over the eligible window. Diagnostic Evidence records min(valid nz_g); that diagnostic value is not part of the Metric value/output schema.
- Validity: Nz calibrated and valid
- N/A: Nz channel unavailable/invalid
- Evidence: canonical Nz rows + quality + eligible window + diagnostic min_nz_g
- Golden: Fixture with known peaks, gaps and invalid samples; invalid peak excluded.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-003 TRUE_HEADING_RATE_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.true_heading_rate@1.0.0`
- Semantic: `tpaa.p1.air.true_heading_rate@1`
- Value kind/unit: `NUMERIC` / `rad/s`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `heading_true_rad`, `session_time_us`, `profile.derivative_window_s`, `profile.max_gap_us`
- Window: turn-capable windows
- Formula/contract: Unwrap heading_true_rad, then compute angular rate with DERIVATIVE_LLS_V1: local first-order least-squares slope over the declared derivative_window_s using only same-validity-piece samples and never bridging max_gap_us. Metric value is abs(rate).
- Validity: true heading valid; gap control; unwrap valid
- N/A: heading unavailable or eligible duration too short
- Evidence: heading series + derivative profile + window
- Golden: 359°→1° wrap fixture and constant-rate turn; verify no 358° spike.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-004 SUSTAINED_TRUE_HEADING_RATE_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.sustained_true_heading_rate@1.0.2`
- Semantic: `tpaa.p1.air.sustained_true_heading_rate@1`
- Value kind/unit: `NUMERIC` / `rad/s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `heading_true_rad`, `session_time_us`, `profile.sustain_duration_s`, `profile.min_coverage`, `profile.max_gap_us`
- Window: turn windows with minimum sustained duration
- Formula/contract: Use the P1-AIR-003 instantaneous absolute heading-rate series. Inside SM_VALIDITY_PIECE_V1 compute ROLLING_MEDIAN_V1 over sustain_duration_s; a window is eligible only when min_coverage is met and no internal gap exceeds max_gap_us. Primary Metric value=maximum eligible rolling-median heading rate; the exact supporting dwell interval is mandatory Evidence, not an additional result value.
- Validity: P1-AIR-003 valid; enough continuous duration
- N/A: insufficient continuous duration
- Evidence: heading series + sustained window + quality
- Golden: Constant-rate turn plus short spike; sustained result must reject transient spike.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-005 HORIZONTAL_TURN_RADIUS_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.horizontal_turn_radius@1.0.2`
- Semantic: `tpaa.p1.air.horizontal_turn_radius@2`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `ground_speed_mps`, `track_true_rad`, `session_time_us`, `profile.derivative_window_s`, `profile.max_gap_us`, `profile.min_turn_rate_rad_s`
- Window: turn windows
- Formula/contract: Compute horizontal speed V_horizontal and unwrap track_true_rad. Compute track-rate omega with DERIVATIVE_LLS_V1 using derivative_window_s without bridging max_gap_us. For samples with abs(omega)>=min_turn_rate_rad_s, R=V_horizontal/abs(omega). Primary Metric value=MEDIAN_V1(R) over the eligible turn interval; min(R) is mandatory diagnostic Evidence, not an additional Metric value.
- Validity: ground speed and track valid; |track_rate|>epsilon
- N/A: track/ground speed absent or no valid turn interval
- Evidence: velocity/track rows + derivative/window profile
- Golden: Circular horizontal trajectory with known radius; verify recovered radius within tolerance.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-006 SUSTAINED_NZ_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.sustained_nz@1.0.2`
- Semantic: `tpaa.p1.air.sustained_nz@1`
- Value kind/unit: `NUMERIC` / `g`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `nz_g`, `session_time_us`, `profile.sustain_duration_s`, `profile.min_coverage`, `profile.max_gap_us`
- Window: maneuver windows
- Formula/contract: Within each SM_VALIDITY_PIECE_V1 interval compute ROLLING_MEDIAN_V1(nz_g) over sustain_duration_s. A rolling window is eligible only when min_coverage is met and no internal gap exceeds max_gap_us. Primary Metric value=maximum eligible rolling-median Nz; the exact supporting dwell interval is mandatory Evidence.
- Validity: Nz valid and continuous for sustain duration
- N/A: insufficient valid dwell
- Evidence: Nz rows + sustain window
- Golden: Short spike vs sustained plateau fixture; plateau selected.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-007 TAS_MACH_ENVELOPE_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.tas_mach_envelope@1.0.2`
- Semantic: `tpaa.p1.air.tas_mach_envelope@1`
- Value kind/unit: `STRUCTURED` / `STRUCTURED`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `NO`
- Inputs: `tas_mps`, `mach`, `session_time_us`
- Window: eligible flight windows
- Formula/contract: Publish exactly STRUCT_P1_AIR_007_V1 with fixed tas and mach subrecords. For each channel independently after validity filtering: N>=1 publishes status=VALID, n=N, min/max and QUANTILE_HF7_V1 P05/P50/P95; N=0 publishes status=INSUFFICIENT_DATA, n=0 and all numeric fields null. The Metric is N_A only when both subrecords are INSUFFICIENT_DATA. Altitude/context tags remain Observation/Evidence context and are not additional result fields.
- Validity: at least one finite validity-filtered TAS or Mach sample in the eligible flight window; units/context known
- N/A: both TAS and Mach have zero finite validity-filtered samples in the eligible window
- Evidence: validity-filtered TAS/Mach rows, per-channel finite sample counts, quantile outputs, altitude/context tags
- Golden: Known sequence with invalid extreme; verify invalid sample excluded and quantiles stable.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-008 MAX_ACCELERATION_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.max_tas_acceleration@1.0.1`
- Semantic: `tpaa.p1.air.max_tas_acceleration@1`
- Value kind/unit: `NUMERIC` / `m/s^2`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `tas_mps`, `session_time_us`, `profile.derivative_window_s`, `profile.max_gap_us`
- Window: acceleration windows
- Formula/contract: Compute a_TAS = d(TAS)/dt with DERIVATIVE_LLS_V1 over derivative_window_s without bridging max_gap_us; publish the maximum eligible a_TAS.
- Validity: DERIVATIVE_LLS_V1 returns at least one finite a_TAS estimate from >=3 distinct timestamps inside one validity piece under derivative_window_s/max_gap_us
- N/A: TAS unavailable or DERIVATIVE_LLS_V1 returns no finite eligible estimate
- Evidence: TAS series + derivative/filter profile
- Golden: Linear TAS ramp with injected noise/gap; recover slope within tolerance.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-009 SUSTAINED_ACCELERATION_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.sustained_tas_acceleration@1.0.2`
- Semantic: `tpaa.p1.air.sustained_tas_acceleration@1`
- Value kind/unit: `NUMERIC` / `m/s^2`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `tas_mps`, `session_time_us`, `profile.derivative_window_s`, `profile.sustain_duration_s`, `profile.min_coverage`, `profile.max_gap_us`
- Window: acceleration windows
- Formula/contract: Compute a_TAS=d(TAS)/dt with DERIVATIVE_LLS_V1 using derivative_window_s/max_gap_us inside SM_VALIDITY_PIECE_V1. Apply ROLLING_MEDIAN_V1 over sustain_duration_s and require min_coverage. Primary Metric value=maximum eligible rolling-median acceleration; the supporting dwell interval is mandatory Evidence.
- Validity: P1-AIR-008 derivative valid and sustain duration met
- N/A: no sustained valid interval
- Evidence: TAS derivative + sustain profile
- Golden: Transient spike plus steady acceleration fixture; steady interval must dominate.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-010 ACCELERATION_TIME_BAND_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.acceleration_time_band@1.0.3`
- Semantic: `tpaa.p1.air.acceleration_time_band@1`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `tas_mps`, `mach`, `session_time_us`, `profile.lower_speed_bound_mps`, `profile.upper_speed_bound_mps`, `profile.max_gap_us`
- Window: profile-defined speed/Mach band windows
- Formula/contract: Within one SM_VALIDITY_PIECE_V1, elapsed time runs from the first valid upward crossing of lower_speed_bound_mps to the first subsequent valid upward crossing of upper_speed_bound_mps. A validity-piece boundary or gap > max_gap_us invalidates the candidate; crossings may not span a reset/discontinuity. Bounds are Evaluation Profile data.
- Validity: both declared speed-bound crossings occur in order inside the same SM_VALIDITY_PIECE_V1 and no gap between supporting samples exceeds max_gap_us
- N/A: lower or upper configured bound is not crossed in order inside one validity piece; any supporting gap exceeds max_gap_us; or speed data are invalid
- Evidence: TAS/Mach series + band profile + crossing evidence
- Golden: Synthetic monotonic ramp crossing configured band; verify exact crossing interpolation and N/A when upper not reached.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-011 MAX_DECELERATION_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.max_tas_deceleration@1.0.1`
- Semantic: `tpaa.p1.air.max_tas_deceleration@1`
- Value kind/unit: `NUMERIC` / `m/s^2`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `tas_mps`, `session_time_us`, `profile.derivative_window_s`, `profile.max_gap_us`
- Window: deceleration windows
- Formula/contract: Compute a_TAS=d(TAS)/dt with DERIVATIVE_LLS_V1 using derivative_window_s/max_gap_us inside SM_VALIDITY_PIECE_V1. Over eligible samples with a_TAS<0, publish abs(min(a_TAS)).
- Validity: TAS derivative valid
- N/A: no valid deceleration interval
- Evidence: TAS derivative + quality
- Golden: Linear deceleration ramp; verify magnitude and gap rejection.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-012 DECELERATION_TIME_BAND_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.deceleration_time_band@1.0.3`
- Semantic: `tpaa.p1.air.deceleration_time_band@1`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `tas_mps`, `mach`, `session_time_us`, `profile.lower_speed_bound_mps`, `profile.upper_speed_bound_mps`, `profile.max_gap_us`
- Window: profile-defined deceleration bands
- Formula/contract: Within one SM_VALIDITY_PIECE_V1, elapsed time runs from the first valid downward crossing of upper_speed_bound_mps to the first subsequent valid downward crossing of lower_speed_bound_mps. A gap > max_gap_us or validity-piece boundary invalidates the candidate. Publish elapsed seconds; lower_speed_bound_mps must be < upper_speed_bound_mps.
- Validity: both declared downward band crossings occur in order inside one validity piece with every supporting gap <=max_gap_us
- N/A: lower/upper bound not crossed in order inside one validity piece; a supporting gap exceeds max_gap_us; or speed is invalid
- Evidence: TAS/Mach + profile + crossing evidence
- Golden: Known ramp from upper to lower threshold; verify duration.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-013 MAX_CLIMB_RATE_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.max_climb_rate@1.0.2`
- Semantic: `tpaa.p1.air.max_climb_rate@1`
- Value kind/unit: `NUMERIC` / `m/s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `alt_msl_m`, `vertical_speed_mps?`, `session_time_us`, `profile.derivative_window_s`, `profile.max_gap_us`
- Window: climb windows
- Formula/contract: Compute climb_rate_mps=d(alt_msl_m)/dt with DERIVATIVE_LLS_V1 using derivative_window_s/max_gap_us inside SM_VALIDITY_PIECE_V1. Publish max(climb_rate_mps) over eligible positive-climb samples. When a canonical vertical_speed channel exists, diagnostic Evidence records it as a cross-check; it is never substituted into the Metric value.
- Validity: altitude MSL valid; derivative/gap profile valid
- N/A: altitude unavailable or no positive climb interval
- Evidence: altitude series + vertical-speed cross-check + profile
- Golden: Linear altitude ramp and optional consistent vertical-speed channel; verify rate.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-014 SUSTAINED_CLIMB_RATE_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.sustained_climb_rate@1.0.2`
- Semantic: `tpaa.p1.air.sustained_climb_rate@1`
- Value kind/unit: `NUMERIC` / `m/s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `alt_msl_m`, `session_time_us`, `profile.derivative_window_s`, `profile.sustain_duration_s`, `profile.min_coverage`, `profile.max_gap_us`
- Window: climb windows
- Formula/contract: Compute climb_rate_mps=d(alt_msl_m)/dt with DERIVATIVE_LLS_V1 using derivative_window_s/max_gap_us. Within SM_VALIDITY_PIECE_V1 apply ROLLING_MEDIAN_V1 over sustain_duration_s and require min_coverage. Primary Metric value=maximum eligible rolling-median climb rate; the supporting dwell interval is mandatory Evidence.
- Validity: continuous climb duration met
- N/A: no sustained climb interval
- Evidence: altitude derivative + sustain window
- Golden: Short climb spike + steady climb; steady selected.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-015 DIVE_ACCELERATION_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.dive_acceleration@1.0.1`
- Semantic: `tpaa.p1.air.dive_acceleration@1`
- Value kind/unit: `NUMERIC` / `m/s^2`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `tas_mps`, `alt_msl_m`, `session_time_us`, `profile.derivative_window_s`, `profile.max_gap_us`, `profile.min_descent_rate_mps`
- Window: dive windows
- Formula/contract: Compute dTAS/dt and dh/dt with DERIVATIVE_LLS_V1 using derivative_window_s and max_gap_us. A sample is dive-eligible only when dh/dt <= -min_descent_rate_mps. The metric value is the fixed P95 of eligible dTAS/dt samples in the dive window; also retain altitude-loss context in Evidence. No Profile parameter may select a different summary statistic.
- Validity: TAS/altitude valid; descent condition met
- N/A: no valid dive interval
- Evidence: TAS + altitude + derived rates
- Golden: Synthetic descending accelerating segment and level acceleration; only dive segment eligible.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-022 SUSTAINED_ROLL_RATE_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.sustained_body_roll_rate@1.0.2`
- Semantic: `tpaa.p1.air.sustained_body_roll_rate@1`
- Value kind/unit: `NUMERIC` / `rad/s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `body_p_rad_s`, `session_time_us`, `profile.sustain_duration_s`, `profile.min_coverage`, `profile.max_gap_us`
- Window: roll windows
- Formula/contract: Within SM_VALIDITY_PIECE_V1 compute ROLLING_MEDIAN_V1(abs(body_roll_rate_p_rad_s)) over sustain_duration_s. Require min_coverage and no gap>max_gap_us. Primary Metric value=maximum eligible rolling-median roll rate; the supporting dwell interval is mandatory Evidence.
- Validity: p valid and sustain duration met
- N/A: no sustained roll interval
- Evidence: body-rate series + sustain profile
- Golden: Transient roll spike vs plateau fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-023 ROLL_TO_BANK_TIME_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.roll_to_bank_time@1.0.1`
- Semantic: `tpaa.p1.air.roll_to_bank_time@1`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `roll_rad`, `body_p_rad_s?`, `session_time_us`, `roll_onset_time_us`, `profile.bank_delta_rad`, `profile.bank_tolerance_rad`, `profile.achievement_persistence_s`, `profile.max_gap_us`
- Window: roll transition windows
- Formula/contract: Starting at supplied roll_onset_time_us inside SM_VALIDITY_PIECE_V1, find the first time abs(roll_rad-roll_at_onset)>=bank_delta_rad and the attained side remains within bank_tolerance_rad for achievement_persistence_s. Any gap > max_gap_us before achievement invalidates the event. Publish elapsed time; roll onset is supplied and is never rediscovered inside this metric.
- Validity: roll attitude valid; onset/target persistence resolved
- N/A: configured bank change not reached or ambiguous onset
- Evidence: roll series + onset/target markers + profile
- Golden: Synthetic 0→60° transition with overshoot; verify first stable crossing, not first noisy crossing.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-024 NOSE_POINTING_RATE_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.nose_pointing_rate@2.0.0`
- Semantic: `tpaa.p1.air.nose_pointing_rate@2`
- Value kind/unit: `NUMERIC` / `rad/s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `attitude_quat`, `session_time_us`, `profile.max_gap_us`
- Window: maneuver windows
- Formula/contract: Transform aircraft body +X boresight by attitude_quat into the declared inertial/local frame. For each consecutive valid sample pair with 0<dt_us<=max_gap_us, GEODESIC_PAIR_RATE_V1 computes omega_i. Primary Metric value=QUANTILE_HF7_V1(omega_i,0.95) over finite eligible pair rates. The pair-rate series is retained as Evidence and is not itself stored in the scalar Metric value.
- Validity: at least one finite GEODESIC_PAIR_RATE_V1 pair rate exists under max_gap_us; attitude/frame convention resolved
- N/A: attitude/frame unavailable or no finite eligible pair rate
- Evidence: attitude series + frame definition + derivative profile
- Golden: Quaternion fixture with known constant yaw/pitch slew; verify angular-rate magnitude.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-025 AOA_ENVELOPE_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.aoa_envelope@2.0.0`
- Semantic: `tpaa.p1.air.aoa_envelope@2`
- Value kind/unit: `STRUCTURED` / `STRUCTURED`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `NO`
- Inputs: `aoa_rad`, `session_time_us`
- Window: eligible maneuver windows
- Formula/contract: Publish exactly STRUCT_P1_AIR_025_V1 over the eligible window: sample_count=N plus min_rad, max_rad and QUANTILE_HF7_V1 P05/P50/P95 as p05_rad/p50_rad/p95_rad. Require N>=1 finite AoA sample. P1 does not interpret these observed statistics as a stall boundary; any later stall-limit claim requires a separate versioned reference contract.
- Validity: at least one finite AoA sample exists in the eligible window; AoA unit/frame convention resolved
- N/A: no finite AoA sample in the eligible window or AoA convention unresolved
- Evidence: AoA rows + calibration/version + quality
- Golden: Known AoA series with invalid outlier; quantiles exclude invalid sample.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-026 HIGH_AOA_DWELL_OBSERVED

- Family: `AIRCRAFT_FLIGHT`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.high_aoa_dwell@1.0.3`
- Semantic: `tpaa.p1.air.high_aoa_dwell@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `aoa_rad`, `session_time_us`, `profile.aoa_threshold_rad`, `profile.min_dwell_s`, `profile.max_gap_us`
- Window: profile-defined high-AoA windows
- Formula/contract: Inside SM_VALIDITY_PIECE_V1, form high-AoA episodes where aoa_rad>=aoa_threshold_rad continuously for at least min_dwell_s without a gap > max_gap_us. dwell_ratio=sum(qualified high-AoA episode duration)/eligible_time. aoa_threshold_rad is Evaluation Profile data, not a stall/capability limit.
- Validity: AoA finite; profile.aoa_threshold_rad/profile.min_dwell_s/profile.max_gap_us resolved; eligible time >0
- N/A: AoA unavailable; profile parameters unresolved; or no eligible time
- Evidence: AoA series + threshold profile + intervals
- Golden: Piecewise AoA fixture with known dwell fraction.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-016 SPECIFIC_MECHANICAL_ENERGY_OBSERVED

- Family: `AIRCRAFT_ENERGY`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.specific_mechanical_energy@1.0.0`
- Semantic: `tpaa.p1.air.specific_mechanical_energy@1`
- Value kind/unit: `NUMERIC` / `J/kg`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `tas_mps`, `alt_msl_m`
- Window: eligible flight windows
- Formula/contract: E_s = G0_MPS2*alt_msl_m + 0.5*TAS^2 using the exact constant-registry value; preserve altitude datum metadata and never mix altitude datums inside one result.
- Validity: TAS and MSL altitude valid; no mixed altitude datum
- N/A: TAS or MSL altitude unavailable
- Evidence: TAS/altitude rows + datum metadata
- Golden: Hand-computable TAS/altitude points; exact energy within tolerance.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-017 SPECIFIC_ENERGY_RATE_OBSERVED

- Family: `AIRCRAFT_ENERGY`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.specific_energy_rate@1.0.2`
- Semantic: `tpaa.p1.air.specific_energy_rate@1`
- Value kind/unit: `NUMERIC` / `W/kg`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `tas_mps`, `alt_msl_m`, `session_time_us`, `profile.derivative_window_s`, `profile.max_gap_us`
- Window: eligible flight windows
- Formula/contract: Compute E_s from P1-AIR-016 at every eligible sample, then compute dE_s/dt with DERIVATIVE_LLS_V1 over derivative_window_s within the same validity piece and never bridge max_gap_us. The derivative estimator/filter family is fixed by this Algorithm Contract; Profile controls only derivative_window_s and max_gap_us.
- Validity: P1-AIR-016 provides finite energy samples and DERIVATIVE_LLS_V1 returns at least one finite dE_s/dt estimate under derivative_window_s/max_gap_us
- N/A: P1-AIR-016 unavailable or no finite derivative estimate is produced
- Evidence: energy series + filter/derivative profile
- Golden: Analytic climb/acceleration fixture with known dE/dt.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-018 SPECIFIC_EXCESS_POWER_OBSERVED

- Family: `AIRCRAFT_ENERGY`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.specific_excess_power_observed@1.0.1`
- Semantic: `tpaa.p1.air.specific_excess_power_observed@1`
- Value kind/unit: `NUMERIC` / `m/s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `tas_mps`, `alt_msl_m`, `session_time_us`, `profile.derivative_window_s`, `profile.max_gap_us`
- Window: eligible flight windows
- Formula/contract: Inside SM_VALIDITY_PIECE_V1 compute dh/dt and d(TAS)/dt with DERIVATIVE_LLS_V1 using the same derivative_window_s/max_gap_us. Then P_s_obs = dh/dt + (TAS/G0_MPS2)*d(TAS)/dt. This is observed kinematic specific excess power, not a thrust-drag model.
- Validity: TAS/altitude derivatives valid
- N/A: TAS or altitude derivative invalid
- Evidence: TAS/altitude + derivatives + profile
- Golden: Analytic constant climb and acceleration fixture; compare closed-form Ps.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-019 ENERGY_RETENTION_OBSERVED

- Family: `AIRCRAFT_ENERGY`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.energy_retention@1.0.3`
- Semantic: `tpaa.p1.air.energy_retention@1`
- Value kind/unit: `STRUCTURED` / `STRUCTURED`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `NO`
- Inputs: `specific_mechanical_energy`, `session_time_us`, `window_start/end`
- Window: maneuver windows
- Formula/contract: Publish exactly STRUCT_P1_AIR_019_V1. Using P1-AIR-016 at exact maneuver-window endpoints, retention_ratio=E_s_end/E_s_start only when abs(E_s_start)>ENERGY_DENOM_EPS_J_PER_KG and delta_E_s_j_per_kg=E_s_end-E_s_start. median_energy_rate_w_per_kg=MEDIAN_V1 of finite valid P1-AIR-017 samples strictly inside the same window; if none exist, set that field null and median_energy_rate_status=INSUFFICIENT_RATE_SAMPLES while endpoint fields remain valid. Do not clamp an ineligible denominator.
- Validity: finite P1-AIR-016 values available at both exact maneuver-window endpoints and abs(E_s_start)>ENERGY_DENOM_EPS_J_PER_KG
- N/A: start/end energy unavailable or denominator guard fails; absence of interior P1-AIR-017 samples nulls only median_energy_rate and does not invalidate retention_ratio/delta_E_s
- Evidence: exact start/end energy rows, window endpoints, finite interior P1-AIR-017 sample count, retention/delta/median-rate field statuses
- Golden: Known 100→90 energy window gives 0.9 retention with matching delta.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-020 ENERGY_RECOVERY_TIME_OBSERVED

- Family: `AIRCRAFT_ENERGY`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.energy_recovery_time@1.0.1`
- Semantic: `tpaa.p1.air.energy_recovery_time@1`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `specific_mechanical_energy`, `session_time_us`, `maneuver_end_time_us`, `pre_event_reference_energy`, `post_event_min_energy`, `profile.recovery_fraction`, `profile.max_recovery_window_s`, `profile.min_crossing_persistence_s`, `profile.max_gap_us`
- Window: post-maneuver recovery windows
- Formula/contract: Let loss=pre_event_reference_energy-post_event_min_energy and recovery_target=post_event_min_energy+recovery_fraction*loss. From maneuver_end_time_us, search no longer than max_recovery_window_s inside SM_POST_MANEUVER_RECOVERY_WINDOW_V1 without bridging any gap > max_gap_us. Publish elapsed time to the first crossing E_s>=recovery_target that remains continuously above target for min_crossing_persistence_s. If loss<=0, the window terminates, or no persistent crossing occurs, return the specified N_A/INSUFFICIENT_DATA status.
- Validity: pre-event reference and post-event continuous energy available
- N/A: criterion not reached before window end or data insufficient
- Evidence: event marker + energy series + recovery profile
- Golden: Synthetic energy drop then recovery; verify crossing time and N/A if not recovered.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-021 ENERGY_RECOVERY_RATE_OBSERVED

- Family: `AIRCRAFT_ENERGY`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.energy_recovery_rate@1.0.4`
- Semantic: `tpaa.p1.air.energy_recovery_rate@1`
- Value kind/unit: `NUMERIC` / `W/kg`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `specific_energy_rate`, `recovery_window`, `profile.max_gap_us`
- Window: post-maneuver recovery windows
- Formula/contract: Within the supplied post-maneuver recovery interval qualified by SM_POST_MANEUVER_RECOVERY_WINDOW_V1 and SM_VALIDITY_PIECE_V1, never bridge a gap > max_gap_us. Select finite P1-AIR-017 samples with dE_s/dt>0 and publish MEDIAN_V1 of those strictly positive rates. If the recovery interval is resolved but contains no strictly positive finite P1-AIR-017 sample, return INSUFFICIENT_DATA; if the recovery interval itself is unresolved, return N_A. Profile cannot select another statistic.
- Validity: qualified recovery interval resolved; at least one finite P1-AIR-017 sample exists inside the interval; no supporting gap exceeds max_gap_us
- N/A: N_A when the recovery interval is unresolved; INSUFFICIENT_DATA when the resolved interval contains no strictly positive finite P1-AIR-017 sample
- Evidence: energy-rate series + recovery window
- Golden: Constant recovery slope fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-038 CLIMB_ENERGY_PARTITION_OBSERVED

- Family: `AIRCRAFT_ENERGY`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.climb_energy_partition@1.0.2`
- Semantic: `tpaa.p1.air.climb_energy_partition@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `tas_mps`, `alt_msl_m`, `session_time_us`, `profile.derivative_window_s`, `profile.max_gap_us`
- Window: positive-energy climb windows
- Formula/contract: Use P1-AIR-017 dE_s/dt computed with the same derivative_window_s/max_gap_us and compute dh/dt with DERIVATIVE_LLS_V1 inside the same SM_VALIDITY_PIECE_V1. When dE_s/dt>ENERGY_RATE_EPS_W_PER_KG and dh/dt>0, primary Metric value eta_climb_obs=(G0_MPS2*dh/dt)/(dE_s/dt). Values outside [0,1] are not clamped; instead emit OUTSIDE_[0,1] as deterministic Evidence/reason flag. This is observed energy partition, not propulsion efficiency.
- Validity: TAS/altitude derivatives valid; total energy rate positive
- N/A: energy rate non-positive/near-zero or no climb
- Evidence: TAS/altitude derivatives + energy profile
- Golden: Analytic climb+acceleration fixture with known potential/total energy-rate ratio.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-039 DIVE_ENERGY_GAIN_OBSERVED

- Family: `AIRCRAFT_ENERGY`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.dive_energy_gain@1.0.3`
- Semantic: `tpaa.p1.air.dive_energy_gain@1`
- Value kind/unit: `STRUCTURED` / `STRUCTURED`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `NO`
- Inputs: `P1-AIR-016.specific_mechanical_energy`, `P1-AIR-017.specific_energy_rate`, `P1-AIR-015.dive_eligible_intervals`
- Window: dive windows
- Formula/contract: Publish exactly STRUCT_P1_AIR_039_V1. Consume exactly the dive-eligible intervals produced by P1-AIR-015, ordered by start_session_time_us. For each interval publish start_session_time_us/end_session_time_us as decimal-string Session Time values, delta_E_s_j_per_kg from P1-AIR-016 and MEDIAN_V1 of valid P1-AIR-017 dE_s/dt samples; when no interior rate sample exists, median_energy_rate_w_per_kg=null and median_energy_rate_status=INSUFFICIENT_RATE_SAMPLES. interval_count equals the array length. Altitude loss and TAS gain remain Evidence, not extra result fields.
- Validity: energy valid; descent condition met
- N/A: no valid dive interval
- Evidence: energy/TAS/altitude series + dive window
- Golden: Synthetic descent with known energy change and speed gain.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-027 CONTROL_RESPONSE_DELAY_OBSERVED

- Family: `AIRCRAFT_CONTROL_RESPONSE`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.control_response_delay@1.0.4`
- Semantic: `tpaa.p1.air.control_response_delay@1`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `control_axis_command`, `response_axis_value`, `session_time_us`, `mode`, `profile.command_deadband`, `profile.command_persistence_s`, `profile.response_threshold`, `profile.response_persistence_s`, `profile.max_search_s`, `profile.max_gap_us`, `control_calibration_id`, `control_calibration_version`, `control_calibration_hash`, `control_response_map_id`, `control_response_map_version`, `control_response_map_hash`
- Window: isolated eligible command-response events
- Formula/contract: Within SM_VALIDITY_PIECE_V1, command onset is the first sample crossing command_deadband in the commanded sign and remaining beyond it for command_persistence_s. Response onset is the first same-sign response crossing response_threshold and remaining beyond it for response_persistence_s within max_search_s. Any gap > max_gap_us invalidates the candidate event. delay=t_response_onset-t_command_onset. The SM_COMMAND_RESPONSE_EVENT_V1 state machine is fixed; Profile supplies only these numeric thresholds/durations.
- Validity: calibrated control command and corresponding response available; calibration id/version/hash valid for event interval; mode value constant during candidate event; Session-Time alignment valid; control-response map id/version/hash resolves the command axis to one canonical response channel/polarity for the event interval
- N/A: control input absent, mode ambiguous, response not found, or overlapping command prevents attribution
- Evidence: command rows + response rows + onset markers + profile
- Golden: Synthetic step command with known response delay, noise, false early blip and missing-response case.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-035 CONTROL_RESPONSE_GAIN_OBSERVED

- Family: `AIRCRAFT_CONTROL_RESPONSE`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.control_response_gain@1.0.5`
- Semantic: `tpaa.p1.air.control_response_gain@1`
- Value kind/unit: `STRUCTURED` / `STRUCTURED`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `NO`
- Inputs: `control_axis_command`, `response_axis_value`, `session_time_us`, `mode`, `profile.event_window_s`, `profile.min_unique_command_levels`, `profile.command_deadband`, `profile.max_gap_us`, `control_calibration_id`, `control_calibration_version`, `control_calibration_hash`, `control_response_map_id`, `control_response_map_version`, `control_response_map_hash`
- Window: isolated command-response events
- Formula/contract: Publish exactly STRUCT_P1_AIR_035_V1. For each SM_COMMAND_RESPONSE_EVENT_V1 isolated event, restrict samples to event_window_s, exclude command magnitudes <=command_deadband, reject sequences containing a gap >max_gap_us, and for one fixed axis/mode compute THEIL_SEN_GAIN_V1 of delta_response versus delta_command with at least min_unique_command_levels. Group events by (control_axis,mode,response_channel,response_unit,gain_unit); within each group event_gains are ordered by event start Session Time and contain exactly event_id+gain. Axes/modes/channels are never mixed.
- Validity: calibrated command and response available; calibration id/version/hash valid for every event; mode value constant within event; at least min_unique_command_levels distinct eligible command levels after deadband/gap filtering; control-response map id/version/hash resolves the command axis to one canonical response channel/polarity for the event interval
- N/A: control calibration/response unavailable; fewer than min_unique_command_levels distinct eligible command levels; or event attribution ambiguous
- Evidence: command/response rows + event markers + mode/profile
- Golden: Synthetic step/ramp inputs with known linear gain and saturation case.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-036 CONTROL_DEADBAND_OBSERVED

- Family: `AIRCRAFT_CONTROL_RESPONSE`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.control_deadband@1.0.3`
- Semantic: `tpaa.p1.air.control_deadband@1`
- Value kind/unit: `NUMERIC` / `normalized`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `control_axis_command`, `response_axis_value`, `session_time_us`, `profile.response_threshold`, `profile.command_persistence_s`, `profile.min_event_count`, `profile.max_gap_us`, `control_calibration_id`, `control_calibration_version`, `control_calibration_hash`, `control_response_map_id`, `control_response_map_version`, `control_response_map_hash`
- Window: approved excitation/response events
- Formula/contract: Across SM_COMMAND_RESPONSE_EVENT_V1 excitation events, a candidate calibrated command change must persist for command_persistence_s, remain inside one validity piece with no gap > max_gap_us, and its associated response must exceed response_threshold under the P1-AIR-027 response-onset state machine. Require at least min_event_count qualified events; publish the smallest persistent absolute calibrated command change. This is an observed relation, not a hard control-law limit.
- Validity: control calibration valid; mode value constant per event; at least min_event_count qualified excitation/response events satisfy response_threshold and command_persistence_s; control-response map id/version/hash resolves the command axis to one canonical response channel/polarity for the event interval
- N/A: control calibration unavailable; fewer than min_event_count qualified events; mode changes within event; or response threshold cannot be resolved
- Evidence: command/response event set + thresholds/profile
- Golden: Synthetic deadband nonlinearity with known deadband and noise.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-037 RESPONSE_PERSISTENCE_OBSERVED

- Family: `AIRCRAFT_CONTROL_RESPONSE`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.response_persistence@1.0.4`
- Semantic: `tpaa.p1.air.response_persistence@2`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `response_axis_value`, `command_event`, `profile.response_threshold`, `profile.max_gap_us`, `profile.reversal_threshold`, `profile.min_event_count`, `control_response_map_id`, `control_response_map_version`, `control_response_map_hash`
- Window: command-response events
- Formula/contract: For each qualified P1-AIR-027 response onset, measure duration until response falls below signed response_threshold, a disqualifying reversal exceeds reversal_threshold, or max_gap_us is exceeded. Require at least min_event_count qualified events. Primary Metric value=MEDIAN_V1(completed response duration); QUANTILE_HF7_V1 P95 duration and completion_ratio=completed_events/qualified_events are mandatory diagnostic Evidence.
- Validity: response onset valid; sign/mode resolved; control-response map id/version/hash resolves the command axis to one canonical response channel/polarity for the event interval
- N/A: no valid onset or overlapping commands
- Evidence: response samples + onset + persistence intervals
- Golden: Synthetic response with transient blip vs sustained response.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-028 CONTROL_INPUT_RATE_RMS

- Family: `AIRCRAFT_HANDLING`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.control_input_rate_rms@1.0.2`
- Semantic: `tpaa.p1.air.control_input_rate_rms@1`
- Value kind/unit: `NUMERIC` / `normalized/s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `control_input`, `session_time_us`, `profile.derivative_window_s`, `profile.max_gap_us`, `profile.control_deadband`, `control_calibration_id`, `control_calibration_version`, `control_calibration_hash`
- Window: maneuver/control windows
- Formula/contract: After excluding control samples with abs(command)<=control_deadband, compute control-input rate with DERIVATIVE_LLS_V1 using derivative_window_s and never bridging max_gap_us/SM_VALIDITY_PIECE_V1 boundaries. Publish RMS_V1(rate) over the eligible window.
- Validity: calibrated control command valid with calibration id/version/hash covering the evaluated interval
- N/A: control channel unavailable
- Evidence: control rows + filter/profile
- Golden: Sinusoidal control input with analytic derivative RMS.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-029 CONTROL_REVERSAL_COUNT

- Family: `AIRCRAFT_HANDLING`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.control_reversal_count@1.0.2`
- Semantic: `tpaa.p1.air.control_reversal_count@1`
- Value kind/unit: `NUMERIC` / `count`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `control_input`, `session_time_us`, `profile.control_deadband`, `profile.reversal_persistence_s`, `profile.max_gap_us`, `control_calibration_id`, `control_calibration_version`, `control_calibration_hash`
- Window: maneuver/control windows
- Formula/contract: Using the calibrated canonical control command supplied under CONTRACT_CONTROL_INPUT_CALIBRATION_V1, count a reversal when sign changes across ±control_deadband and the new sign persists for reversal_persistence_s without a gap > max_gap_us. One persistent sign change counts once; the Metric Plugin performs no de-bias/re-calibration.
- Validity: calibrated control command valid; calibration id/version/hash covers the evaluated interval; profile parameters resolved
- N/A: control unavailable
- Evidence: control rows + reversal markers
- Golden: Fixture with noise around zero and 3 true reversals; expect 3.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-030 ATTITUDE_OSCILLATION_INDEX

- Family: `AIRCRAFT_HANDLING`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.attitude_oscillation_index@1.0.4`
- Semantic: `tpaa.p1.air.attitude_oscillation_index@1`
- Value kind/unit: `STRUCTURED` / `STRUCTURED`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `NO`
- Inputs: `roll_rad`, `pitch_rad`, `session_time_us`, `profile.low_hz`, `profile.high_hz`, `profile.min_window_s`, `profile.min_coverage`, `profile.max_gap_us`, `profile.resample_rate_hz`, `profile.filter_padding_s`
- Window: maneuver windows
- Formula/contract: Publish exactly STRUCT_P1_AIR_030_V1 with roll and pitch subrecords. For each attitude axis independently, each SM_VALIDITY_PIECE_V1 interval with duration>=min_window_s and valid coverage>=min_coverage is filtered by BANDPASS_BUTTERWORTH4_ZP_V1 using low_hz/high_hz/resample_rate_hz/filter_padding_s; any source gap >max_gap_us splits the piece. If an axis has at least one eligible filtered piece, publish status=VALID and RMS_V1 over all eligible filtered samples for that axis; otherwise publish status=INSUFFICIENT_DATA and rms_rad=null. Overall Metric is N_A only when both axes are insufficient.
- Validity: at least one of roll/pitch has an eligible interval with duration>=min_window_s, coverage>=min_coverage, 0<low_hz<high_hz<resample_rate_hz/2 and deterministic filter grid/padding requirements satisfied
- N/A: both roll and pitch lack any eligible deterministic filter interval
- Evidence: attitude rows + filter profile + spectral/energy evidence
- Golden: Synthetic sine oscillation plus drift; verify band component and drift rejection.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-031 JERK_RMS

- Family: `AIRCRAFT_HANDLING`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.jerk_rms@2.0.0`
- Semantic: `tpaa.p1.air.jerk_rms@2`
- Value kind/unit: `NUMERIC` / `m/s^3`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `accel_body_mps2_xyz`, `session_time_us`, `profile.derivative_window_s`, `profile.max_gap_us`
- Window: maneuver windows
- Formula/contract: Inside each SM_VALIDITY_PIECE_V1, apply DERIVATIVE_LLS_V1 independently to calibrated body-frame ax, ay, az using derivative_window_s/max_gap_us. For timestamps where all three derivative components are finite, compute jerk_norm_mps3=sqrt(jx^2+jy^2+jz^2) and publish RMS_V1(jerk_norm_mps3). No nz or single-axis fallback is permitted.
- Validity: all three calibrated body acceleration components are finite in at least one eligible derivative window and DERIVATIVE_LLS_V1 returns a simultaneous finite jx/jy/jz sample under derivative_window_s/max_gap_us
- N/A: three-axis calibrated body acceleration unavailable/invalid or no simultaneous finite 3D jerk sample
- Evidence: acceleration rows + derivative/filter profile
- Golden: Three-axis linear/quadratic body-acceleration fixture with analytically known jerk vector magnitude; verify semantic v2 and forbid nz/single-axis fallback.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-032 FUEL_FLOW_OBSERVED

- Family: `AIRCRAFT_PERSISTENCE`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.fuel_flow@1.0.1`
- Semantic: `tpaa.p1.air.fuel_flow@2`
- Value kind/unit: `NUMERIC` / `kg/s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `fuel_flow_kg_s`, `session_time_us`
- Window: eligible flight windows
- Formula/contract: Primary Metric value=MEDIAN_V1 of eligible fuel-flow samples within the declared engine/mode/context cohort. QUANTILE_HF7_V1 P95 fuel flow is mandatory diagnostic Evidence. Never mix engine/mode/context cohorts inside one MetricInstance.
- Validity: fuel-flow channel valid
- N/A: fuel-flow unavailable
- Evidence: fuel-flow rows + context
- Golden: Known constant/step flow fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-033 FUEL_BURN_RATE_OBSERVED

- Family: `AIRCRAFT_PERSISTENCE`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.fuel_burn_rate@1.0.1`
- Semantic: `tpaa.p1.air.fuel_burn_rate@1`
- Value kind/unit: `NUMERIC` / `kg/s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `fuel_remaining_kg`, `session_time_us`, `profile.derivative_window_s`, `profile.max_gap_us`, `profile.refuel_jump_threshold_kg`, `profile.event_guard_s`
- Window: stable non-refuel windows
- Formula/contract: Split fuel_remaining_kg into derivative pieces with SM_FUEL_QUANTITY_EVENT_V1; when no explicit marker exists, a positive jump >=refuel_jump_threshold_kg starts a reset/refuel event. Exclude event_guard_s around reset/refuel boundaries. Within each remaining SM_VALIDITY_PIECE_V1 piece compute burn_rate=-d(fuel_remaining_kg)/dt with DERIVATIVE_LLS_V1 using derivative_window_s/max_gap_us; only finite burn_rate>=0 is eligible. fuel_flow_kg_s, when available, is diagnostic cross-check evidence only.
- Validity: fuel remaining valid and monotonic except identified events
- N/A: fuel quantity unavailable or refuel/reset unresolved
- Evidence: fuel quantity + event markers + optional fuel-flow
- Golden: Linear fuel decline plus refuel jump; exclude refuel segment.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-AIR-034 ENDURANCE_PROXY_OBSERVED

- Family: `AIRCRAFT_PERSISTENCE`
- Subject: `AIRCRAFT`
- Algorithm: `alg.tpaa.p1.air.endurance_proxy@1.0.2`
- Semantic: `tpaa.p1.air.endurance_proxy@1`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `fuel_remaining_kg`, `P1-AIR-033.fuel_burn_rate_kg_s`, `session_time_us`, `profile.burn_rate_window_s`, `profile.min_coverage`, `profile.max_gap_us`
- Window: stable consumption windows
- Formula/contract: Compute smoothed_burn_rate_kg_s as ROLLING_MEDIAN_V1 of positive valid P1-AIR-033 burn-rate samples over burn_rate_window_s with min_coverage/max_gap_us. If smoothed_burn_rate_kg_s<=FUEL_BURN_RATE_EPS_KG_S return N_A/INSUFFICIENT_DATA; otherwise endurance_proxy_s=fuel_remaining_kg/smoothed_burn_rate_kg_s. This is an observational endurance proxy, not a mission/range prediction.
- Validity: fuel_remaining finite and ROLLING_MEDIAN_V1 returns burn rate >FUEL_BURN_RATE_EPS_KG_S under burn_rate_window_s/min_coverage/max_gap_us
- N/A: fuel unavailable; rolling burn-rate window ineligible; or smoothed burn rate <=FUEL_BURN_RATE_EPS_KG_S
- Evidence: fuel state + burn-rate evidence
- Golden: Known fuel/flow pair; verify quotient and N/A at zero flow.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-001 DETECTION_OPPORTUNITY_COVERAGE

- Family: `SENSOR_DETECTION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.detection_opportunity_coverage@1.0.2`
- Semantic: `tpaa.p1.sensor.detection_opportunity_coverage@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `reference_target_presence`, `sensor_operating_mode`, `sensor_data_availability`, `reference_relative_state`, `detection_opportunity_id`, `opportunity_profile_id`, `opportunity_profile_version`, `opportunity_profile_hash`
- Window: reference-target-present intervals
- Formula/contract: coverage=total duration of canonical CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1 intervals / total authoritative reference-target-present duration for the same evaluated system/reference entity. Opportunity construction is performed upstream by WRE using the frozen opportunity profile; this Metric never rebuilds mode/geometry/reference-quality eligibility and never uses observed detection outcome.
- Validity: canonical opportunity intervals and authoritative reference-target-present intervals resolved for the same evaluated system/reference entity; opportunity profile id/version/hash present
- N/A: opportunity contract/profile unavailable or no authoritative reference-target-present duration
- Evidence: canonical opportunity interval ids, opportunity profile id/version/hash, reference-target-present intervals, eligibility provenance
- Golden: Synthetic target-present interval with planned sensor-off segment; verify denominator/eligible coverage.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-002 DETECTION_RATE_OBSERVED

- Family: `SENSOR_DETECTION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.detection_rate@1.0.3`
- Semantic: `tpaa.p1.sensor.detection_rate@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `evaluation_opportunity_intervals`, `detection_opportunity_id`, `opportunity_profile_id`, `opportunity_profile_version`, `opportunity_profile_hash`, `detection_confirmation_event_id`, `confirmation_profile_id`, `confirmation_profile_version`, `confirmation_profile_hash`
- Window: valid detection-opportunity windows
- Formula/contract: detection_rate = count of canonical opportunity intervals having at least one CONTRACT_DETECTION_CONFIRMATION_EVENT_V1 for the same opportunity_id/reference association / count of canonical CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1 intervals. Confirmation persistence and opportunity eligibility are upstream contract semantics; this Metric does not rerun either state machine.
- Validity: canonical opportunity intervals and confirmation events resolved with matching opportunity_id/reference association and profile provenance
- N/A: opportunity contract/profile unavailable or no valid opportunities; confirmation contract unresolved when a detection event is claimed
- Evidence: opportunity interval ids, confirmation event ids, opportunity/confirmation profile id/version/hash, association provenance
- Golden: Known 10 opportunities with 8 detections, including one invalid opportunity excluded.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-003 TIME_TO_FIRST_DETECTION

- Family: `SENSOR_DETECTION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.time_to_first_detection@1.0.3`
- Semantic: `tpaa.p1.sensor.time_to_first_detection@1`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `opportunity_start_time_us`, `first_confirmed_detection_time_us`, `detection_confirmation_event_id`, `confirmation_profile_id`, `confirmation_profile_version`, `confirmation_profile_hash`, `detection_opportunity_id`, `opportunity_profile_id`, `opportunity_profile_version`, `opportunity_profile_hash`
- Window: each detection-opportunity episode
- Formula/contract: time_to_first_detection_s=(first_confirmed_detection_time_us-opportunity_start_time_us)/1e6 using a CONTRACT_DETECTION_CONFIRMATION_EVENT_V1 event inside the same CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1 interval and authoritative reference association
- Validity: canonical opportunity interval and confirmed-detection event resolved for the same authoritative reference association; Session-Time aligned
- N/A: opportunity/confirmation contract unavailable or no confirmed detection inside a valid opportunity
- Evidence: opportunity event + first detection row + association
- Golden: Fixture with opportunity at t0 and detection at t0+3.2s; missing detection => N/A/status.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-004 FIRST_DETECTION_RANGE_OBSERVED

- Family: `SENSOR_DETECTION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.first_detection_range@1.0.4`
- Semantic: `tpaa.p1.sensor.first_detection_range@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `first_confirmed_detection_time_us`, `reference_range_m`, `detection_confirmation_event_id`, `confirmation_profile_id`, `confirmation_profile_version`, `confirmation_profile_hash`
- Window: first-detection event
- Formula/contract: Interpolate authoritative reference range with LINEAR_INTERPOLATION_V1 at first_confirmed_detection_time_us from CONTRACT_DETECTION_CONFIRMATION_EVENT_V1 for the same reference association; never rediscover or re-confirm detection inside this Metric.
- Validity: canonical confirmation event, authoritative reference association and reference relative state are resolved; interpolation gap valid
- N/A: confirmation event unavailable or no valid reference range match at the event time
- Evidence: confirmation event id, confirmation profile id/version/hash, reference association, reference rows used for interpolation
- Golden: Linear range closure fixture; verify interpolated range.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-005 RANGE_ERROR_BIAS

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.range_error_bias@1.0.3`
- Semantic: `tpaa.p1.sensor.range_error_bias@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `measured_range_m`, `reference_range_m`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: MEAN_V1 of (measured_range-reference_range) over eligible matched samples.
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=RANGE; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measured_range_m, reference_range_m, match relation, P1-QA-002/005/006, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Constant +50 m bias fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-006 RANGE_ERROR_RMSE

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.range_error_rmse@1.0.2`
- Semantic: `tpaa.p1.sensor.range_error_rmse@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `measured_range_m`, `reference_range_m`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: sqrt(mean((measured_range-reference_range)^2))
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=RANGE; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measured_range_m, reference_range_m, match relation, P1-QA-002/005/006, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Known residual vector [3,4] m -> RMSE sqrt(12.5).

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-007 RANGE_ERROR_P95

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.range_error_p95@1.0.2`
- Semantic: `tpaa.p1.sensor.range_error_p95@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `measured_range_m`, `reference_range_m`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: quantile(abs(measured_range-reference_range),0.95)
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=RANGE; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measured_range_m, reference_range_m, match relation, P1-QA-002/005/006, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Deterministic residual set with hand-computable nearest-rank/interpolation profile.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-008 AZIMUTH_ERROR_BIAS

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.azimuth_error_bias@1.0.2`
- Semantic: `tpaa.p1.sensor.azimuth_error_bias@1`
- Value kind/unit: `NUMERIC` / `rad`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `measured_az_rad`, `reference_az_rad`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: circular_mean(wrap_pi(measured_az-reference_az))
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=AZIMUTH; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measured_az_rad, reference_az_rad, match relation, P1-QA-002/005/006, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: 179°/-179° wrap fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-009 AZIMUTH_ERROR_RMSE

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.azimuth_error_rmse@1.0.2`
- Semantic: `tpaa.p1.sensor.azimuth_error_rmse@1`
- Value kind/unit: `NUMERIC` / `rad`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `measured_az_rad`, `reference_az_rad`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: sqrt(mean(wrap_pi(measured_az-reference_az)^2))
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=AZIMUTH; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measured_az_rad, reference_az_rad, match relation, P1-QA-002/005/006, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Known wrapped angular residuals.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-010 ELEVATION_ERROR_RMSE

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.elevation_error_rmse@1.0.2`
- Semantic: `tpaa.p1.sensor.elevation_error_rmse@1`
- Value kind/unit: `NUMERIC` / `rad`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `measured_el_rad`, `reference_el_rad`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: sqrt(mean((measured_el-reference_el)^2))
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=ELEVATION; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measured_el_rad, reference_el_rad, match relation, P1-QA-002/005/006, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Known elevation residuals.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-011 POSITION_3D_ERROR_RMSE

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.position_3d_error_rmse@1.0.2`
- Semantic: `tpaa.p1.sensor.position_3d_error_rmse@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `measured_position_ecef_m`, `reference_target_position_ecef_m`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: sqrt(mean(||p_meas-p_ref||^2))
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=POSITION_3D; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measured_position_ecef_m, reference_target_position_ecef_m, match relation, P1-QA-002/005/006, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Orthogonal 3D residual fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-012 RADIAL_VELOCITY_ERROR_RMSE

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.radial_velocity_error_rmse@1.0.2`
- Semantic: `tpaa.p1.sensor.radial_velocity_error_rmse@1`
- Value kind/unit: `NUMERIC` / `m/s`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `measured_radial_velocity_mps`, `reference_range_rate_mps`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: sqrt(mean((vr_meas-vr_ref)^2))
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=RADIAL_VELOCITY; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measured_radial_velocity_mps, reference_range_rate_mps, match relation, P1-QA-002/005/006, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Known closing-rate residuals.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-013 CROSS_RANGE_ERROR_RMSE

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.cross_range_error_rmse@1.0.2`
- Semantic: `tpaa.p1.sensor.cross_range_error_rmse@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `measured_position_sensor_frame`, `reference_position_sensor_frame`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: sqrt(mean(e_cross^2)) after decomposing position error perpendicular to reference LOS
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=CROSS_RANGE; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measured_position_sensor_frame, reference_position_sensor_frame, match relation, P1-QA-002/005/006, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Known radial/cross-range decomposition fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-014 VERTICAL_ERROR_RMSE

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.vertical_error_rmse@1.0.2`
- Semantic: `tpaa.p1.sensor.vertical_error_rmse@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `measured_position_local`, `reference_position_local`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: sqrt(mean((z_meas-z_ref)^2)) in frozen local frame
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=VERTICAL_POSITION; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measured_position_local, reference_position_local, match relation, P1-QA-002/005/006, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Known vertical residual fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-015 RANGE_ERROR_MAE

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.range_error_mae@1.0.3`
- Semantic: `tpaa.p1.sensor.range_error_mae@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `sensor_measurement`, `reference_relative_state`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: MEAN_V1 of abs(measured_range-reference_range) over eligible matched samples.
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=RANGE; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measurement row, reference state, match relation, uncertainty decomposition, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Known signed residual vector; compare MAE.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-016 RANGE_ERROR_P50

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.range_error_p50@1.0.2`
- Semantic: `tpaa.p1.sensor.range_error_p50@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `sensor_measurement`, `reference_relative_state`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: quantile(abs(measured_range-reference_range),0.50)
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=RANGE; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measurement row, reference state, match relation, uncertainty decomposition, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Deterministic residual set; verify median absolute error.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-017 RANGE_ERROR_MAX_ABS

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.range_error_max_abs@1.0.2`
- Semantic: `tpaa.p1.sensor.range_error_max_abs@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `sensor_measurement`, `reference_relative_state`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: max(abs(measured_range-reference_range))
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=RANGE; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measurement row, reference state, match relation, uncertainty decomposition, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Known residual set with one valid maximum and one invalid outlier.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-018 AZIMUTH_ERROR_P95

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.azimuth_error_p95@1.0.2`
- Semantic: `tpaa.p1.sensor.azimuth_error_p95@1`
- Value kind/unit: `NUMERIC` / `rad`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `sensor_measurement`, `reference_relative_state`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: quantile(abs(wrap_pi(measured_az-reference_az)),0.95)
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=AZIMUTH; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measurement row, reference state, match relation, uncertainty decomposition, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Wrapped-angle residual set; verify P95.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-019 ELEVATION_ERROR_BIAS

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.elevation_error_bias@1.0.3`
- Semantic: `tpaa.p1.sensor.elevation_error_bias@1`
- Value kind/unit: `NUMERIC` / `rad`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `sensor_measurement`, `reference_relative_state`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: MEAN_V1 of (measured_el-reference_el) over eligible matched samples.
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=ELEVATION; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measurement row, reference state, match relation, uncertainty decomposition, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Known constant elevation bias.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-020 ELEVATION_ERROR_P95

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.elevation_error_p95@1.0.2`
- Semantic: `tpaa.p1.sensor.elevation_error_p95@1`
- Value kind/unit: `NUMERIC` / `rad`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `sensor_measurement`, `reference_relative_state`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: quantile(abs(measured_el-reference_el),0.95)
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=ELEVATION; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measurement row, reference state, match relation, uncertainty decomposition, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Known elevation residual set.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-SNS-021 RADIAL_POSITION_ERROR_RMSE

- Family: `SENSOR_ACCURACY`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.sensor.radial_position_error_rmse@1.0.2`
- Semantic: `tpaa.p1.sensor.radial_position_error_rmse@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M2` / `P1_FOUNDATION_32`; P1 longitudinal: `YES`
- Inputs: `sensor_measurement`, `reference_relative_state`, `measurement_time_us`, `reference_truth_uncertainty`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: matched measurement/reference samples
- Formula/contract: sqrt(mean(e_radial^2)) where e_radial=(p_meas-p_ref)·u_ref_los
- Validity: authoritative association valid; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=RADIAL_POSITION; units/frame known
- N/A: no valid matched samples; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile with deterministic N/A reason
- Evidence: measurement row, reference state, match relation, uncertainty decomposition, reference match quality profile id/version/hash + per-sample eligibility/rejection reason
- Golden: Known 3D error decomposed into radial/cross/vertical components.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-TRK-001 TRACK_INITIATION_TIME

- Family: `TRACK_PERFORMANCE`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.track.initiation_time@1.0.5`
- Semantic: `tpaa.p1.track.initiation_time@1`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `first_confirmed_detection_time_us`, `stable_track_start_time_us`, `detection_confirmation_event_id`, `confirmation_profile_id`, `confirmation_profile_version`, `confirmation_profile_hash`, `profile.stable_track_persistence_s`, `profile.max_gap_us`
- Window: associated track-initiation windows
- Formula/contract: Track initiation time = (stable_track_start_time_us-first_confirmed_detection_time_us)/1e6, where first_confirmed_detection_time_us comes from CONTRACT_DETECTION_CONFIRMATION_EVENT_V1 and stable_track_start_time_us is produced by SM_TRACK_STABLE_V1 using stable_track_persistence_s/max_gap_us for the same authoritative reference association.
- Validity: canonical confirmation event, track validity and authoritative association resolved; timestamps aligned; stable-track onset satisfies declared persistence/gap rule
- N/A: confirmation event/association/track validity unavailable or no stable-track onset satisfying the declared persistence/gap rule
- Evidence: confirmation event/profile provenance, track states, association relation, stable-track state evidence
- Golden: Known 1.5 s initiation; unstable provisional track excluded.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-TRK-002 TRACK_POSITION_ERROR_RMSE

- Family: `TRACK_PERFORMANCE`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.track.position_error_rmse@1.0.3`
- Semantic: `tpaa.p1.track.position_error_rmse@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `track_position_ecef_m`, `reference_target_position_ecef_m`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: valid associated track/reference-matched windows
- Formula/contract: sqrt(mean(||p_track-p_ref||^2))
- Validity: canonical valid track states are authoritatively associated; matched reference position and Session-Time alignment available; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=POSITION_3D
- N/A: no valid associated track/reference position samples; reference-match quality profile absent/unresolved or all matched samples rejected by the profile
- Evidence: track states, association relation, reference position states, time/match provenance
- Golden: Known track residual fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-TRK-003 TRACK_VELOCITY_ERROR_RMSE

- Family: `TRACK_PERFORMANCE`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.track.velocity_error_rmse@1.0.3`
- Semantic: `tpaa.p1.track.velocity_error_rmse@1`
- Value kind/unit: `NUMERIC` / `m/s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `track_velocity_ecef_mps`, `reference_target_velocity_ecef_mps`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: valid associated track/reference-matched windows
- Formula/contract: sqrt(mean(||v_track-v_ref||^2))
- Validity: canonical valid track states are authoritatively associated; matched reference velocity and Session-Time alignment available; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=VELOCITY_3D
- N/A: no valid associated track/reference velocity samples; reference-match quality profile absent/unresolved or all matched samples rejected by the profile
- Evidence: track states, association relation, reference velocity states, time/match provenance
- Golden: Known velocity residual fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-TRK-004 TRACK_CONTINUITY

- Family: `TRACK_PERFORMANCE`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.track.continuity@1.0.3`
- Semantic: `tpaa.p1.track.continuity@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `valid_track_intervals`, `evaluation_opportunity_intervals`, `detection_opportunity_id`, `opportunity_profile_id`, `opportunity_profile_version`, `opportunity_profile_hash`
- Window: valid track/reference evaluation windows
- Formula/contract: duration(canonical valid track ∩ canonical opportunity)/duration(canonical opportunity) using CONTRACT_TRACK_VALIDITY_V1 and CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1 for the same authoritative association
- Validity: canonical opportunity interval, track validity and authoritative association resolved with matching evaluated system/reference entity and opportunity profile provenance
- N/A: opportunity contract/profile unavailable or no valid opportunities; track validity/association unresolved
- Evidence: opportunity interval/profile provenance, track validity states, association relation
- Golden: Known intervals with gap; exact ratio.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-TRK-005 TRACK_DROP_COUNT

- Family: `TRACK_PERFORMANCE`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.track.drop_count@1.0.4`
- Semantic: `tpaa.p1.track.drop_count@1`
- Value kind/unit: `NUMERIC` / `count`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `valid_track_intervals`, `detection_opportunity_id`, `opportunity_profile_id`, `opportunity_profile_version`, `opportunity_profile_hash`, `profile.drop_min_duration_s`
- Window: valid track/reference evaluation windows
- Formula/contract: Within canonical CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1 intervals, count one drop when authoritative track validity transitions VALID→INVALID for the same association and invalid dwell lasts at least drop_min_duration_s. A continuous invalid dwell counts once.
- Validity: canonical opportunity interval, track validity and authoritative association resolved; drop_min_duration_s resolved
- N/A: opportunity contract/profile unavailable or no valid opportunities; track validity/association unresolved
- Evidence: opportunity interval/profile provenance, track validity transition evidence, association relation, drop duration profile
- Golden: Interval fixture with short glitch and two true drops.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-TRK-006 TRACK_REACQUISITION_TIME

- Family: `TRACK_PERFORMANCE`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.track.reacquisition_time@1.0.4`
- Semantic: `tpaa.p1.track.reacquisition_time@2`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `track_drop_start_time_us`, `reacquired_stable_track_time_us`, `detection_opportunity_id`, `opportunity_profile_id`, `opportunity_profile_version`, `opportunity_profile_hash`, `profile.drop_min_duration_s`, `profile.reacquisition_persistence_s`
- Window: valid track/reference evaluation windows
- Formula/contract: Within canonical CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1 intervals and using SM_TRACK_DROP_REACQUIRE_V1, a drop qualifies only when invalid dwell>=drop_min_duration_s. reacquisition_delay=reacquired_stable_track_time_us-track_drop_start_time_us, where same-association validity persists for reacquisition_persistence_s. Primary Metric value=MEDIAN_V1(qualified reacquisition_delay); QUANTILE_HF7_V1 P95 is mandatory diagnostic Evidence.
- Validity: canonical opportunity interval, track validity and authoritative association resolved; drop/reacquisition parameters resolved
- N/A: opportunity contract/profile unavailable or no valid opportunities/qualified drops; track validity/association unresolved
- Evidence: opportunity interval/profile provenance, drop/reacquisition state evidence, association relation, drop/reacquisition profile
- Golden: Fixture with known two reacquisition delays.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-TRK-007 TRACK_AGE

- Family: `TRACK_PERFORMANCE`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.track.age@1.0.3`
- Semantic: `tpaa.p1.track.age@2`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `track_state_time_us`, `last_measurement_effective_time_us`
- Window: valid associated track-state windows
- Formula/contract: track_age_s=(track_state_time_us-last_measurement_effective_time_us)/1e6. Primary Metric value=MEDIAN_V1(track_age_s) over eligible canonical valid-track samples; QUANTILE_HF7_V1 P95 and max(track_age_s) are mandatory diagnostic Evidence.
- Validity: canonical valid associated track state and last contributing measurement effective time are available on the same Session-Time basis
- N/A: no valid associated track state or last contributing measurement effective time unavailable
- Evidence: track states, association relation, track validity intervals, last contributing measurement effective time provenance
- Golden: Known propagated track ages.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ID-001 ASSOCIATION_ACCURACY

- Family: `ASSOCIATION_IDENTIFICATION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.id.association_accuracy@1.0.1`
- Semantic: `tpaa.p1.id.association_accuracy@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `track_to_truth_association`, `reference_identity`
- Window: associated target/track windows
- Formula/contract: correct_association_duration / associated_duration
- Validity: authoritative association relation resolved for the eligible interval; required persistence/gap parameters resolved when declared
- N/A: authoritative association relation unavailable/unresolved or no eligible associated dwell
- Evidence: track/ID states, authoritative association intervals, reference_target_id provenance
- Golden: Known mapping intervals with one wrong segment.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ID-002 WRONG_ASSOCIATION_COUNT

- Family: `ASSOCIATION_IDENTIFICATION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.id.wrong_association_count@1.0.1`
- Semantic: `tpaa.p1.id.wrong_association_count@1`
- Value kind/unit: `NUMERIC` / `count`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `track_to_truth_association`, `reference_identity`
- Window: associated target/track windows
- Formula/contract: count distinct qualified wrong-association episodes
- Validity: authoritative association relation resolved for the eligible interval; required persistence/gap parameters resolved when declared
- N/A: authoritative association relation unavailable/unresolved or no eligible associated dwell
- Evidence: track/ID states, authoritative association intervals, reference_target_id provenance
- Golden: Known 2 wrong episodes separated by correct interval.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ID-003 TRACK_SWAP_COUNT

- Family: `ASSOCIATION_IDENTIFICATION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.id.track_swap_count@1.0.1`
- Semantic: `tpaa.p1.id.track_swap_count@1`
- Value kind/unit: `NUMERIC` / `count`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `track_id`, `reference_target_id`, `session_time_us`, `profile.swap_persistence_s`
- Window: associated target/track windows
- Formula/contract: Count a track-swap event when two live track IDs exchange their associated reference_target_id assignments and the exchanged assignment persists for at least swap_persistence_s. One continuous exchanged interval counts once.
- Validity: authoritative association relation resolved for the eligible interval; required persistence/gap parameters resolved when declared
- N/A: authoritative association relation unavailable/unresolved or no eligible associated dwell
- Evidence: track/ID states, authoritative association intervals, reference_target_id provenance
- Golden: Two-target synthetic swap event.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ID-004 TRACK_SPLIT_COUNT

- Family: `ASSOCIATION_IDENTIFICATION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.id.track_split_count@1.0.1`
- Semantic: `tpaa.p1.id.track_split_count@1`
- Value kind/unit: `NUMERIC` / `count`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `track_id`, `reference_target_id`, `profile.split_persistence_s`
- Window: associated target/track windows
- Formula/contract: Count one split event when a single reference_target_id is simultaneously represented by more than one distinct track_id continuously for at least split_persistence_s; one continuous multi-track episode counts once.
- Validity: authoritative association relation resolved for the eligible interval; required persistence/gap parameters resolved when declared
- N/A: authoritative association relation unavailable/unresolved or no eligible associated dwell
- Evidence: track/ID states, authoritative association intervals, reference_target_id provenance
- Golden: Single truth target duplicated into two tracks.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ID-005 TRACK_MERGE_COUNT

- Family: `ASSOCIATION_IDENTIFICATION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.id.track_merge_count@1.0.1`
- Semantic: `tpaa.p1.id.track_merge_count@1`
- Value kind/unit: `NUMERIC` / `count`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `track_id`, `reference_target_id`, `profile.merge_persistence_s`
- Window: associated target/track windows
- Formula/contract: Count a merge event when two or more distinct reference targets are simultaneously represented by one track ID continuously for at least merge_persistence_s. One continuous merged interval counts once.
- Validity: authoritative association relation resolved for the eligible interval; required persistence/gap parameters resolved when declared
- N/A: authoritative association relation unavailable/unresolved or no eligible associated dwell
- Evidence: track/ID states, authoritative association intervals, reference_target_id provenance
- Golden: Two truth targets merged into one track.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ID-006 DUPLICATE_TRACK_RATIO

- Family: `ASSOCIATION_IDENTIFICATION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.id.duplicate_track_ratio@1.0.2`
- Semantic: `tpaa.p1.id.duplicate_track_ratio@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `active_tracks`, `reference_target_id`, `profile.duplicate_persistence_s`
- Window: associated target/track windows
- Formula/contract: Under SM_ASSOCIATION_EPISODE_V1, a duplicate episode exists when more than one distinct track_id represents the same reference_target_id continuously for at least duplicate_persistence_s. duplicate_track_ratio=total duplicate-episode dwell/eligible associated target-present dwell.
- Validity: authoritative association relation resolved for the eligible interval; required persistence/gap parameters resolved when declared
- N/A: authoritative association relation unavailable/unresolved or no eligible associated dwell
- Evidence: track/ID states, authoritative association intervals, reference_target_id provenance
- Golden: Known duplicate dwell interval.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ID-007 TRACK_IDENTITY_CONTINUITY

- Family: `ASSOCIATION_IDENTIFICATION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.id.track_identity_continuity@1.0.2`
- Semantic: `tpaa.p1.id.track_identity_continuity@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `reference_target_id`, `track_id_sequence`, `profile.identity_persistence_s`, `profile.max_gap_us`
- Window: associated target/track windows
- Formula/contract: Within eligible associated target-present time governed by SM_ASSOCIATION_EPISODE_V1, an identity segment is continuous only while the same track_id represents the same reference_target_id with no gap > max_gap_us. Segments shorter than identity_persistence_s are not eligible. identity_continuity=longest eligible continuous identity dwell/eligible associated target-present duration.
- Validity: authoritative association relation resolved for the eligible interval; required persistence/gap parameters resolved when declared
- N/A: authoritative association relation unavailable/unresolved or no eligible associated dwell
- Evidence: track/ID states, authoritative association intervals, reference_target_id provenance
- Golden: Target represented by same ID except one persistent switch.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ID-008 IDENTIFICATION_ACCURACY

- Family: `ASSOCIATION_IDENTIFICATION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.id.identification_accuracy@1.0.2`
- Semantic: `tpaa.p1.id.identification_accuracy@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `reported_classification`, `reference_classification`, `reference_classification_taxonomy_id`, `reference_classification_taxonomy_version`, `reference_classification_taxonomy_hash`
- Window: associated target/track windows
- Formula/contract: Normalize reported_classification and reference_classification with REFERENCE_CLASSIFICATION_TAXONOMY_CONTRACT_V1. Over authoritative association intervals where canonical reference label!=UNKNOWN and canonical reported label!=UNKNOWN, primary Metric value identification_accuracy=correct canonical-label dwell/classified eligible dwell. The canonical taxonomy confusion matrix is mandatory Evidence, not an additional Metric value.
- Validity: authoritative association resolved; authoritative reference classification interval available; taxonomy_id/version/hash resolved; reported label normalizable through the same taxonomy
- N/A: reference classification/taxonomy unavailable or unresolved; association unresolved; reference label quality invalid
- Evidence: track/ID states, reference identity labels, association intervals, reference classification authority event, taxonomy id/version/hash + alias normalization result
- Golden: Multi-class confusion fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ID-009 FALSE_IDENTIFICATION_RATE

- Family: `ASSOCIATION_IDENTIFICATION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.id.false_identification_rate@1.0.1`
- Semantic: `tpaa.p1.id.false_identification_rate@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `reported_classification`, `reference_classification`, `reference_classification_taxonomy_id`, `reference_classification_taxonomy_version`, `reference_classification_taxonomy_hash`
- Window: associated target/track windows
- Formula/contract: Normalize both labels with REFERENCE_CLASSIFICATION_TAXONOMY_CONTRACT_V1. Over authoritative association intervals where canonical reference label != UNKNOWN and canonical reported label != UNKNOWN: false_identification_rate = incorrect canonical-label dwell / classified eligible dwell. UNKNOWN reports are excluded from this denominator and are measured by the separate UNKNOWN_DWELL_RATIO metric.
- Validity: authoritative association resolved; authoritative reference classification interval available; taxonomy_id/version/hash resolved; reported label normalizable through the same taxonomy
- N/A: reference classification/taxonomy unavailable or unresolved; association unresolved; reference label quality invalid
- Evidence: track/ID states, reference identity labels, association intervals, reference classification authority event, taxonomy id/version/hash + alias normalization result
- Golden: Known false-class dwell.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ID-010 UNKNOWN_DWELL_RATIO

- Family: `ASSOCIATION_IDENTIFICATION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.id.unknown_dwell_ratio@1.0.1`
- Semantic: `tpaa.p1.id.unknown_dwell_ratio@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `reported_classification`
- Window: associated target/track windows
- Formula/contract: UNKNOWN dwell / eligible track dwell
- Validity: authoritative association relation resolved for the eligible interval; required persistence/gap parameters resolved when declared
- N/A: authoritative association relation unavailable/unresolved or no eligible associated dwell
- Evidence: track/ID states, authoritative association intervals, reference_target_id provenance
- Golden: Known UNKNOWN segments.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ID-011 IDENTIFICATION_LATENCY

- Family: `ASSOCIATION_IDENTIFICATION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.id.identification_latency@1.0.3`
- Semantic: `tpaa.p1.id.identification_latency@1`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `stable_track_start_time_us`, `first_stable_non_unknown_correct_id_time_us`, `reference_classification_taxonomy_id`, `reference_classification_taxonomy_version`, `reference_classification_taxonomy_hash`, `profile.stable_track_persistence_s`, `profile.id_stability_persistence_s`, `profile.max_gap_us`
- Window: associated target/track windows
- Formula/contract: Normalize reported/reference labels with REFERENCE_CLASSIFICATION_TAXONOMY_CONTRACT_V1. identification_latency_s=(first SM_IDENTIFICATION_STABLE_V1 correct non-UNKNOWN canonical identification time-stable_track_start_time_us)/1e6 for the same authoritative association. SM_TRACK_STABLE_V1 uses stable_track_persistence_s/max_gap_us; SM_IDENTIFICATION_STABLE_V1 uses id_stability_persistence_s/max_gap_us.
- Validity: authoritative association and reference classification/taxonomy resolved; stable_track_start_time_us produced by SM_TRACK_STABLE_V1 under stable_track_persistence_s/max_gap_us; reported label normalizable through the same taxonomy
- N/A: reference classification/taxonomy unavailable or unresolved; association unresolved; reference label quality invalid
- Evidence: track/ID states, reference identity labels, association intervals, reference classification authority event, taxonomy id/version/hash + alias normalization result
- Golden: Known classification transition timeline.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ID-012 IDENTIFICATION_STABILITY

- Family: `ASSOCIATION_IDENTIFICATION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.id.identification_stability@1.0.3`
- Semantic: `tpaa.p1.id.identification_stability@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `reported_classification`, `session_time_us`, `reference_classification_taxonomy_id`, `reference_classification_taxonomy_version`, `reference_classification_taxonomy_hash`, `profile.id_stability_persistence_s`, `profile.max_gap_us`
- Window: associated target/track windows
- Formula/contract: Normalize labels with REFERENCE_CLASSIFICATION_TAXONOMY_CONTRACT_V1. After the first SM_IDENTIFICATION_STABLE_V1 correct non-UNKNOWN canonical identification, primary Metric value identification_stability=stable_correct_canonical_classified_dwell/post_identification_eligible_dwell for the same authoritative association. Canonical-label transition_count is mandatory Evidence. SM_IDENTIFICATION_STABLE_V1 uses id_stability_persistence_s/max_gap_us from the declared Evaluation Profile.
- Validity: authoritative association resolved; authoritative reference classification interval available; taxonomy_id/version/hash resolved; reported label normalizable through the same taxonomy
- N/A: reference classification/taxonomy unavailable or unresolved; association unresolved; reference label quality invalid
- Evidence: track/ID states, reference identity labels, association intervals, reference classification authority event, taxonomy id/version/hash + alias normalization result
- Golden: Correct→wrong→correct classification timeline.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-PSV-001 PASSIVE_LOS_ANGULAR_ERROR_RMSE

- Family: `PASSIVE_SENSOR`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.passive.los_angular_error_rmse@1.0.3`
- Semantic: `tpaa.p1.passive.los_angular_error_rmse@1`
- Value kind/unit: `NUMERIC` / `rad`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `measured_los_unit`, `reference_los_unit`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`, `system_type`
- Window: IRST/EO/passive-sensor evaluation windows
- Formula/contract: sqrt(mean(acos(clamp(u_meas·u_ref,-1,1))^2))
- Validity: system_type in {'IRST','EO'}; reference state/association/timing valid; matched sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=LOS_ANGLE
- N/A: system_type not in {'IRST','EO'}; passive measurement/reference unavailable; reference-match quality profile absent/unresolved; or all matched samples rejected
- Evidence: passive measurements/tracks, reference truth, match/association relations
- Golden: Known angular offsets.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-PSV-002 PASSIVE_LOS_RATE_ERROR_RMSE

- Family: `PASSIVE_SENSOR`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.passive.los_rate_error_rmse@1.0.3`
- Semantic: `tpaa.p1.passive.los_rate_error_rmse@1`
- Value kind/unit: `NUMERIC` / `rad/s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `measured_los_rate_rad_s`, `reference_los_rate_rad_s`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`, `system_type`
- Window: IRST/EO/passive-sensor evaluation windows
- Formula/contract: sqrt(mean((los_rate_meas-los_rate_ref)^2))
- Validity: system_type in {'IRST','EO'}; reference state/association/timing valid; matched sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=LOS_RATE
- N/A: system_type not in {'IRST','EO'}; passive measurement/reference unavailable; reference-match quality profile absent/unresolved; or all matched samples rejected
- Evidence: passive measurements/tracks, reference truth, match/association relations
- Golden: Known LOS-rate residuals.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-PSV-003 PASSIVE_RANGE_ESTIMATE_ERROR_RMSE

- Family: `PASSIVE_SENSOR`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.passive.range_estimate_error_rmse@1.0.3`
- Semantic: `tpaa.p1.passive.range_estimate_error_rmse@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `passive_range_estimate_m`, `reference_range_m`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`, `system_type`
- Window: IRST/EO/passive-sensor evaluation windows
- Formula/contract: sqrt(mean((range_est-range_ref)^2))
- Validity: system_type in {'IRST','EO'}; reference state/association/timing valid; matched sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=RANGE
- N/A: system_type not in {'IRST','EO'}; passive measurement/reference unavailable; reference-match quality profile absent/unresolved; or all matched samples rejected
- Evidence: passive measurements/tracks, reference truth, match/association relations
- Golden: Known passive range estimates.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-PSV-004 PASSIVE_DETECTION_RATE

- Family: `PASSIVE_SENSOR`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.passive.detection_rate@1.0.3`
- Semantic: `tpaa.p1.passive.detection_rate@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `passive_detection_flag`, `evaluation_opportunity_intervals`, `detection_opportunity_id`, `opportunity_profile_id`, `opportunity_profile_version`, `opportunity_profile_hash`, `detection_confirmation_event_id`, `confirmation_profile_id`, `confirmation_profile_version`, `confirmation_profile_hash`, `system_type`
- Window: IRST/EO/passive-sensor evaluation windows
- Formula/contract: detected confirmed passive opportunity count / valid passive opportunity count, using only CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1 and CONTRACT_DETECTION_CONFIRMATION_EVENT_V1 events for the same reference association
- Validity: system_type in {'IRST','EO'}; canonical passive opportunity intervals and confirmation events resolved; authoritative association and Session-Time alignment valid
- N/A: system_type not in {'IRST','EO'}; no valid passive opportunity; opportunity/confirmation contract unresolved; or passive source unavailable
- Evidence: passive measurements/tracks, reference truth, match/association relations
- Golden: Known opportunity/detection fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-PSV-005 PASSIVE_TRACK_CONTINUITY

- Family: `PASSIVE_SENSOR`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.passive.track_continuity@1.0.3`
- Semantic: `tpaa.p1.passive.track_continuity@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `passive_track_valid_intervals`, `evaluation_opportunity_intervals`, `detection_opportunity_id`, `opportunity_profile_id`, `opportunity_profile_version`, `opportunity_profile_hash`, `system_type`
- Window: IRST/EO/passive-sensor evaluation windows
- Formula/contract: duration(valid passive track ∩ canonical passive opportunity)/duration(canonical passive opportunity) using CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1
- Validity: system_type in {'IRST','EO'}; canonical passive opportunity intervals, track validity, association and Session-Time alignment resolved
- N/A: system_type not in {'IRST','EO'}; no valid passive opportunity; or track/association contract unresolved
- Evidence: passive measurements/tracks, reference truth, match/association relations
- Golden: Known passive track gaps.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-PSV-006 PASSIVE_REACQUISITION_TIME

- Family: `PASSIVE_SENSOR`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.passive.reacquisition_time@1.0.4`
- Semantic: `tpaa.p1.passive.reacquisition_time@2`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `passive_drop_time`, `passive_reacquired_time`, `profile.drop_min_duration_s`, `profile.reacquisition_persistence_s`, `profile.max_gap_us`, `system_type`
- Window: IRST/EO/passive-sensor evaluation windows
- Formula/contract: For passive tracks use SM_TRACK_DROP_REACQUIRE_V1 with drop_min_duration_s/reacquisition_persistence_s/max_gap_us. Primary Metric value=MEDIAN_V1(reacquisition_delay) measured from qualified drop start to stable same-association reacquisition; QUANTILE_HF7_V1 P95 is mandatory diagnostic Evidence.
- Validity: system_type in {'IRST','EO'}; track-validity timeline and authoritative same-target association resolved; drop/reacquisition state machine receives continuous Session-Time input subject to max_gap_us
- N/A: system_type not in {'IRST','EO'}; track/association unavailable; or no qualified drop/reacquisition event
- Evidence: passive measurements/tracks, reference truth, match/association relations
- Golden: Known passive reacquisition delays.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-PSV-007 PASSIVE_FALSE_TRACK_RATE

- Family: `PASSIVE_SENSOR`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.passive.false_track_rate@1.0.3`
- Semantic: `tpaa.p1.passive.false_track_rate@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `passive_tracks`, `reference_targets`, `association_result`, `profile.stable_track_persistence_s`, `profile.max_gap_us`, `system_type`, `reference_target_coverage_id`, `reference_target_coverage_version`, `reference_target_coverage_hash`, `reference_target_coverage_status`
- Window: passive tracking windows
- Formula/contract: Among passive tracks qualified by SM_TRACK_STABLE_V1, false_track_rate = count(stable tracks with no valid CONTRACT_ASSOCIATION_RELATION_V1 association) / count(stable qualified passive tracks). Stability uses stable_track_persistence_s/max_gap_us; no geometry-only association is inferred inside this metric.
- Validity: system_type in {'IRST','EO'}; reference_target_coverage_status=COMPLETE for the entire evaluated interval; track stability and authoritative association relation resolved
- N/A: system_type not in {'IRST','EO'}; reference target-set coverage is PARTIAL/UNKNOWN or does not span the full evaluated interval; or track/association unavailable
- Evidence: stable passive tracks, association relation including NO_MATCH/AMBIGUOUS outcome, reference target-set coverage id/version/hash/status
- Golden: Fixture with 10 qualified tracks, 2 unassociated false tracks and one excluded ambiguous track.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ESM-001 EMITTER_DETECTION_RATE

- Family: `RWR_ESM`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.esm.emitter_detection_rate@1.0.2`
- Semantic: `tpaa.p1.esm.emitter_detection_rate@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `reference_emitter_active_intervals`, `esm_detection_intervals`, `detection_opportunity_id`, `opportunity_profile_id`, `opportunity_profile_version`, `opportunity_profile_hash`, `detection_confirmation_event_id`, `confirmation_profile_id`, `confirmation_profile_version`, `confirmation_profile_hash`
- Window: reference emitter-active evaluation windows
- Formula/contract: confirmed detected emitter-opportunity count / valid emitter-opportunity count using CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1 and CONTRACT_DETECTION_CONFIRMATION_EVENT_V1; observed detection outcome never defines the opportunity denominator
- Validity: canonical emitter opportunity intervals and confirmed-detection events resolved; authoritative emitter association and Session-Time alignment valid
- N/A: opportunity contract unavailable/no valid emitter opportunities; confirmation contract unresolved; or ESM source absent
- Evidence: ESM reports, reference emitter truth/event, time alignment, association
- Golden: Known emitter on/off timeline and detections.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ESM-002 EMITTER_BEARING_ERROR_RMSE

- Family: `RWR_ESM`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.esm.emitter_bearing_error_rmse@1.0.2`
- Semantic: `tpaa.p1.esm.emitter_bearing_error_rmse@1`
- Value kind/unit: `NUMERIC` / `rad`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `reported_bearing_rad`, `reference_bearing_rad`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: reference emitter-active evaluation windows
- Formula/contract: sqrt(mean(wrap_pi(reported-reference)^2))
- Validity: reference emitter state/time valid; ESM timestamps aligned; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=BEARING
- N/A: reference emitter activity unavailable or ESM source absent; reference-match quality profile absent/unresolved or all matched samples rejected by the profile
- Evidence: ESM reports, reference emitter truth/event, time alignment, association
- Golden: Bearing wrap fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ESM-003 EMITTER_DETECTION_LATENCY

- Family: `RWR_ESM`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.esm.emitter_detection_latency@1.0.3`
- Semantic: `tpaa.p1.esm.emitter_detection_latency@1`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `opportunity_start_time_us`, `first_confirmed_detection_time_us`, `detection_confirmation_event_id`, `confirmation_profile_id`, `confirmation_profile_version`, `confirmation_profile_hash`, `detection_opportunity_id`, `opportunity_profile_id`, `opportunity_profile_version`, `opportunity_profile_hash`
- Window: reference emitter-active evaluation windows
- Formula/contract: detection_latency_s=(first_confirmed_detection_time_us-opportunity_start_time_us)/1e6 using one CONTRACT_DETECTION_CONFIRMATION_EVENT_V1 event inside its CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1 interval
- Validity: canonical emitter opportunity and confirmed-detection event resolved for the same reference emitter association; Session-Time aligned
- N/A: opportunity/confirmation contract unavailable, no confirmed detection inside a valid opportunity, or ESM source absent
- Evidence: ESM reports, reference emitter truth/event, time alignment, association
- Golden: Known activation and detection delay.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ESM-004 EMITTER_ASSOCIATION_ACCURACY

- Family: `RWR_ESM`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.esm.emitter_association_accuracy@1.0.1`
- Semantic: `tpaa.p1.esm.emitter_association_accuracy@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `esm_emitter_track_id`, `reference_emitter_id`
- Window: reference emitter-active evaluation windows
- Formula/contract: correct association dwell / associated dwell
- Validity: reference emitter state/time valid; ESM timestamps aligned
- N/A: reference emitter activity unavailable or ESM source absent
- Evidence: ESM reports, reference emitter truth/event, time alignment, association
- Golden: Known correct/wrong emitter mapping intervals.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ESM-005 EMITTER_CLASSIFICATION_ACCURACY

- Family: `RWR_ESM`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.esm.emitter_classification_accuracy@1.0.3`
- Semantic: `tpaa.p1.esm.emitter_classification_accuracy@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `reported_emitter_class`, `reference_emitter_class`, `reference_classification_taxonomy_id`, `reference_classification_taxonomy_version`, `reference_classification_taxonomy_hash`
- Window: reference emitter-active evaluation windows
- Formula/contract: Normalize reported_emitter_class and authoritative reference_emitter_class with REFERENCE_CLASSIFICATION_TAXONOMY_CONTRACT_V1. Over authoritative emitter-association intervals where canonical reference label!=UNKNOWN and canonical reported label!=UNKNOWN, primary Metric value emitter_classification_accuracy=correct canonical-label dwell/classified eligible dwell. The canonical taxonomy confusion matrix is mandatory Evidence, not an additional Metric value.
- Validity: authoritative emitter reference/association interval available; taxonomy_id/version/hash resolved; reported label normalizable through the same taxonomy; Session-Time aligned
- N/A: reference emitter classification/taxonomy unavailable or unresolved; association unresolved; reference label quality invalid; or no classified eligible dwell
- Evidence: ESM reports, authoritative emitter reference event, association intervals, taxonomy id/version/hash, alias normalization result, canonical-label confusion matrix
- Golden: Known emitter-class confusion fixture.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-ESM-006 EMITTER_TRACK_CONTINUITY

- Family: `RWR_ESM`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.esm.emitter_track_continuity@1.0.2`
- Semantic: `tpaa.p1.esm.emitter_track_continuity@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `esm_track_valid_intervals`, `reference_emitter_active_intervals`, `detection_opportunity_id`, `opportunity_profile_id`, `opportunity_profile_version`, `opportunity_profile_hash`
- Window: reference emitter-active evaluation windows
- Formula/contract: duration(valid ESM track ∩ canonical emitter opportunity)/duration(canonical emitter opportunity) using CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1
- Validity: canonical emitter opportunity intervals, ESM track validity, association and Session-Time alignment resolved
- N/A: opportunity contract unavailable/no valid emitter opportunities or ESM track/association unresolved
- Evidence: ESM reports, reference emitter truth/event, time alignment, association
- Golden: Known ESM track gaps during active emitter.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-DL-001 MESSAGE_LATENCY

- Family: `DATALINK`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.datalink.message_latency@1.0.2`
- Semantic: `tpaa.p1.datalink.message_latency@1`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `message_send_time_us`, `message_receive_time_us`
- Window: valid data-link/remote-track intervals
- Formula/contract: (receive-send)/1e6
- Validity: send/receive timestamps resolved to Session Time through CONTRACT_TIME_TRANSFORM_V1; link endpoint identity known; receive_time >= send_time
- N/A: send/receive timestamp, TimeTransform, or link endpoint identity unavailable/invalid
- Evidence: raw/link messages, send/receive timestamp provenance, CONTRACT_TIME_TRANSFORM_V1
- Golden: Known timestamp pairs including invalid negative latency rejection.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-DL-002 MESSAGE_JITTER

- Family: `DATALINK`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.datalink.message_jitter@1.0.3`
- Semantic: `tpaa.p1.datalink.message_jitter@1`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `message_latency_series`, `profile.min_message_count`, `profile.max_gap_us`
- Window: valid data-link/remote-track intervals
- Formula/contract: Within one continuous message-validity piece containing at least min_message_count messages and no gap > max_gap_us, compute message_latency_us. message_jitter_us=MAD_V1(message_latency_us). QUANTILE_HF7_V1 P95-P50 latency spread is retained only as diagnostic evidence and is not an alternative metric formula.
- Validity: latency samples satisfy P1-DL-001 timestamp/link validity; sample count >= min_message_count; no internal gap > max_gap_us
- N/A: insufficient valid latency samples; sample count < min_message_count; or gap > max_gap_us
- Evidence: P1-DL-001 latency series, message validity pieces, jitter profile
- Golden: Known latency sequence and MAD.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-DL-003 MESSAGE_LOSS_RATE

- Family: `DATALINK`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.datalink.message_loss_rate@1.0.2`
- Semantic: `tpaa.p1.datalink.message_loss_rate@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `message_sequence_id`, `expected_sequence_domain`
- Window: valid data-link/remote-track intervals
- Formula/contract: Within each canonical sequence_epoch_id governed by SM_DATALINK_SEQUENCE_EPOCH_V1, expected_count is derived from the declared expected_sequence_domain/modulus and observed ordered sequence positions. message_loss_rate = missing_expected_positions / expected_positions. Do not infer a reset from arbitrary backward jumps; modulo wrap remains inside the epoch.
- Validity: canonical sequence_epoch_id/domain/modulus resolved; link endpoint identity known
- N/A: sequence epoch/domain/modulus or link endpoint identity unavailable
- Evidence: raw/link messages, sequence epochs, remote track states, reference truth when applicable
- Golden: Sequence fixture with reset and two true losses.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-DL-004 OUT_OF_ORDER_RATE

- Family: `DATALINK`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.datalink.out_of_order_rate@1.0.2`
- Semantic: `tpaa.p1.datalink.out_of_order_rate@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `message_sequence_id`, `receive_order`
- Window: valid data-link/remote-track intervals
- Formula/contract: Within each canonical sequence_epoch_id from CONTRACT_TDL_SEQUENCE_EPOCH_V1 / SM_DATALINK_SEQUENCE_EPOCH_V1, out_of_order_rate = out_of_order_received_messages / received_messages. Epoch boundaries are authoritative; the metric must not infer resets from arbitrary backward sequence jumps.
- Validity: canonical sequence_epoch_id and receive order resolved; link endpoint identity known
- N/A: sequence epoch/receive order or link endpoint identity unavailable
- Evidence: raw/link messages, sequence epochs, remote track states, reference truth when applicable
- Golden: Known reorder sequence.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-DL-005 REMOTE_TRACK_AGE

- Family: `DATALINK`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.datalink.remote_track_age@1.0.3`
- Semantic: `tpaa.p1.datalink.remote_track_age@1`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `remote_track_effective_time_us`, `local_use_time_us`
- Window: valid data-link/remote-track intervals
- Formula/contract: remote_track_age_s=(local_use_time_us-remote_track_effective_time_us)/1e6
- Validity: remote_track_effective_time_us and local_use_time_us resolved to Session Time; remote track validity known; link endpoint identity known
- N/A: remote effective/local use time, track-validity state, or link endpoint identity unavailable
- Evidence: remote track states, local-use timestamps, track validity timeline, CONTRACT_TIME_TRANSFORM_V1
- Golden: Known age values.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-DL-006 REMOTE_TRACK_POSITION_ERROR_RMSE

- Family: `DATALINK`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.datalink.remote_track_position_error_rmse@1.0.2`
- Semantic: `tpaa.p1.datalink.remote_track_position_error_rmse@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `remote_track_position_ecef_m`, `reference_target_position_ecef_m`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: valid data-link/remote-track intervals
- Formula/contract: sqrt(mean(||p_remote-p_ref||^2))
- Validity: remote track validity and authoritative target association resolved; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=POSITION_3D; link endpoint identity known
- N/A: remote track/reference/association unavailable; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile
- Evidence: remote track states, association relation, reference relative state, P1-QA-005 interpolation quality
- Golden: Known remote-track position residuals.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-DL-007 REMOTE_TRACK_VELOCITY_ERROR_RMSE

- Family: `DATALINK`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.datalink.remote_track_velocity_error_rmse@1.0.3`
- Semantic: `tpaa.p1.datalink.remote_track_velocity_error_rmse@1`
- Value kind/unit: `NUMERIC` / `m/s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `remote_track_velocity_ecef_mps`, `reference_target_velocity_ecef_mps`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: valid data-link/remote-track intervals
- Formula/contract: sqrt(mean(||v_remote-v_ref||^2))
- Validity: remote track validity and authoritative target association resolved; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=VELOCITY_3D; link endpoint identity known
- N/A: remote track/reference/association unavailable; reference-match quality profile absent/unresolved; or all matched samples rejected by the profile
- Evidence: remote track velocity states, association relation, reference relative state, P1-QA-005 interpolation quality
- Golden: Known remote velocity residuals.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-DL-008 REMOTE_TRACK_CONTINUITY

- Family: `DATALINK`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.datalink.remote_track_continuity@1.0.3`
- Semantic: `tpaa.p1.datalink.remote_track_continuity@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `remote_track_valid_intervals`, `reference_target_present_intervals`, `detection_opportunity_id`, `opportunity_profile_id`, `opportunity_profile_version`, `opportunity_profile_hash`
- Window: valid data-link/remote-track intervals
- Formula/contract: duration(valid remote track ∩ canonical remote-track opportunity)/duration(canonical remote-track opportunity) using CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1
- Validity: canonical remote-track opportunity intervals, remote track validity, authoritative target association and link endpoint identity resolved
- N/A: opportunity contract unavailable/no valid remote-track opportunities or remote track/association unresolved
- Evidence: remote track validity intervals, association relation, reference target/opportunity intervals
- Golden: Known remote track gaps.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-FUS-001 FUSED_POSITION_ERROR_RMSE

- Family: `SENSOR_FUSION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.fusion.position_error_rmse@1.0.3`
- Semantic: `tpaa.p1.fusion.position_error_rmse@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `fused_track_position_ecef_m`, `reference_target_position_ecef_m`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: valid fused-track/reference-matched windows
- Formula/contract: sqrt(mean(||p_fused-p_ref||^2))
- Validity: canonical fused track is valid; fusion provenance/source membership and authoritative target association resolved; matched reference position and timestamps available; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=POSITION_3D
- N/A: no valid fused/reference position samples or fusion provenance/association unresolved; reference-match quality profile absent/unresolved or all matched samples rejected by the profile
- Evidence: fused track states, fusion source contribution/member refs, association relation, reference position states, time/match provenance
- Golden: Known fused-track position residuals.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-FUS-002 FUSED_VELOCITY_ERROR_RMSE

- Family: `SENSOR_FUSION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.fusion.velocity_error_rmse@1.0.3`
- Semantic: `tpaa.p1.fusion.velocity_error_rmse@1`
- Value kind/unit: `NUMERIC` / `m/s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `fused_track_velocity_ecef_mps`, `reference_target_velocity_ecef_mps`, `reference_match_quality_profile_id`, `reference_match_quality_profile_version`, `reference_match_quality_profile_hash`
- Window: valid fused-track/reference-matched windows
- Formula/contract: sqrt(mean(||v_fused-v_ref||^2))
- Validity: canonical fused track is valid; fusion provenance/source membership and authoritative target association resolved; matched reference velocity and timestamps available; matched reference sample passes CONTRACT_REFERENCE_MATCH_QUALITY_PROFILE_V1 for error_domain=VELOCITY_3D
- N/A: no valid fused/reference velocity samples or fusion provenance/association unresolved; reference-match quality profile absent/unresolved or all matched samples rejected by the profile
- Evidence: fused track states, fusion source contribution/member refs, association relation, reference velocity states, time/match provenance
- Golden: Known fused velocity residuals.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-FUS-003 FUSION_LATENCY

- Family: `SENSOR_FUSION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.fusion.latency@1.0.4`
- Semantic: `tpaa.p1.fusion.latency@1`
- Value kind/unit: `NUMERIC` / `s`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `source_update_effective_time_us`, `fused_state_effective_time_us`
- Window: fused-update windows with resolved causal source provenance
- Formula/contract: For each fused update, SM_FUSION_CAUSAL_MATCH_V1 selects the latest causally eligible source update referenced by frozen fusion provenance. fusion_latency_s=(fused_state_effective_time_us-source_update_effective_time_us)/1e6. Geometry-only re-association is forbidden inside this metric.
- Validity: fusion provenance/source membership available; fused/source effective timestamps resolved to Session Time; causal source update resolved by SM_FUSION_CAUSAL_MATCH_V1
- N/A: fusion provenance unavailable, source update unresolved, or effective timestamps not alignable to Session Time
- Evidence: fused update, source contribution/member refs, causal-match evidence, time alignment provenance
- Golden: Synthetic source update followed by delayed fused update.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-FUS-004 FUSED_TRACK_CONTINUITY

- Family: `SENSOR_FUSION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.fusion.track_continuity@1.0.3`
- Semantic: `tpaa.p1.fusion.track_continuity@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `fused_track_valid_intervals`, `reference_target_present_intervals`, `detection_opportunity_id`, `opportunity_profile_id`, `opportunity_profile_version`, `opportunity_profile_hash`
- Window: valid fused-opportunity windows
- Formula/contract: duration(valid fused track ∩ canonical fused opportunity)/duration(canonical fused opportunity) using CONTRACT_DETECTION_OPPORTUNITY_INTERVAL_V1
- Validity: canonical fused opportunity intervals, fusion provenance, fused track validity and authoritative target association resolved
- N/A: opportunity contract unavailable/no valid fused opportunities or fusion provenance/track validity/association unresolved
- Evidence: fused track validity intervals, fusion source contribution/member refs, association relation, opportunity intervals
- Golden: Known fused track gaps.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-FUS-005 DUPLICATE_SUPPRESSION_RATE

- Family: `SENSOR_FUSION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.fusion.duplicate_suppression_rate@1.0.2`
- Semantic: `tpaa.p1.fusion.duplicate_suppression_rate@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `source_tracks_by_truth`, `fused_tracks_by_truth`, `profile.duplicate_persistence_s`
- Window: eligible associated fused-track target-present windows
- Formula/contract: A duplicate interval exists when more than one fused track is simultaneously associated with the same reference target continuously for at least duplicate_persistence_s. duplicate_suppression_rate = 1 - duplicate_fused_track_dwell / eligible_target_dwell.
- Validity: fusion provenance and authoritative association timeline available; eligible associated target-present dwell resolved; timestamps aligned
- N/A: fusion provenance/association unavailable or no eligible associated target-present dwell
- Evidence: fused track identities, fusion source contribution/member refs, association intervals, duplicate episode intervals
- Golden: Two source tracks same truth fused into one except one duplicate interval.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-FUS-006 FUSION_ASSOCIATION_ACCURACY

- Family: `SENSOR_FUSION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.fusion.association_accuracy@1.0.2`
- Semantic: `tpaa.p1.fusion.association_accuracy@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `source_track_membership`, `reference_target_ids`, `fused_track_id`
- Window: eligible fused associated windows
- Formula/contract: correct source-to-truth membership dwell / fused associated dwell
- Validity: fusion source membership/provenance and authoritative source/target association intervals available; timestamps aligned
- N/A: fusion provenance/association unavailable or no eligible fused associated dwell
- Evidence: fused track/source membership, fusion provenance, authoritative association intervals, correct/incorrect membership dwell
- Golden: Known fusion membership with one wrong source association.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-FUS-007 TRACK_HANDOVER_CONTINUITY

- Family: `SENSOR_FUSION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.fusion.handover_continuity@1.0.4`
- Semantic: `tpaa.p1.fusion.handover_continuity@1`
- Value kind/unit: `NUMERIC` / `ratio`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `handover_event_id`, `reference_target_id`, `pre_fused_track_id`, `post_fused_track_id`, `handover_time_us`, `identity_preserved`, `handover_profile_id`, `handover_profile_version`, `handover_profile_hash`
- Window: qualified fusion handover events
- Formula/contract: handover_continuity=count(canonical qualified CONTRACT_FUSION_HANDOVER_EVENT_V1 events with identity_preserved=true)/count(all canonical qualified handover events). Qualification/persistence/gap and source-membership change are owned by WRE event construction, not this Metric.
- Validity: at least one canonical qualified handover event with frozen profile/provenance and authoritative reference association
- N/A: no canonical qualified handover event or handover-event provenance/association unresolved
- Evidence: qualified handover event, pre/post source membership, fused_track_id, authoritative reference_target_id association
- Golden: Radar→radar+IRST→IRST handover with one identity break.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

### P1-FUS-008 TRACK_HANDOVER_JUMP

- Family: `SENSOR_FUSION`
- Subject: `MISSION_SYSTEM_INSTANCE`
- Algorithm: `alg.tpaa.p1.fusion.handover_jump@1.0.4`
- Semantic: `tpaa.p1.fusion.handover_jump@1`
- Value kind/unit: `NUMERIC` / `m`
- Delivery: `M3` / `P1_REMAINDER_84`; P1 longitudinal: `YES`
- Inputs: `handover_event_id`, `handover_time_us`, `pre_fused_track_id`, `post_fused_track_id`, `fused_position_before`, `fused_velocity_before`, `fused_position_after`, `pre_handover_state_time_us`, `handover_profile_id`, `handover_profile_version`, `handover_profile_hash`, `profile.max_propagation_age_us`
- Window: qualified fusion handover events with propagatable pre-handover state
- Formula/contract: For each canonical qualified CONTRACT_FUSION_HANDOVER_EVENT_V1, propagate the last pre-handover fused position to handover_time_us with CV_PROPAGATION_V1 only when handover_time_us-pre_handover_state_time_us<=max_propagation_age_us: p_pred=p_before+v_before*dt. track_handover_jump_m=||p_after-p_pred||. Velocity discontinuity is not part of this metric.
- Validity: canonical qualified handover event resolved; pre/post fused states and pre-handover velocity valid; propagation age <=max_propagation_age_us
- N/A: handover event absent/unresolved; required fused state/velocity unavailable; or propagation age exceeds max_propagation_age_us
- Evidence: qualified handover event, pre/post fused states, pre-handover velocity, CV propagation trace, fusion provenance
- Golden: Synthetic source handover with known 120 m discontinuity.

> GENERATED MIRROR from `canonical/P1_METRIC_CATALOG.json`; not an independent definition authority.

## 8. P2～P6 / 训练评价指标族扩展边界

本分册的 116 项仍是**唯一可执行 P1 Catalog**。`EXTENSION_METRIC_FAMILY_REGISTRY.json` 只冻结未来语义族，不创建第二套 executable code/formula authority。

未来扩展至少包括：Training Data Quality、World Relation/Gap、Basic/WVR/BVR/Strike Training、Outcome、Human Competency、Team/Mission、P2 Context-adjusted、P3 Capability、Longitudinal Process、General Longitudinal、Model Profile、Instructor/Agreement 等 family。

任何 family 进入对应 M 里程碑实施时必须形成独立 versioned metric catalog/definition，并补齐 formula/operator、input authority、eligibility、unit/value kind、evidence、Golden 和 migration mapping；不得把历史交付标签当作 current M，也不得在 116 项中塞入不同 claim level 的新含义。

## 9. Metric / Assessment / Estimate 分工

- Metric：可重复的物理/统计/事件测量；
- Assessment Profile：把 eligible Metric/Event/Evidence 映射到 Qualification/Competency；
- P2 Attribution：在明确 model/spec 下形成 adjusted/candidate factor products；
- P3 Capability Estimate：长期参考条件估计；
- P6 Forecast：未来分布/情景产品。

这些产品不能用一个“score metric”统一替代。若某未来需求实际是 assessment、estimate 或 forecast，应建立对应产品 contract，而不是滥加 Metric code。

## 10. Outcome 与 J 边界

Official Success/Validity/Result Class 只能来自 approved J 或明确 authority。内部 Assessment 可以形成 Objective Completion Evidence，但不得写入 J，也不得把 Action 自动解释为 official success。

## 11. Longitudinal 未来指标

R39 中 TP gap、PA response、AJ link、team divergence、chain completeness、HMI effectiveness、training exposure/decline、aircraft change point/model profile 等知识已在 extension family registry 保留。未来实现应采用独立 semantic version 和 comparison/cohort contract；不得通过从一个 P1 trend value 派生自由 JSON 来规避正式 Metric/Estimate 定义。
