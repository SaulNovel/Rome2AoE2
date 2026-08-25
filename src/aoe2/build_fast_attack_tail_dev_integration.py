"""Build an isolated FAST attack-tail test from an approved corpse integration."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'third_party/python-deps')]
from aoe2_genie_tooling import GenieWorkspace
from aoe2.dat_integration import sha256,validate_generated_corpse_contract
from aoe2.scenario_validation import validate_scenario
from aoe2.sld import parse_sld
def same_visual_frame(left,right):
 import copy
 left=copy.deepcopy(left);right=copy.deepcopy(right);left.frame_index=right.frame_index=0;return left==right
def main():
 p=argparse.ArgumentParser();p.add_argument('--base-receipt',type=Path,required=True);p.add_argument('--attack-report',type=Path,required=True);a=p.parse_args();base=json.loads(a.base_receipt.read_text());attack=json.loads(a.attack_report.read_text())
 if base['format']!='rome2aoe2.fast-corpse-dev-integration' or attack['format']!='rome2aoe2.fast-attack-tail-hold' or attack['release_eligible'] is not False:raise RuntimeError('FAST integration evidence mismatch')
 source_mod=Path(base['mod']);source_scenario=Path(base['scenario']);prototype=Path(attack['output_sld']);identity=attack['output_sha256'][:16];root=a.base_receipt.parents[2]/'fast-attack-tail'/identity;mod=root/source_mod.name;scenario=root/source_scenario.name
 if mod.exists():raise FileExistsError(f'refusing to overwrite dev test: {mod}')
 root.mkdir(parents=True,exist_ok=True);shutil.copytree(source_mod,mod);shutil.copy2(source_scenario,scenario);graphics=mod/'resources/_common/drs/graphics';dat=mod/'resources/_common/dat/empires2_x2_p1.dat';workspace=GenieWorkspace.load(dat);allocation=base['allocation'];unit=workspace.unit_manager.get(allocation['unit_id']);graphic=workspace.graphic_manager.get(allocation['graphic_ids']['attack']);stem=graphic.file_name[:-3] if graphic.file_name.endswith('_x1') else graphic.file_name;attack_dest=graphics/f'{stem}_x2.sld';shutil.copy2(prototype,attack_dest)
 before={'reload_time':unit.reload_time,'frame_delay':unit.frame_delay,'interrupt_frame':unit.interrupt_frame,'idle_attack_graphic_id':unit.idle_attack_graphic_id,'sequence_type':workspace.dat.sprites[graphic.id].sequence_type}
 if abs(before['reload_time']-attack['reload_time'])>1e-7:raise RuntimeError(f'attack report reload does not match DAT: {before}')
 graphic.frame_count=attack['extended_frames_per_direction'];graphic.frame_duration=attack['frame_duration'];workspace.save(dat);written=GenieWorkspace.load(dat);u=written.unit_manager.get(allocation['unit_id']);g=written.graphic_manager.get(allocation['graphic_ids']['attack']);corpse=written.unit_manager.get(allocation['corpse_unit_id']);corpse_graphic=written.graphic_manager.get(allocation['corpse_graphic_id']);runtime={'reload_time':u.reload_time,'frame_delay':u.frame_delay,'interrupt_frame':u.interrupt_frame,'idle_attack_graphic_id':u.idle_attack_graphic_id,'sequence_type':written.dat.sprites[g.id].sequence_type}
 if runtime!=before or (g.frame_count,g.angle_count)!=(attack['extended_frames_per_direction'],attack['directions']) or abs(g.frame_duration-attack['frame_duration'])>1e-7:raise RuntimeError('attack DAT roundtrip mismatch')
 corpse_contract=validate_generated_corpse_contract(u,corpse,allocation['corpse_graphic_id'],(base['profile']['expected_template_corpse_graphic_id'],))
 base_corpse=base['corpse_graphic']
 if (corpse_graphic.frame_count,corpse_graphic.angle_count)!=(base_corpse['frame_count'],base_corpse['angle_count']) or abs(corpse_graphic.frame_duration-base_corpse['frame_duration'])>1e-7:raise RuntimeError('approved corpse metadata changed')
 source_count=attack['source_frames_per_direction'];target_count=attack['extended_frames_per_direction'];facets=attack['directions'];hold=attack['hold_source_ordinal'];source=parse_sld(Path(attack['source_sld']).read_bytes());extended=parse_sld(attack_dest.read_bytes());prefix=all(same_visual_frame(extended.frames[d*target_count+i],source.frames[d*source_count+i]) for d in range(facets) for i in range(source_count));held=all(same_visual_frame(extended.frames[d*target_count+i],source.frames[d*source_count+hold]) for d in range(facets) for i in range(source_count,target_count))
 scenario_validation=validate_scenario(scenario,written,(allocation['unit_id'],));scenario_hash=sha256(scenario)
 if scenario_hash!=base['scenario_sha256'] or not prefix or not held:raise RuntimeError('attack/scenario structural validation failed')
 receipt={'format':'rome2aoe2.fast-attack-tail-dev-integration','version':1,'release_eligible':False,'mod':str(mod),'mod_title':base['mod_title'],'conflicting_mod_titles':base['conflicting_mod_titles'],'scenario':str(scenario),'scenario_sha256':scenario_hash,'scenario_validation':scenario_validation,'allocation':allocation,'profile':base['profile'],'dat':{'path':str(dat),'sha256':sha256(dat)},'attack':{'sld':str(attack_dest),'sha256':sha256(attack_dest),'graphic_id':g.id,'frame_count':g.frame_count,'frame_duration':g.frame_duration,'angle_count':g.angle_count,'native_prefix_unchanged':prefix,'held_frames_equal_selected_recovery':held,'hold_source_ordinal':hold,'source_frames':source_count,'held_frames':target_count-source_count},'runtime':runtime,'corpse':{'contract':corpse_contract,'graphic_id':corpse_graphic.id,'frame_count':corpse_graphic.frame_count,'frame_duration':corpse_graphic.frame_duration,'angle_count':corpse_graphic.angle_count,'sld':next(x for x in base['assets'] if 'corpse_x2' in x['path'])},'validation':'passed'};path=root/'fast-attack-tail-integration-receipt.json';path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');print(path)
if __name__=='__main__':main()
