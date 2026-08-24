"""Atomically activate one local dev data mod and disable explicit conflicts."""
from __future__ import annotations
import argparse,json,os,tempfile
from pathlib import Path
def activate(status_path:Path,target_title:str,conflicts=()):
 document=json.loads(status_path.read_text());found=False;changed=[];conflicts=set(conflicts)
 for mod in document.get("Mods",[]):
  title=mod.get("Title");desired=True if title==target_title else (False if title in conflicts else mod.get("Enabled",False))
  if title==target_title:found=True
  if mod.get("Enabled")!=desired:mod["Enabled"]=desired;changed.append({"title":title,"enabled":desired})
 if not found:raise RuntimeError(f"installed local mod is absent from mod-status.json: {target_title}")
 fd,name=tempfile.mkstemp(prefix="mod-status-",suffix=".json",dir=status_path.parent);os.close(fd);temporary=Path(name)
 try:temporary.write_text(json.dumps(document,separators=(",",":")));os.replace(temporary,status_path)
 finally:
  if temporary.exists():temporary.unlink()
 return {"target":target_title,"enabled":True,"conflicts_disabled":sorted(conflicts),"changes":changed}
def main():
 p=argparse.ArgumentParser();p.add_argument("--status",type=Path,required=True);p.add_argument("--target",required=True);p.add_argument("--disable",action="append",default=[]);a=p.parse_args();print(json.dumps(activate(a.status,a.target,a.disable),indent=2))
if __name__=="__main__":main()
