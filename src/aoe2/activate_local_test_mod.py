"""Atomically activate one local dev data mod and disable explicit conflicts."""
from __future__ import annotations
import argparse,json,os,tempfile
from pathlib import Path
def _normalized(value):return str(value or '').replace('\\','/').replace('//','/').casefold()
def activate(status_path:Path,target_title:str,conflicts=(),target_path=None,disable_local_prefix=None):
 document=json.loads(status_path.read_text());found=False;changed=[];conflicts=set(conflicts);target_path_normalized=_normalized(target_path);prefix=_normalized(disable_local_prefix)
 for mod in document.get("Mods",[]):
  title=mod.get("Title");path=_normalized(mod.get("Path"));is_target=title==target_title or bool(target_path_normalized and path==target_path_normalized);is_prefixed_conflict=bool(prefix and path.startswith('local/'+prefix) and not is_target);desired=True if is_target else (False if title in conflicts or is_prefixed_conflict else mod.get("Enabled",False))
  if is_target:
   found=True
   if title!=target_title:mod["Title"]=target_title;changed.append({"path":mod.get("Path"),"old_title":title,"title":target_title})
  if mod.get("Enabled")!=desired:mod["Enabled"]=desired;changed.append({"title":mod.get("Title"),"path":mod.get("Path"),"enabled":desired})
 if not found:raise RuntimeError(f"installed local mod is absent from mod-status.json: {target_title}")
 fd,name=tempfile.mkstemp(prefix="mod-status-",suffix=".json",dir=status_path.parent);os.close(fd);temporary=Path(name)
 try:temporary.write_text(json.dumps(document,separators=(",",":")));os.replace(temporary,status_path)
 finally:
  if temporary.exists():temporary.unlink()
 return {"target":target_title,"target_path":target_path,"enabled":True,"conflicts_disabled":sorted(conflicts),"disabled_local_prefix":disable_local_prefix,"changes":changed}
def main():
 p=argparse.ArgumentParser();p.add_argument("--status",type=Path,required=True);p.add_argument("--target",required=True);p.add_argument("--target-path");p.add_argument("--disable",action="append",default=[]);p.add_argument("--disable-local-prefix");a=p.parse_args();print(json.dumps(activate(a.status,a.target,a.disable,a.target_path,a.disable_local_prefix),indent=2))
if __name__=="__main__":main()
