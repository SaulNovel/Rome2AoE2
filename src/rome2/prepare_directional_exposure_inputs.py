"""Resolve native action blends/static input for the frozen exposure test."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from rome2aoe2.conversion import DEFAULT_BLENDER,load_and_validate_manifest
from rome2aoe2.native_assembly import assemble_native,static_assembly_identity
from rome2aoe2.production import frozen_candidate,resolve_production_profile
def main():
 p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();request=load_and_validate_manifest(a.manifest);profile=resolve_production_profile('aoe2-infantry-animation-production-v5-equipment-readability');blade=profile['attachment_capabilities']['one_handed_blade/weapon_02'];static=ROOT/'build/conversions'/request.unit.definition.main_unit.casefold()/static_assembly_identity(request.manifest,blade)/'static-assembly-input.json';actions={}
 for category in ('idle','walk','attack','death'):
  record=request.manifest['animations'][category];blend,assembly=assemble_native(request.manifest,frozen_candidate(category,record),DEFAULT_BLENDER,blade);actions[category]={'blend':str(blend),'record':record,'fingerprint':assembly['action_fingerprint_before']}
 result={'manifest':str(a.manifest),'manifest_hash':request.manifest_hash,'profile':profile['name'],'static_input':str(static),'actions':actions};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(a.output)
if __name__=='__main__':main()
