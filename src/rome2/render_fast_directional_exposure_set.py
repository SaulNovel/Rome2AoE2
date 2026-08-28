"""Render all native source frames at x2 with frozen directional HDR gains."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--gain-receipt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--category',action='append',dest='categories');a=p.parse_args();inputs=json.loads(a.inputs.read_text());receipt=json.loads(a.gain_receipt.read_text());blender=Path(r'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe');reports={}
 selected=set(a.categories or inputs['actions'])
 for category,item in inputs['actions'].items():
  if category not in selected:continue
  record=item['record'];root=a.output/category;report=root/'render-report.json';cmd=[str(blender),'--background','--python',str(ROOT/'src/blender/render_manifest_native_production.py'),'--','--input-blend',item['blend'],'--static-input',inputs['static_input'],'--output-root',str(root),'--report',str(report),'--category',category,'--manifest-hash',inputs['manifest_hash'],'--profile-name',inputs['profile'],'--render-mode','fast','--fast-all-source-samples','--looping',str(int(record['looping'])),'--animation-asset',record['resolved_asset'],'--source-samples',str(record['frame_count']),'--source-fps',str(record['fps']),'--action-fingerprint',item['fingerprint'],'--direction-gains-json',str(a.gain_receipt),'--diagnostic-identity',receipt['identity']];result=subprocess.run(cmd)
  if result.returncode:raise SystemExit(result.returncode)
  reports[category]=str(report)
 summary={'format':'rome2aoe2.fast-directional-exposure-render-set','version':1,'identity':receipt['identity'],'release_eligible':False,'gain_receipt':str(a.gain_receipt),'reports':reports};a.output.mkdir(parents=True,exist_ok=True);(a.output/'render-set-report.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
