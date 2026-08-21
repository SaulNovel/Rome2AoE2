from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .errors import ConverterError, ErrorCode


class CapabilityStatus(str, Enum):
    VALIDATED = "VALIDATED"


@dataclass(frozen=True)
class Capability:
    category: str
    key: str
    status: CapabilityStatus
    evidence: str


CAPABILITIES = {
    ("MATERIAL", key): Capability("MATERIAL", key, CapabilityStatus.VALIDATED,
                                  "exact Hastati oracle parity / captured WeightedDirtmap recovery")
    for key in ("DefaultMaterial", "Weighted", "WeightedDirtmap",
                "WeightedSkinDirtmap", "DecalDirtmap")
}
CAPABILITIES.update({
    ("ATTACHMENT", "crest_centre"): Capability("ATTACHMENT", "crest_centre", CapabilityStatus.VALIDATED,
                                                 "generic asset-pair contact solver"),
    ("ATTACHMENT", "one_handed_blade/weapon_02"): Capability(
        "ATTACHMENT", "one_handed_blade/weapon_02", CapabilityStatus.VALIDATED,
        "RMV v_pivot plus geometry grip validation"),
    ("ATTACHMENT", "shield/weapon_03"): Capability("ATTACHMENT", "shield/weapon_03",
                                                    CapabilityStatus.VALIDATED, "source socket and RMV pivot"),
    ("ATTACHMENT", "javelin/weapon_05"): Capability("ATTACHMENT", "javelin/weapon_05",
                                                    CapabilityStatus.VALIDATED, "source socket and RMV pivot"),
    ("RENDER", "infantry_static_review_v1"): Capability(
        "RENDER", "infantry_static_review_v1", CapabilityStatus.VALIDATED,
        "approved Hastati oracle camera and captured runtime presentation"),
})


def require_capabilities(category: str, keys: Iterable[str]) -> list[Capability]:
    resolved = []
    for key in sorted(set(keys)):
        capability = CAPABILITIES.get((category, key))
        if capability is None or capability.status != CapabilityStatus.VALIDATED:
            raise ConverterError(ErrorCode.UNSUPPORTED_CAPABILITY,
                                 "Conversion requires a capability that has not been validated",
                                 category=category, capability=key)
        resolved.append(capability)
    return resolved


def conversion_capabilities(materials: Iterable[str]) -> dict[str, list[dict[str, str]]]:
    required = {
        "MATERIAL": list(materials),
        "ATTACHMENT": ["crest_centre", "one_handed_blade/weapon_02",
                       "shield/weapon_03", "javelin/weapon_05"],
        "RENDER": ["infantry_static_review_v1"],
    }
    return {category: [{"key": item.key, "status": item.status.value, "evidence": item.evidence}
                       for item in require_capabilities(category, keys)]
            for category, keys in required.items()}
