"""Generated TPAA P/M/WS program registries. Do not edit by hand."""

from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

class CapabilityPhase(StrEnum):
    P1 = 'P1'
    P2 = 'P2'
    P3 = 'P3'
    P4 = 'P4'
    P5 = 'P5'
    P6 = 'P6'

class DevelopmentMilestone(StrEnum):
    M0 = 'M0'
    M1 = 'M1'
    M2 = 'M2'
    M3 = 'M3'
    M4 = 'M4'
    M5 = 'M5'
    M6 = 'M6'
    M7 = 'M7'
    M8 = 'M8'
    M9 = 'M9'

class EngineeringWorkstream(StrEnum):
    WS_API = 'WS-API'
    WS_ASSESS = 'WS-ASSESS'
    WS_CAPABILITY = 'WS-CAPABILITY'
    WS_CORE = 'WS-CORE'
    WS_DATA = 'WS-DATA'
    WS_DEVOPS = 'WS-DEVOPS'
    WS_GOVERNANCE = 'WS-GOVERNANCE'
    WS_GUI = 'WS-GUI'
    WS_INTEROP = 'WS-INTEROP'
    WS_LONGITUDINAL = 'WS-LONGITUDINAL'
    WS_METRIC = 'WS-METRIC'
    WS_OBSERVATION = 'WS-OBSERVATION'
    WS_PERFORMANCE = 'WS-PERFORMANCE'
    WS_PLATFORM = 'WS-PLATFORM'
    WS_SECURITY = 'WS-SECURITY'
    WS_STORAGE = 'WS-STORAGE'
    WS_TEST = 'WS-TEST'
    WS_WORLD = 'WS-WORLD'

CAPABILITY_PHASES: tuple[Mapping[str, object], ...] = (
    MappingProxyType({
        'p_code': 'P1',
        'name': 'Observed Performance',
        'purpose': 'Observed aircraft and mission-system engineering performance; no context attribution or intrinsic-capability claim.',
        'baseline_status': 'CURRENT_BASELINE',
        'frozen_extension_scope': 'Aircraft and mission-system observed-performance products, evidence and numeric longitudinal trend.',
    }),
    MappingProxyType({
        'p_code': 'P2',
        'name': 'Context Attribution & Normalization',
        'purpose': 'Attribute/normalize observed performance using frozen context/factor views.',
        'baseline_status': 'DESIGN_CONTRACT_FROZEN',
        'frozen_extension_scope': 'Factor views, attribution/normalization, adjusted estimate and identifiability governance.',
    }),
    MappingProxyType({
        'p_code': 'P3',
        'name': 'Intrinsic Capability / Aircraft Twin',
        'purpose': 'Estimate intrinsic capability under governed as-of lifecycle/configuration semantics.',
        'baseline_status': 'DESIGN_CONTRACT_FROZEN',
        'frozen_extension_scope': 'Reference-condition longitudinal estimate, capability model/surface, aircraft twin and model profile.',
    }),
    MappingProxyType({
        'p_code': 'P4',
        'name': 'Human-Machine Assessment',
        'purpose': 'Assess W↔P↔A↔M evidence and human-machine interaction.',
        'baseline_status': 'DESIGN_CONTRACT_FROZEN',
        'frozen_extension_scope': 'Individual/human-machine qualification, competency diagnostics, evidence and instructor-review workflow.',
    }),
    MappingProxyType({
        'p_code': 'P5',
        'name': 'Team / Mission / System Assessment',
        'purpose': 'Multi-entity/team/mission reconstruction and assessment.',
        'baseline_status': 'DESIGN_CONTRACT_FROZEN',
        'frozen_extension_scope': 'Team/package/mission objective assessment with composition-aware longitudinal analysis.',
    }),
    MappingProxyType({
        'p_code': 'P6',
        'name': 'Prediction / Counterfactual / Closed Loop',
        'purpose': 'Governed forecast/counterfactual products physically separated from facts.',
        'baseline_status': 'DESIGN_CONTRACT_FROZEN',
        'frozen_extension_scope': 'Forecast/counterfactual/recommendation products separated from facts and requiring explicit assumptions/approval.',
    }),
)

