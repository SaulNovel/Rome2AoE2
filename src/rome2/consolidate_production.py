"""Create validated, profile-generic consolidated production reports."""
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from rome2aoe2.conversion import load_and_validate_manifest
from rome2aoe2.production_reports import CATEGORIES,write_consolidated_category
def main():
 parser=argparse.ArgumentParser();parser.add_argument("manifest",type=Path);parser.add_argument("--production-profile",required=True);parser.add_argument("--expected-manifest-hash");args=parser.parse_args();request=load_and_validate_manifest(args.manifest)
 if args.expected_manifest_hash and request.manifest_hash!=args.expected_manifest_hash:raise RuntimeError(f"manifest identity mismatch: {request.manifest_hash}")
 paths={category:str(write_consolidated_category(request,category,args.production_profile)) for category in CATEGORIES};print(json.dumps(paths,indent=2,sort_keys=True))
if __name__=="__main__":main()
