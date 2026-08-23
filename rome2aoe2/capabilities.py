from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .errors import ConverterError, ErrorCode


class CapabilityStatus(str, Enum):
    VALIDATED = "VALIDATED"
    REVOKED = "REVOKED"


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
    ("ATTACHMENT", "one_handed_blade_v2_full_source_frame/weapon_02"): Capability(
        "ATTACHMENT", "one_handed_blade_v2_full_source_frame/weapon_02", CapabilityStatus.REVOKED,
        "human review found the native weapon_02 forward direction reversed"),
    ("ATTACHMENT", "one_handed_blade_v3_source_frame_forward_corrected/weapon_02"): Capability(
        "ATTACHMENT", "one_handed_blade_v3_source_frame_forward_corrected/weapon_02",
        CapabilityStatus.VALIDATED,
        "v2 grip plus versioned weapon_02 handle-to-tip forward convention correction"),
    ("ATTACHMENT", "shield/weapon_03"): Capability("ATTACHMENT", "shield/weapon_03",
                                                    CapabilityStatus.VALIDATED, "source socket and RMV pivot"),
    ("ATTACHMENT", "javelin/weapon_05"): Capability("ATTACHMENT", "javelin/weapon_05",
                                                    CapabilityStatus.VALIDATED, "source socket and RMV pivot"),
    ("RENDER", "infantry_static_review_v1"): Capability(
        "RENDER", "infantry_static_review_v1", CapabilityStatus.VALIDATED,
        "approved Hastati oracle camera and captured runtime presentation"),
    **{("ANIMATION", key): Capability("ANIMATION", key, CapabilityStatus.VALIDATED, evidence)
       for key, evidence in {
           "discovery.fragment_state": "Rome II animation fragment state/path provenance",
           "export.asset_editor_native": "real RmvToGltfExporter runner",
           "action_preservation": "pre/post native Action fingerprints",
           "preview.contact_sheet": "nine-sample one-direction cached preview",
           "idle.native": "native Action; no locomotion container",
           "walk.external_centering": "outer horizontal container; joint curves unchanged",
           "attack.native_motion": "native Action and motion preserved",
           "death.native_fall": "native vertical fall and carrier animation preserved",
           "animated_weighted_geometry.asset_editor_native_basis": "Principes three-component/two-clip native rest-basis proof",
       }.items()},
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


def conversion_capabilities(
        materials: Iterable[str],
        blade_capability: str = "one_handed_blade_v3_source_frame_forward_corrected",
) -> dict[str, list[dict[str, str]]]:
    required = {
        "MATERIAL": list(materials),
        "ATTACHMENT": ["crest_centre", f"{blade_capability}/weapon_02",
                       "shield/weapon_03", "javelin/weapon_05"],
        "RENDER": ["infantry_static_review_v1"],
    }
    return {category: [{"key": item.key, "status": item.status.value, "evidence": item.evidence}
                       for item in require_capabilities(category, keys)]
            for category, keys in required.items()}