DEVELOPMENT_MILESTONES: tuple[Mapping[str, object], ...] = (
    MappingProxyType({
        'code': 'M0',
        'name': 'Engineering Bootstrap',
        'name_cn': '工程启动基线',
        'objective': 'Create a buildable/testable Windows+Linux software substrate; no capability Phase is admitted by M0 alone.',
        'p_capability_impact': (),
        'required_workstreams': ('WS-CORE', 'WS-STORAGE', 'WS-API', 'WS-GUI', 'WS-TEST', 'WS-PLATFORM', 'WS-SECURITY', 'WS-DEVOPS', 'WS-GOVERNANCE'),
    }),
    MappingProxyType({
        'code': 'M1',
        'name': 'P1 Minimum Vertical Slice',
        'name_cn': 'P1最小端到端闭环',
        'objective': 'Run one Basic Flight synthetic vertical slice Source→Canonical→Context→Episode/Stage→World→representative metrics→Observation→Release→API→GUI on Windows and Linux.',
        'p_capability_impact': ('P1',),
        'required_workstreams': ('WS-DATA', 'WS-WORLD', 'WS-METRIC', 'WS-OBSERVATION', 'WS-STORAGE', 'WS-API', 'WS-GUI', 'WS-TEST', 'WS-PLATFORM'),
    }),
    MappingProxyType({
        'code': 'M2',
        'name': 'P1 Basic Flight Complete',
        'name_cn': 'P1基本飞行完整能力',
        'objective': 'Complete Basic Flight P1 capability plus the 32-item P1 foundation metric delivery batch and representative Golden evidence.',
        'p_capability_impact': ('P1',),
        'required_workstreams': ('WS-DATA', 'WS-WORLD', 'WS-METRIC', 'WS-OBSERVATION', 'WS-GUI', 'WS-TEST'),
    }),
    MappingProxyType({
        'code': 'M3',
        'name': 'P1 Four-Training-Type Complete',
        'name_cn': 'P1四类训练观测能力完整',
        'objective': 'Complete P1 Basic/WVR/BVR/Strike observed-performance capability and all 116 executable P1 metrics; P1 formulas/semantics are production candidates.',
        'p_capability_impact': ('P1',),
        'required_workstreams': ('WS-WORLD', 'WS-METRIC', 'WS-OBSERVATION', 'WS-API', 'WS-GUI', 'WS-TEST'),
    }),
    MappingProxyType({
        'code': 'M4',
        'name': 'P1 Longitudinal & Debrief Closure',
        'name_cn': 'P1长期趋势与复盘闭环',
        'objective': 'Close P1 aircraft/mission-system longitudinal trends, evidence-first debrief/analytics and historical replay without activating P4 human assessment.',
        'p_capability_impact': ('P1',),
        'required_workstreams': ('WS-LONGITUDINAL', 'WS-OBSERVATION', 'WS-GUI', 'WS-API', 'WS-TEST', 'WS-GOVERNANCE'),
    }),
    MappingProxyType({
        'code': 'M5',
        'name': 'P1 Product Qualification & Release',
        'name_cn': 'P1产品资格与正式发布',
        'objective': 'Qualify P1 on mandatory Windows/Linux profiles, target workload, security/governance, packaging, upgrade/rollback and release acceptance.',
        'p_capability_impact': ('P1',),
        'required_workstreams': ('WS-PLATFORM', 'WS-PERFORMANCE', 'WS-SECURITY', 'WS-DEVOPS', 'WS-TEST', 'WS-GOVERNANCE'),
    }),
    MappingProxyType({
        'code': 'M6',
        'name': 'P2 Attribution Activation',
        'name_cn': 'P2归因/条件调整启用',
        'objective': 'Admit P2 Context Attribution & Normalization after identifiability, leakage, uncertainty and evidence gates are validated.',
        'p_capability_impact': ('P2',),
        'required_workstreams': ('WS-CAPABILITY', 'WS-DATA', 'WS-TEST', 'WS-GUI', 'WS-GOVERNANCE'),
    }),
    MappingProxyType({
        'code': 'M7',
        'name': 'P3 Capability/Twin Activation',
        'name_cn': 'P3能力模型/数字孪生启用',
        'objective': 'Admit P3 capability models, aircraft twin revisions and model profiles with applicability/knowledge-time/model validation gates.',
        'p_capability_impact': ('P3',),
        'required_workstreams': ('WS-CAPABILITY', 'WS-LONGITUDINAL', 'WS-TEST', 'WS-GUI', 'WS-GOVERNANCE'),
    }),
    MappingProxyType({
        'code': 'M8',
        'name': 'P4/P5 Training Assessment Activation',
        'name_cn': 'P4/P5训练评价启用',
        'objective': 'Admit P4 individual/human-machine and P5 team/package/mission assessment with instructor, privacy, scope separation and longitudinal evidence gates.',
        'p_capability_impact': ('P4', 'P5'),
        'required_workstreams': ('WS-ASSESS', 'WS-WORLD', 'WS-LONGITUDINAL', 'WS-GUI', 'WS-SECURITY', 'WS-TEST', 'WS-GOVERNANCE'),
    }),
    MappingProxyType({
        'code': 'M9',
        'name': 'P6 Joint/LVC & Predictive Activation',
        'name_cn': 'P6联合/LVC与预测闭环启用',
        'objective': 'Admit P6 Joint/LVC and forecast/counterfactual/recommendation products with fact/projection separation, external interoperability and approval gates.',
        'p_capability_impact': ('P6',),
        'required_workstreams': ('WS-INTEROP', 'WS-CAPABILITY', 'WS-ASSESS', 'WS-GUI', 'WS-SECURITY', 'WS-TEST', 'WS-GOVERNANCE'),
    }),
)

