"""Build an isolated FAST lift-only directional exposure integration."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'third_party/python-deps')]
from aoe2_genie_tooling import GenieWorkspace
from aoe2.dat_integration import sha256,validate_generated_corpse_contract
from aoe2.scenario_validation import validate_scenario
from aoe2.sld import parse_sld

TITLE='Rome2AoE2 FAST Directional Dev Test'
TIMING={'idle':(43,1/15),'walk':(23,1/20),'attack':(40,1/20),'death':(33,1/15),'corpse':(54,10.0)}

def main():
 p=argparse.ArgumentParser();p.add_argument('--base-receipt',type=Path,required=True);p.add_argument('--sld-report',type=Path,required=True);p.add_argument('--corpse-report',type=Path,required=True);p.add_argument('--gain-receipt',type=Path,required=True);a=p.parse_args();base=json.loads(a.base_receipt.read_text());slds=json.loads(a.sld_report.read_text());corpse_report=json.loads(a.corpse_report.read_text());gains=json.loads(a.gain_receipt.read_text())
 if base['format']!='rome2aoe2.fast-attack-tail-dev-integration' or gains['identity']!='directional_exposure_lift_only_v1':raise RuntimeError('diagnostic integration evidence mismatch')
 identity=hashlib.sha256((json.dumps(gains,sort_keys=True)+json.dumps({k:v.get('sha256') for k,v in slds.items() if isinstance(v,dict)},sort_keys=True)+corpse_report['corpse']['sha256']).encode()).hexdigest()[:16];root=a.base_receipt.parents[2]/'fast-directional-exposure'/identity;mod=root/TITLE;scenario=root/'Rome2AoE2FASTDirectionalDevTest.aoe2scenario'
 if mod.exists():raise FileExistsError(f'refusing to overwrite dev test: {mod}')
 root.mkdir(parents=True,exist_ok=True);shutil.copytree(Path(base['mod']),mod);shutil.copy2(Path(base['scenario']),scenario);graphics=mod/'resources/_common/drs/graphics';dat=mod/'resources/_common/dat/empires2_x2_p1.dat';(mod/'info.json').write_text(json.dumps({'Author':'Rome2AoE2','CacheStatus':0,'Title':TITLE,'Description':'TEST / NON-PRODUCTION frozen directional-exposure integration; not release eligible.'},indent=2)+'\n')
 assets={}
 for category in ('idle','walk','attack','death'):
  source=Path(slds[category]['path']);dest=graphics/f'rome2aoe2_rom_principes_{category}_x2.sld';shutil.copy2(source,dest);assets[category]={'path':str(dest),'sha256':sha256(dest)}
 corpse_source=Path(corpse_report['corpse']['path']);corpse_dest=graphics/'rome2aoe2_rom_principes_corpse_x2.sld';shutil.copy2(corpse_source,corpse_dest);assets['corpse']={'path':str(corpse_dest),'sha256':sha256(corpse_dest)}
 workspace=GenieWorkspace.load(dat);allocation=base['allocation'];unit=workspace.unit_manager.get(allocation['unit_id']);before={'reload_time':unit.reload_time,'frame_delay':unit.frame_delay,'interrupt_frame':unit.interrupt_frame,'idle_attack_graphic_id':unit.idle_attack_graphic_id}
 for category,(count,duration) in TIMING.items():
  gid=allocation['corpse_graphic_id'] if category=='corpse' else allocation['graphic_ids'][category];graphic=workspace.graphic_manager.get(gid);graphic.frame_count=count;graphic.frame_duration=duration
 workspace.save(dat);written=GenieWorkspace.load(dat);living=written.unit_manager.get(allocation['unit_id']);corpse=written.unit_manager.get(allocation['corpse_unit_id']);runtime={'reload_time':living.reload_time,'frame_delay':living.frame_delay,'interrupt_frame':living.interrupt_frame,'idle_attack_graphic_id':living.idle_attack_graphic_id,'sequence_type':written.dat.sprites[allocation['graphic_ids']['attack']].sequence_type}
 if runtime!={**before,'sequence_type':3}:raise RuntimeError('gameplay attack runtime changed')
 graphic_values={}
 for category,(count,duration) in TIMING.items():
  gid=allocation['corpse_graphic_id'] if category=='corpse' else allocation['graphic_ids'][category];graphic=written.graphic_manager.get(gid);graphic_values[category]={'graphic_id':gid,'frame_count':graphic.frame_count,'frame_duration':graphic.frame_duration,'angle_count':graphic.angle_count}
  if (graphic.frame_count,graphic.angle_count)!=(count,16) or abs(graphic.frame_duration-duration)>1e-6:raise RuntimeError(f'{category} DAT roundtrip mismatch')
 contract=validate_generated_corpse_contract(living,corpse,allocation['corpse_graphic_id'],(base['profile']['expected_template_corpse_graphic_id'],));scenario_validation=validate_scenario(scenario,written,(allocation['unit_id'],));scenario_hash=sha256(scenario)
 if scenario_hash!=base['scenario_sha256']:raise RuntimeError('scenario changed')
 for category,record in assets.items():
  doc=parse_sld(Path(record['path']).read_bytes());record['version']=doc.version;record['total_frames']=len(doc.frames);record['parser_readback']=doc.version==4 and len(doc.frames)==16*TIMING[category][0]
  if not record['parser_readback']:raise RuntimeError(f'{category} SLD readback failed')
 receipt={'format':'rome2aoe2.fast-directional-exposure-dev-integration','version':1,'identity':gains['identity'],'release_eligible':False,'mod':str(mod),'mod_title':TITLE,'conflicting_mod_titles':[base['mod_title'],*base['conflicting_mod_titles']],'scenario':str(scenario),'scenario_sha256':scenario_hash,'scenario_validation':scenario_validation,'allocation':allocation,'profile':base['profile'],'gain_receipt':str(a.gain_receipt),'gains':gains['gains'],'dat':{'path':str(dat),'sha256':sha256(dat)},'graphics':graphic_values,'assets':assets,'runtime':runtime,'corpse_contract':contract,'corpse_validation':corpse_report['validation'],'validation':'passed'};path=root/'fast-directional-exposure-integration-receipt.json';path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');print(path)
if __name__=='__main__':main()
