"""Generic AoE2 DAT integration from frozen manifest and SLD production data."""
from __future__ import annotations
import hashlib,json,re,shutil
from pathlib import Path

CATEGORIES=("idle","walk","attack","death")
LIVE_GRAPHIC_FIELDS={
 "standing_sprite_id1":"idle","standing_sprite_id2":"idle","walking_graphic_id":"walk",
 "running_graphic_id":"walk","attack_graphic_id":"attack","attack_graphic2":"attack",
 "dying_sprite_id":"death","undead_sprite_id":"death",
}
TASK_GRAPHIC_FIELDS=("move_sprite_id","proceed_sprite_id","work_sprite_id","carry_sprite_id")
RUNTIME_FIELDS=("force_player_color","layer","color_table","transparent_selection","speed_mult","replay_delay","sequence_type","mirroring_mode")

def sha256(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def slug(value):return re.sub(r"[^a-z0-9]+","_",value.casefold()).strip("_")
def allocation_key(manifest_hash,profile_id):return f"{manifest_hash}:{profile_id}"
def occupied_allocations(registry,exclude_key=None):
 units=set();graphics=set()
 for key,value in registry["allocations"].items():
  if key==exclude_key:continue
  units.add(value["unit_id"]);graphics.update(value["graphic_ids"].values())
  if "corpse_unit_id" in value:units.add(value["corpse_unit_id"])
  if "corpse_graphic_id" in value:graphics.add(value["corpse_graphic_id"])
 return units,graphics
def first_free(start,occupied,count=1):
 candidate=start
 while True:
  values=tuple(range(candidate,candidate+count))
  if not any(value in occupied for value in values):return values
  candidate+=1
def resolve_allocation(workspace,registry,manifest_hash,profile_id,corpse_policy="inherit_template"):
 key=allocation_key(manifest_hash,profile_id);reserved_units,reserved_graphics=occupied_allocations(registry,key)
 source_units={index for index in range(len(workspace.dat.civilizations[0].units)) if workspace.unit_manager.exists(index)}
 source_graphics={index for index in range(len(workspace.dat.sprites)) if workspace.graphic_manager.exists(index)}
 existing=registry["allocations"].get(key)
 if existing:
  unit_id=existing["unit_id"];graphic_ids=existing["graphic_ids"]
 else:
  unit_id=first_free(registry["unit_search_start"],source_units|reserved_units)[0]
  values=first_free(registry["graphic_search_start"],source_graphics|reserved_graphics,4);graphic_ids=dict(zip(CATEGORIES,values))
 for category in CATEGORIES:
  graphic_id=graphic_ids[category]
  if graphic_id in source_graphics or graphic_id in reserved_graphics:raise ValueError(f"graphic allocation collision: {category}={graphic_id}")
 if unit_id in source_units or unit_id in reserved_units:raise ValueError(f"unit allocation collision: {unit_id}")
 if len(set(graphic_ids.values()))!=4:raise ValueError("graphic allocation contains duplicates")
 result={"key":key,"unit_id":unit_id,"graphic_ids":graphic_ids}
 if corpse_policy=="generated_corpse_decay_v1":
  used_units=source_units|reserved_units|{unit_id};used_graphics=source_graphics|reserved_graphics|set(graphic_ids.values())
  result["corpse_unit_id"]=existing.get("corpse_unit_id") if existing and "corpse_unit_id" in existing else first_free(registry["unit_search_start"],used_units)[0]
  result["corpse_graphic_id"]=existing.get("corpse_graphic_id") if existing and "corpse_graphic_id" in existing else first_free(registry["graphic_search_start"],used_graphics)[0]
 return result
def resolve_corpse_allocation(workspace,registry,allocation):
 """Extend an existing live allocation without treating its installed IDs as collisions."""
 source_units={index for index in range(len(workspace.dat.civilizations[0].units)) if workspace.unit_manager.exists(index)}
 source_graphics={index for index in range(len(workspace.dat.sprites)) if workspace.graphic_manager.exists(index)}
 reserved_units,reserved_graphics=occupied_allocations(registry,allocation["key"])
 return {**allocation,"corpse_unit_id":first_free(registry["unit_search_start"],source_units|reserved_units|{allocation["unit_id"]})[0],"corpse_graphic_id":first_free(registry["graphic_search_start"],source_graphics|reserved_graphics|set(allocation["graphic_ids"].values()))[0]}
def apply_generated_corpse_contract(live_unit,corpse_unit,corpse_graphic_id):
 live_unit.dead_unit_id=corpse_unit.id
 corpse_unit.standing_sprite_id1=corpse_graphic_id;corpse_unit.standing_sprite_id2=-1;corpse_unit.dead_unit_id=-1
 for field in ("walking_graphic_id","running_graphic_id","attack_graphic_id","attack_graphic2","dying_sprite_id","undead_sprite_id"):
  if hasattr(corpse_unit,field):setattr(corpse_unit,field,-1)
 return {"live_dead_unit_id":live_unit.dead_unit_id,"corpse_unit_id":corpse_unit.id,"corpse_graphic_id":corpse_graphic_id}
def validate_generated_corpse_contract(live_unit,corpse_unit,corpse_graphic_id,forbidden_graphics=()):
 reachable=reachable_graphics(corpse_unit);values=set(reachable.values())
 if values!={corpse_graphic_id}:raise RuntimeError(f"generated corpse visual contract invalid: {reachable}")
 retained=values&set(forbidden_graphics)
 if retained:raise RuntimeError(f"inherited corpse graphics remain reachable: {sorted(retained)}")
 if _get(live_unit,"dead_unit_id")!=corpse_unit.id:raise RuntimeError("live dead_unit_id does not select generated corpse")
 return {"reachable":reachable,"retained":sorted(retained)}
def category_stem(unit,category):return f"rome2aoe2_{slug(unit)}_{category}"
def reference_graphic_id(template,category):
 return {"idle":template.standing_sprite_id1,"walk":template.walking_graphic_id,"attack":template.attack_graphic_id,"death":template.dying_sprite_id}[category]
def _get(unit,field):
 try:return getattr(unit,field)
 except (AttributeError,TypeError):return -1
def apply_visual_contract(unit,graphic_ids):
 """Replace every reachable live sprite selector on a cloned gameplay unit."""
 for field,category in LIVE_GRAPHIC_FIELDS.items():
  if field in {"running_graphic_id","attack_graphic2","undead_sprite_id"} and _get(unit,field)<0:continue
  setattr(unit,field,graphic_ids[category])
 raw=getattr(unit,"_unit",unit);task_info=getattr(raw,"task_info",None)
 if task_info:
  for task in task_info.tasks:
   for field in TASK_GRAPHIC_FIELDS:
    value=getattr(task,field)
    if value>=0:setattr(task,field,graphic_ids["attack"] if field=="work_sprite_id" else graphic_ids["walk"])
def reachable_graphics(unit,include_dead=False):
 result={field:_get(unit,field) for field in LIVE_GRAPHIC_FIELDS if _get(unit,field)>=0}
 raw=getattr(unit,"_unit",unit);task_info=getattr(raw,"task_info",None)
 if task_info:
  for index,task in enumerate(task_info.tasks):
   for field in TASK_GRAPHIC_FIELDS:
    value=getattr(task,field)
    if value>=0:result[f"task[{index}].{field}"]=value
 if include_dead and _get(unit,"dead_unit_id")>=0:result["dead_unit_id"]=_get(unit,"dead_unit_id")
 return result
def validate_visual_contract(unit,template,graphic_ids,allowed_template_graphics=()):
 reachable=reachable_graphics(unit);forbidden=set(reachable_graphics(template).values())-set(allowed_template_graphics)
 retained={field:value for field,value in reachable.items() if value in forbidden}
 if retained:raise RuntimeError(f"reachable source-template graphics remain: {retained}")
 expected=set(graphic_ids.values())
 unexpected={field:value for field,value in reachable.items() if value not in expected}
 if unexpected:raise RuntimeError(f"reachable graphics outside generated visual contract: {unexpected}")
 return {"reachable":reachable,"forbidden_template_graphics":sorted(forbidden),"retained":retained}
def clone_graphic(workspace,reference,graphic_id,stem,name,frames,fps):
 return workspace.graphic_manager.add_graphic(stem,name=name,graphic_id=graphic_id,frame_count=frames,angle_count=16,frame_duration=1/fps,old_color_flag=reference.force_player_color,layer=reference.layer,force_player_color=reference.color_table,transparent_selection=reference.transparent_selection,speed_multiplier=reference.speed_mult,replay_delay=reference.replay_delay,sequence_type=reference.sequence_type,mirroring_mode=reference.mirroring_mode)
def expected_sld_paths(sld_root,unit,category):
 return {scale:Path(sld_root)/category/f"{slug(unit)}-{category}_{scale}.sld" for scale in ("x1","x2")}
def install_slds(sld_root,graphics_root,unit):
 assets=[];graphics_root.mkdir(parents=True,exist_ok=True)
 for category in CATEGORIES:
  stem=category_stem(unit,category)
  for scale,source in expected_sld_paths(sld_root,unit,category).items():
   if not source.is_file():raise FileNotFoundError(f"missing approved SLD: {source}")
   destination=graphics_root/f"{stem}_{scale}.sld";shutil.copy2(source,destination)
   if sha256(source)!=sha256(destination):raise RuntimeError(f"installed SLD hash mismatch: {category}/{scale}")
   assets.append({"category":category,"scale":scale,"source":str(source),"installed":str(destination),"sha256":sha256(destination)})
 return assets