ENGINEERING_WORKSTREAMS: tuple[Mapping[str, object], ...] = (
    MappingProxyType({
        'code': 'WS-API',
        'name': 'Application / API / DTO',
        'scope': 'Use cases, REST, DTOs, idempotency and service integration.',
    }),
    MappingProxyType({
        'code': 'WS-ASSESS',
        'name': 'Training Assessment',
        'scope': 'P4/P5 qualification, competency, evidence, instructor review and team/mission assessment.',
    }),
    MappingProxyType({
        'code': 'WS-CAPABILITY',
        'name': 'Attribution / Capability Intelligence',
        'scope': 'P2 attribution/normalization and P3 capability/twin/model profile.',
    }),
    MappingProxyType({
        'code': 'WS-CORE',
        'name': 'Core Contracts & Code Generation',
        'scope': 'Core artifacts, generated types/enums, contract loading and semantic governance.',
    }),
    MappingProxyType({
        'code': 'WS-DATA',
        'name': 'Data / Registry / Canonical',
        'scope': 'Source registry, ingest, provenance, time, entity, canonical facts and context.',
    }),
    MappingProxyType({
        'code': 'WS-DEVOPS',
        'name': 'CI/CD / Build / Release',
        'scope': 'Dependency lock, SBOM, package manifest, release, upgrade/rollback and cold-start.',
    }),
    MappingProxyType({
        'code': 'WS-GOVERNANCE',
        'name': 'Architecture / Change Governance',
        'scope': 'Baseline lock, traceability, plugin/model/profile publication and change closure.',
    }),
    MappingProxyType({
        'code': 'WS-GUI',
        'name': 'GUI / Visualization / Debrief',
        'scope': 'PySide6, timeline, replay, evidence, assessment and analytics UI.',
    }),
    MappingProxyType({
        'code': 'WS-INTEROP',
        'name': 'External / LVC Interoperability',
        'scope': 'External gateways, protocol adapters, time/frame conversion and LVC integration.',
    }),
    MappingProxyType({
        'code': 'WS-LONGITUDINAL',
        'name': 'Longitudinal Analytics',
        'scope': 'P1 observed trend and later capability/person/team longitudinal products.',
    }),
    MappingProxyType({
        'code': 'WS-METRIC',
        'name': 'Metric Engine',
        'scope': 'P1 metric operators, 116 metrics, input authority, evidence and metric publication.',
    }),
    MappingProxyType({
        'code': 'WS-OBSERVATION',
        'name': 'Observation / Release / Replay',
        'scope': 'Published observations, immutable release, historical replay and provenance.',
    }),
    MappingProxyType({
        'code': 'WS-PERFORMANCE',
        'name': 'Performance & Scalability',
        'scope': 'Workload envelope, profiling, concurrency, resource safety and qualification.',
    }),
    MappingProxyType({
        'code': 'WS-PLATFORM',
        'name': 'Cross-Platform Runtime',
        'scope': 'Windows/Linux adapters, packaging, logical equivalence and runtime certification.',
    }),
    MappingProxyType({
        'code': 'WS-SECURITY',
        'name': 'Security & Data Governance',
        'scope': 'Identity, RBAC, audit, privacy, data handling and export governance.',
    }),
    MappingProxyType({
        'code': 'WS-STORAGE',
        'name': 'Persistence & Migration',
        'scope': 'DB schema, migrations, repositories, object/Parquet storage and recovery.',
    }),
    MappingProxyType({
        'code': 'WS-TEST',
        'name': 'Verification / Golden / Replay',
        'scope': 'Unit, contract, Golden, replay, migration, E2E and acceptance evidence.',
    }),
    MappingProxyType({
        'code': 'WS-WORLD',
        'name': 'Episode / Stage / World / Event',
        'scope': 'Episode detection, Stage projection, C/W/P/A/J/M reconstruction, events and relations.',
    }),
)
