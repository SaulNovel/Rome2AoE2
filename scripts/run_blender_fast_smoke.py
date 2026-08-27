"""Launch and structurally validate the offline Blender FAST smoke."""
from __future__ import annotations
import os, subprocess, sys
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
def main():
    blender=Path(os.environ.get("ROME2AOE2_BLENDER",r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"))
    fixture=ROOT/"data/local-fixtures";output=ROOT/"build/smoke/principes-fast-x2.png"
    command=[str(blender),"--background","--python",str(ROOT/"scripts/blender_fast_smoke.py"),"--","--fixture-root",str(fixture),"--output",str(output)]
    result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
    if result.returncode: print(result.stdout[-2000:]);print(result.stderr[-2000:]);return result.returncode
    with Image.open(output) as image:
        image.load();alpha=image.getchannel("A");bounds=alpha.getbbox()
        if image.size!=(400,400) or image.mode!="RGBA" or bounds is None: print(f"FAIL image={image.size}/{image.mode} bounds={bounds}");return 1
    print(f"PASS Blender FAST Principes 400x400 RGBA bounds={bounds} output={output}")
    return 0
if __name__=="__main__":raise SystemExit(main())
