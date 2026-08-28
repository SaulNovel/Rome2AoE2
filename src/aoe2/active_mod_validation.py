"""Prove which enabled AoE2 mod supplies the game-facing DAT."""
from __future__ import annotations
import json
from pathlib import Path
from aoe2.dat_integration import sha256

def _normalized(value):return str(value or '').replace('\\','/').replace('//','/').strip('/').casefold()
def _entry_root(mods_root:Path,status_path:str):
 parts=str(status_path).replace('\\','/').split('//',1)
 if len(parts)!=2:return None
 return mods_root/parts[0]/parts[1]
def audit_active_dat(status_file:Path,mods_root:Path,target_title:str,target_status_path:str,expected_sha256:str):
 document=json.loads(Path(status_file).read_text());target_normalized=_normalized(target_status_path);rows=[];candidates=[];all_data_candidates=[];target=None
 for entry in document.get('Mods',[]):
  root=_entry_root(Path(mods_root),entry.get('Path',''));dat=root/'resources/_common/dat/empires2_x2_p1.dat' if root else None;exists=bool(dat and dat.is_file());record={'title':entry.get('Title'),'path':entry.get('Path'),'priority':entry.get('Priority'),'enabled':bool(entry.get('Enabled')),'folder':str(root) if root else None,'folder_exists':bool(root and root.is_dir()),'dat_path':str(dat) if dat else None,'dat_exists':exists,'dat_sha256':sha256(dat) if exists else None};rows.append(record)
  if _normalized(entry.get('Path'))==target_normalized:target=record
  if record['enabled'] and exists:
   all_data_candidates.append(record)
   if _normalized(entry.get('Path')).startswith('local/rome2aoe2'):candidates.append(record)
 if target is None:raise RuntimeError(f'target mod path absent from mod-status.json: {target_status_path}')
 if target['title']!=target_title or not target['enabled']:raise RuntimeError('target data mod is not enabled under its intended title')
 if target['dat_sha256']!=expected_sha256:raise RuntimeError('enabled target DAT hash mismatch')
 # AoE2 lists lower numeric Priority first. Requiring one enabled Rome2AoE2
 # DAT removes any dependence on undocumented cross-data-mod merge behavior.
 if len(candidates)!=1 or candidates[0]['path']!=target['path']:raise RuntimeError(f'active Rome2AoE2 DAT is ambiguous: {[r["path"] for r in candidates]}')
 if len(all_data_candidates)!=1 or all_data_candidates[0]['path']!=target['path']:raise RuntimeError(f'active DAT precedence is ambiguous across enabled mods: {[r["path"] for r in all_data_candidates]}')
 rome_rows=[row for row in rows if _normalized(row['path']).startswith('local/rome2aoe2')]
 return {'status_file':str(status_file),'target_title':target_title,'target_status_path':target_status_path,'rome2aoe2_mods':rome_rows,'enabled_rome2aoe2_data_mods':candidates,'enabled_data_mods':all_data_candidates,'dat_precedence':'target is the sole enabled mod containing resources/_common/dat/empires2_x2_p1.dat; target wins unambiguously','active_dat':target}
