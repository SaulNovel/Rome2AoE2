"""Transactional graphics-only refresh for compatible AoE2 dev integrations."""
from __future__ import annotations
import hashlib, shutil, uuid
from pathlib import Path
from typing import Any

class IntegrationCompatibilityError(RuntimeError):
    def __init__(self, reason: str, message: str, **context: Any):
        self.reason,self.context=reason,context
        detail=" ".join(f"{key}={value!r}" for key,value in sorted(context.items()))
        super().__init__(f"{reason}: {message}"+(f" ({detail})" if detail else ""))
    def as_dict(self):return {"reason":self.reason,"message":str(self),"context":self.context}

def sha256(path: Path) -> str:
    digest=hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda:source.read(1024*1024),b""):digest.update(block)
    return digest.hexdigest()

def validate_existing_integration(manifest: dict, integration_profile: dict,
                                  allocation: dict, unit: Any,
                                  graphics: dict[str,Any], scenario_counts: dict[str,int]) -> dict:
    expected_ids=allocation["graphic_ids"]
    actual={"idle":unit.standing_sprite_id1,"walk":unit.walking_graphic_id,
            "attack":unit.attack_graphic_id,"death":unit.dying_sprite_id}
    if actual!=expected_ids or unit.standing_sprite_id2!=expected_ids["idle"]:
        raise IntegrationCompatibilityError("INTEGRATION_MAPPING_MISMATCH","unit graphic mappings differ",expected=expected_ids,actual=actual,standing2=unit.standing_sprite_id2)
    if unit.dead_unit_id!=integration_profile["expected_template_corpse_unit_id"]:
        raise IntegrationCompatibilityError("INTEGRATION_CORPSE_MISMATCH","corpse mapping differs",expected=integration_profile["expected_template_corpse_unit_id"],actual=unit.dead_unit_id)
    for category,row in manifest["animations"].items():
        graphic=graphics[category]
        if graphic.id!=expected_ids[category]:
            raise IntegrationCompatibilityError("INTEGRATION_GRAPHIC_ID_MISMATCH","graphic ID differs",category=category,expected=expected_ids[category],actual=graphic.id)
        if graphic.frame_count!=row["frame_count"] or graphic.angle_count!=16:
            raise IntegrationCompatibilityError("INTEGRATION_FRAME_MISMATCH","graphic frame/facet inventory differs",category=category,expected_frames=row["frame_count"],actual_frames=graphic.frame_count,expected_facets=16,actual_facets=graphic.angle_count)
        expected_duration=1/row["fps"]
        if abs(graphic.frame_duration-expected_duration)>1e-7:
            raise IntegrationCompatibilityError("INTEGRATION_TIMING_MISMATCH","graphic frame duration differs",category=category,expected=expected_duration,actual=graphic.frame_duration)
    expected_counts={str(player):integration_profile["scenario"]["units_per_player"] for player in range(1,integration_profile["scenario"]["players"]+1)}
    if scenario_counts!=expected_counts:
        raise IntegrationCompatibilityError("INTEGRATION_SCENARIO_MISMATCH","scenario unit counts differ",expected=expected_counts,actual=scenario_counts)
    return {"unit_id":allocation["unit_id"],"graphic_ids":actual,"corpse_unit_id":unit.dead_unit_id,"scenario_counts":scenario_counts}

def transactional_replace_assets(assets: list[dict[str,Any]]) -> list[dict[str,Any]]:
    if len(assets)!=8 or len({str(Path(item["destination"]).resolve()) for item in assets})!=8:
        raise IntegrationCompatibilityError("INTEGRATION_ASSET_SET_INVALID","asset refresh requires eight unique destinations",count=len(assets))
    for item in assets:
        source=Path(item["source"])
        if not source.is_file():raise IntegrationCompatibilityError("INTEGRATION_SLD_MISSING","approved SLD is missing",path=str(source))
        actual=sha256(source)
        if actual!=item["sha256"]:raise IntegrationCompatibilityError("INTEGRATION_SLD_HASH_MISMATCH","approved SLD hash differs",path=str(source),expected=item["sha256"],actual=actual)
    parent=Path(assets[0]["destination"]).parent;parent.mkdir(parents=True,exist_ok=True)
    stage=parent.parent/f".rome2aoe2-assets-{uuid.uuid4().hex}";stage.mkdir(parents=True);prepared=[]
    try:
        for index,item in enumerate(assets):
            candidate=stage/f"{index:02d}.sld";shutil.copy2(item["source"],candidate)
            if sha256(candidate)!=item["sha256"]:raise IntegrationCompatibilityError("INTEGRATION_STAGE_HASH_MISMATCH","staged SLD hash differs",path=str(candidate))
            prepared.append((candidate,item))
        for candidate,item in prepared:
            destination=Path(item["destination"]);destination.parent.mkdir(parents=True,exist_ok=True);candidate.replace(destination)
    finally:
        shutil.rmtree(stage,ignore_errors=True)
    result=[]
    for item in assets:
        destination=Path(item["destination"]);actual=sha256(destination)
        if actual!=item["sha256"]:raise IntegrationCompatibilityError("INTEGRATION_INSTALLED_HASH_MISMATCH","installed SLD hash differs",path=str(destination))
        result.append({**item,"installed_sha256":actual,"match":True})
    return result
