"""Authoritative W4 projection of the R3.3 P01-P13 GUI page catalogue."""

from __future__ import annotations

from dataclasses import dataclass


class PageContractError(ValueError):
    """Stable failure raised when the GUI page catalogue drifts."""


@dataclass(frozen=True, slots=True)
class PageContract:
    slot: str
    key: str
    title: str
    navigation_group: str
    surface: str
    semantic_class: str
    purpose: str
    object_name: str


PAGE_CONTRACTS = (
    PageContract(
        "P01",
        "TRAINING_SESSION_LIST",
        "Training Session List",
        "Training Sessions",
        "M1",
        "P1",
        "Session import, immutable release status, and filtering",
        "tpaaPageP01TrainingSessions",
    ),
    PageContract(
        "P02",
        "PLATFORM_PERFORMANCE_OVERVIEW",
        "Session / Episode & Platform Performance",
        "Episode Review",
        "M1/M3",
        "P1",
        "Session and Episode overview with aircraft and mission-system observations",
        "tpaaPageP02PlatformPerformance",
    ),
    PageContract(
        "P03",
        "INTERACTIVE_EVIDENCE_DEBRIEF",
        "Interactive Evidence / Episode Debrief",
        "Episode Review",
        "M1/M4",
        "P1/P4+",
        "Release-bound replay, master timeline, evidence, and debrief",
        "tpaaPageP03EvidenceDebrief",
    ),
    PageContract(
        "P04",
        "INDIVIDUAL_TRAINING_ASSESSMENT",
        "Individual Training Assessment",
        "Human Capability",
        "M8",
        "P4",
        "Individual Basic and human-machine assessment",
        "tpaaPageP04IndividualAssessment",
    ),
    PageContract(
        "P05",
        "TEAM_MISSION_ASSESSMENT",
        "Team / Package / Mission Assessment",
        "Team Capability",
        "M8",
        "P5",
        "WVR, BVR, Strike, team, package, and mission assessment",
        "tpaaPageP05TeamMissionAssessment",
    ),
    PageContract(
        "P06",
        "AIRCRAFT_CAPABILITY_TWIN",
        "Aircraft Capability Digital Twin",
        "Aircraft Capability",
        "M7",
        "P3",
        "Aircraft CAP-L3 and immutable digital-twin estimates",
        "tpaaPageP06AircraftTwin",
    ),
    PageContract(
        "P07",
        "AIRCRAFT_MODEL_CAPABILITY",
        "Aircraft Model Capability Profile",
        "Aircraft Capability",
        "M7",
        "P3",
        "Model, block, and configuration capability profile",
        "tpaaPageP07ModelCapability",
    ),
    PageContract(
        "P08",
        "CONTEXT_ADJUSTMENT",
        "Context Adjustment / Capability Separation",
        "Aircraft Capability",
        "M6",
        "P2",
        "Association-only attribution, normalization, and CAP-L2 separation",
        "tpaaPageP08ContextAdjustment",
    ),
    PageContract(
        "P09",
        "CAPABILITY_EVOLUTION",
        "Observed Trend / Capability Evolution",
        "Aircraft Capability",
        "M4/M7",
        "P1/P3",
        "Aircraft and mission-system observed trends and capability evolution",
        "tpaaPageP09CapabilityEvolution",
    ),
    PageContract(
        "P10",
        "LONGITUDINAL_HUMAN_TEAM",
        "Longitudinal Human / Team",
        "Human Capability",
        "M4/M8",
        "P4/P5",
        "Comparable individual and team longitudinal views",
        "tpaaPageP10LongitudinalHumanTeam",
    ),
    PageContract(
        "P11",
        "COURSE_UNIT_JOINT_PLANNING",
        "Course / Unit / Joint-LVC & Planning",
        "Course & Unit",
        "M9",
        "P5/P6",
        "Course, unit, Joint-LVC, forecast, and what-if planning",
        "tpaaPageP11CourseUnitPlanning",
    ),
    PageContract(
        "P12",
        "DATA_QUALITY_ELIGIBILITY",
        "Data Quality & Observation Eligibility",
        "Data Quality",
        "M1/M3",
        "P1",
        "Source, World, time, association, and observation eligibility evidence",
        "tpaaPageP12DataQuality",
    ),
    PageContract(
        "P13",
        "GOVERNANCE",
        "Profile / Version / Publication / Model Governance",
        "Governance",
        "Runtime",
        "P1+",
        "Profiles, contexts, releases, models, permissions, audit, and runtime",
        "tpaaPageP13Governance",
    ),
)


def validate_page_contracts(contracts: tuple[PageContract, ...] = PAGE_CONTRACTS) -> None:
    expected_slots = tuple(f"P{index:02d}" for index in range(1, 14))
    if tuple(item.slot for item in contracts) != expected_slots:
        raise PageContractError("W4_PAGE_SLOT_MISMATCH")
    for field in ("key", "title", "object_name"):
        values = tuple(getattr(item, field) for item in contracts)
        if len(set(values)) != len(values):
            raise PageContractError(f"W4_PAGE_{field.upper()}_DUPLICATE")
    if contracts[5].key != "AIRCRAFT_CAPABILITY_TWIN":
        raise PageContractError("W4_P06_SEMANTIC_DRIFT")
    if contracts[7].key != "CONTEXT_ADJUSTMENT":
        raise PageContractError("W4_P08_SEMANTIC_DRIFT")
    if contracts[11].key != "DATA_QUALITY_ELIGIBILITY":
        raise PageContractError("W4_P12_SEMANTIC_DRIFT")


def page_contract(slot: str) -> PageContract:
    for contract in PAGE_CONTRACTS:
        if contract.slot == slot:
            return contract
    raise PageContractError(f"W4_PAGE_UNKNOWN:{slot}")


__all__ = [
    "PAGE_CONTRACTS",
    "PageContract",
    "PageContractError",
    "page_contract",
    "validate_page_contracts",
]
