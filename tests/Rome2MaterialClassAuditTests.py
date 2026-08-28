"""Regression checks for reusable anatomical/material validation."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; REPORT=ROOT/"build"/"local-integration"/"rome2"/"material-class-audit"/"anatomical-material-audit.json"
def data(): return json.loads(REPORT.read_text(encoding="utf-8"))
def test_skin_never_conductor():
    d=data(); objects=d["blender_object_audit"]["objects"]
    skin={"roman_1_head","roman_body1"}
    classes={row["material"]:row["current_v4_class"] for obj in objects for row in obj["classes"]}
    assert all(classes[name]=="dielectric" for name in skin)
def test_exposed_limb_evidence_is_explicit():
    regions={r["region"]:r for r in data()["regions"]}
    assert regions["forearms below elbow"]["material"]=="roman_body1" and regions["forearms below elbow"]["result"]=="pass"
    assert regions["hands"]["material"]=="roman_body1" and regions["hands"]["result"]=="pass"
    assert regions["lower legs"]["material"]=="3c_aurelian_pants" and regions["lower legs"]["result"]=="fail"
def test_no_false_variant_replacement():
    variants=data()["trouser_slot_variants"]; assert len(variants)==4
    assert len({v["model"].lower() for v in variants})==1
    assert variants[0]["mask0"] is None and variants[1]["mask0"]=="1" and variants[2]["mask0"]=="2"
def test_mixed_equipment_is_flagged():
    findings=" ".join(data()["blocking_findings"]).lower(); assert "gladius" in findings and "grip" in findings
    assert "pilum" in findings and "wooden shaft" in findings
def test_shield_and_helmet_do_not_spill_to_skin():
    d=data(); objects=d["blender_object_audit"]["objects"]
    mats={o["object"]:o["materials"] for o in objects}
    assert mats["roman_augustan_scutuma_weapon_03_0"]==["augustan_scutum_lod1"]
    assert mats["roman_augustan_scutuma_weapon_03_1"]==["augustan_scutum_bossa_lod1"]
    assert mats["Mesh_0.002"]==["3c_niederbieber_helmet"]
def run_all():
    tests=[test_skin_never_conductor,test_exposed_limb_evidence_is_explicit,test_no_false_variant_replacement,test_mixed_equipment_is_flagged,test_shield_and_helmet_do_not_spill_to_skin]
    for t in tests:t();print(f"ok - {t.__name__}")
    print(f"PASS ({len(tests)} checks)")
if __name__=="__main__":run_all()
