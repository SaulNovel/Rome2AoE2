import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
HELPER=Path(os.environ.get('ROME2AOE2_PACK_HELPER',ROOT/'tools/rome2_pack/target/release/rome2aoe2-pack.exe'))

class Rome2AssetExtractionTests(unittest.TestCase):
 def setUp(self):
  if not HELPER.is_file(): self.skipTest('rome2aoe2-pack release helper unavailable')
  self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
 def tearDown(self): self.temp.cleanup()
 def pack(self,name,files):
  spec=self.root/(name+'.json'); out=self.root/(name+'.pack'); spec.write_text(json.dumps({'format':'rome2aoe2.test-pack-spec','version':1,'files':[{'path':p,'content_utf8':c} for p,c in files.items()]}))
  subprocess.run([HELPER,'create-test-pack','--spec',spec,'--output',out],check=True,capture_output=True,text=True); return out
 def extract_manifest(self,deps,packs,version=2):
  source=self.root/'dependency.json'; output=self.root/'nested'/'manifest.json'; source.write_text(json.dumps({'format_version':version,'dependencies':deps}))
  cmd=[sys.executable,'-B',ROOT/'src/rome2/extract_dependency_manifest.py','--manifest',source,'--helper',HELPER,'--output-root',self.root/'out','--extraction-manifest',output]
  for pack in packs: cmd.extend(['--pack',pack])
  result=subprocess.run(cmd,capture_output=True,text=True); return result,json.loads(output.read_text()) if output.exists() else None
 def dep(self,path,types=['model'],origins=[]): return {'path':path,'normalized_path':path.replace('\\','/').casefold(),'asset_types':types,'origins':origins}
 def test_successful_model_extraction(self):
  pack=self.pack('one',{'Models/A.rigid_model_v2':'A'}); result,m=self.extract_manifest([self.dep('Models/A.rigid_model_v2')],[pack]); self.assertEqual(result.returncode,0); self.assertEqual(m['status'],'success'); self.assertEqual(m['assets'][0]['path'],'Models/A.rigid_model_v2')
 def test_multiple_assets_and_output_hierarchy(self):
  pack=self.pack('one',{'Models/A.rigid_model_v2':'A','Models/B.rigid_model_v2':'B'}); result,m=self.extract_manifest([self.dep('Models/A.rigid_model_v2'),self.dep('Models/B.rigid_model_v2')],[pack]); self.assertEqual(result.returncode,0); self.assertEqual(len(m['assets']),2); self.assertTrue((self.root/'out/Models/A.rigid_model_v2').is_file())
 def test_precedence_shadowed_and_case_normalization(self):
  first=self.pack('first',{'Models/Case.RIGID_MODEL_V2':'first'}); second=self.pack('second',{'models/case.rigid_model_v2':'second'}); result,m=self.extract_manifest([self.dep('models\\case.rigid_model_v2')],[first,second]); self.assertEqual(result.returncode,0); self.assertEqual(m['assets'][0]['pack'],'first.pack'); self.assertEqual(m['assets'][0]['shadowed_packs'],['second.pack']); self.assertEqual(m['assets'][0]['matched_path'],'Models/Case.RIGID_MODEL_V2')
 def test_missing_partial_failure_and_manifest_creation(self):
  pack=self.pack('one',{'Models/A.rigid_model_v2':'A'}); result,m=self.extract_manifest([self.dep('Models/A.rigid_model_v2'),self.dep('Models/Missing.rigid_model_v2')],[pack]); self.assertEqual(result.returncode,1); self.assertEqual(m['status'],'failed'); self.assertEqual(m['missing'][0]['failure_kind'],'not-found')
 def test_skipped_and_origins_preserved(self):
  origins=[{'attribute':'model','definition':'root','slot_path':'a','reference_chain':['root']}]; pack=self.pack('one',{'Models/A.rigid_model_v2':'A'}); result,m=self.extract_manifest([self.dep('Models/A.rigid_model_v2',origins=origins),self.dep('odd.file',['unknown'])],[pack]); self.assertEqual(result.returncode,0); self.assertEqual(m['status'],'success-with-skips'); self.assertEqual(m['assets'][0]['origins'],origins); self.assertEqual(len(m['skipped']),1)
 def test_version_2_manifest_keeps_missing_attach_point_unavailable(self):
  origins=[{'attribute':'model','definition':'root','slot_path':'weapon_2','reference_chain':['root']}]; pack=self.pack('one',{'Models/A.rigid_model_v2':'A'}); result,m=self.extract_manifest([self.dep('Models/A.rigid_model_v2',origins=origins)],[pack],version=2); self.assertEqual(result.returncode,0); self.assertEqual(m['source_dependency_manifest_version'],2); self.assertNotIn('attach_point',m['assets'][0]['origins'][0])
 def test_version_3_manifest_preserves_attach_point(self):
  origins=[{'attribute':'model','attach_point':'weapon_02','definition':'root','slot_path':'weapon_2','reference_chain':['root']}]; pack=self.pack('one',{'Models/A.rigid_model_v2':'A'}); result,m=self.extract_manifest([self.dep('Models/A.rigid_model_v2',origins=origins)],[pack],version=3); self.assertEqual(result.returncode,0); self.assertEqual(m['source_dependency_manifest_version'],3); self.assertEqual(m['assets'][0]['origins'][0]['attach_point'],'weapon_02')
 def test_malformed_manifest_and_duplicate_packs_rejected(self):
  pack=self.pack('one',{'Models/A.rigid_model_v2':'A'}); result,_=self.extract_manifest([{'path':'bad'}],[pack]); self.assertEqual(result.returncode,2); result,_=self.extract_manifest([self.dep('Models/A.rigid_model_v2')],[pack,pack]); self.assertEqual(result.returncode,2)
if __name__=='__main__': unittest.main()
