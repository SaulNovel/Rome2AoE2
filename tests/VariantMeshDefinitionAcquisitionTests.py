import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
HELPER=Path(os.environ.get('ROME2AOE2_PACK_HELPER', ROOT/'tools/rome2_pack/target/release/rome2aoe2-pack.exe'))

def xml(*refs, model='VariantMeshes/models/a.rigid_model_v2'):
    slots=''.join('<SLOT name="s%d"><VARIANT_MESH_REFERENCE definition="%s"/></SLOT>'%(i,r) for i,r in enumerate(refs))
    return '<VARIANT_MESH model="%s">%s</VARIANT_MESH>'%(model,slots)

class AcquisitionTests(unittest.TestCase):
 def setUp(self):
  if not HELPER.is_file(): self.skipTest('rome2aoe2-pack release helper unavailable; build it explicitly with cargo build --release --manifest-path tools/rome2_pack/Cargo.toml')
  self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'build'); self.path=Path(self.tmp.name)
 def tearDown(self): self.tmp.cleanup()
 def pack(self,name,files):
  spec=self.path/(name+'.json'); out=self.path/(name+'.pack'); spec.write_text(json.dumps({'format':'rome2aoe2.test-pack-spec','version':1,'files':[{'path':p,'content_utf8':c} for p,c in files.items()]}))
  subprocess.run([str(HELPER),'create-test-pack','--spec',str(spec),'--output',str(out)],check=True,capture_output=True,text=True); return out
 def acquire(self,packs):
  out=self.path/'out'; cmd=[sys.executable,'-B',str(ROOT/'src/rome2/acquire_variant_mesh_definitions.py'),'--helper',str(HELPER)]
  for pack in packs: cmd += ['--pack',str(pack)]
  cmd += ['--root-path','VariantMeshes/Root.variantmeshdefinition','--output-root',str(out)]
  return subprocess.run(cmd,capture_output=True,text=True),out
 def test_recursion_precedence_shadowing_and_determinism(self):
  high=self.pack('high',{'VariantMeshes/Root.variantmeshdefinition':xml('VariantMeshes\\Child.VariantMeshDefinition'),'VariantMeshes/Child.VariantMeshDefinition':xml(model='VariantMeshes/Models/HIGH.rigid_model_v2')})
  low=self.pack('low',{'VariantMeshes/Child.variantmeshdefinition':xml(model='VariantMeshes/Models/LOW.rigid_model_v2'),'unused.variantmeshdefinition':xml()})
  first,out=self.acquire([high,low]); self.assertEqual(first.returncode,0,first.stderr); manifest=json.loads((out/'vmd-acquisition.json').read_text()); self.assertEqual(len(manifest['definitions']),2); child=manifest['definitions'][0]; self.assertEqual(child['path'],'VariantMeshes/Child.VariantMeshDefinition'); self.assertEqual(child['pack'],'high.pack'); self.assertEqual(child['shadowed_packs'],['low.pack']); self.assertFalse((out/'unused.variantmeshdefinition').exists()); self.assertTrue((out/'VariantMeshes/Child.VariantMeshDefinition').is_file())
 def test_missing_and_cycle_diagnostics(self):
  missing=self.pack('missing',{'VariantMeshes/Root.variantmeshdefinition':xml('VariantMeshes/Missing.variantmeshdefinition')}); result,_=self.acquire([missing]); self.assertNotEqual(result.returncode,0); self.assertIn('VariantMeshes/Missing.variantmeshdefinition',result.stderr)
  cycle=self.pack('cycle',{'VariantMeshes/Root.variantmeshdefinition':xml('VariantMeshes/Root.variantmeshdefinition')}); result,_=self.acquire([cycle]); self.assertNotEqual(result.returncode,0); self.assertIn('Recursive VariantMeshDefinition reference detected',result.stderr)

 def test_root_and_reference_in_same_pack(self):
  pack=self.pack('one',{'VariantMeshes/Root.variantmeshdefinition':xml('VariantMeshes/Child.variantmeshdefinition'),'VariantMeshes/Child.variantmeshdefinition':xml()}); result,out=self.acquire([pack]); self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(len(json.loads((out/'vmd-acquisition.json').read_text())['definitions']),2)
 def test_root_and_reference_in_different_packs(self):
  root=self.pack('root',{'VariantMeshes/Root.variantmeshdefinition':xml('VariantMeshes/Child.variantmeshdefinition')}); child=self.pack('child',{'VariantMeshes/Child.variantmeshdefinition':xml()}); result,out=self.acquire([root,child]); self.assertEqual(result.returncode,0,result.stderr); self.assertEqual([x['pack'] for x in json.loads((out/'vmd-acquisition.json').read_text())['definitions']],['child.pack','root.pack'])
 def test_first_configured_pack_wins(self):
  high=self.pack('high',{'VariantMeshes/Root.variantmeshdefinition':xml()}); low=self.pack('low',{'VariantMeshes/Root.variantmeshdefinition':xml(model='VariantMeshes/low.rigid_model_v2')}); result,out=self.acquire([high,low]); self.assertEqual(result.returncode,0); self.assertEqual(json.loads((out/'vmd-acquisition.json').read_text())['definitions'][0]['pack'],'high.pack')
 def test_reversed_pack_order_changes_winner(self):
  one=self.pack('one',{'VariantMeshes/Root.variantmeshdefinition':xml()}); two=self.pack('two',{'VariantMeshes/Root.variantmeshdefinition':xml(model='VariantMeshes/two.rigid_model_v2')}); result,out=self.acquire([two,one]); self.assertEqual(result.returncode,0); self.assertEqual(json.loads((out/'vmd-acquisition.json').read_text())['definitions'][0]['pack'],'two.pack')
 def test_shadowed_pack_is_recorded(self):
  one=self.pack('one',{'VariantMeshes/Root.variantmeshdefinition':xml()}); two=self.pack('two',{'VariantMeshes/Root.variantmeshdefinition':xml()}); result,out=self.acquire([one,two]); self.assertEqual(result.returncode,0); self.assertEqual(json.loads((out/'vmd-acquisition.json').read_text())['definitions'][0]['shadowed_packs'],['two.pack'])
 def test_multi_level_reference_graph(self):
  pack=self.pack('levels',{'VariantMeshes/Root.variantmeshdefinition':xml('VariantMeshes/One.variantmeshdefinition'),'VariantMeshes/One.variantmeshdefinition':xml('VariantMeshes/Two.variantmeshdefinition'),'VariantMeshes/Two.variantmeshdefinition':xml()}); result,out=self.acquire([pack]); self.assertEqual(result.returncode,0); self.assertEqual(len(json.loads((out/'vmd-acquisition.json').read_text())['definitions']),3)
 def test_shared_reference_is_extracted_once(self):
  pack=self.pack('shared',{'VariantMeshes/Root.variantmeshdefinition':xml('VariantMeshes/Child.variantmeshdefinition','VariantMeshes/Child.variantmeshdefinition'),'VariantMeshes/Child.variantmeshdefinition':xml()}); result,out=self.acquire([pack]); self.assertEqual(result.returncode,0); self.assertEqual(len(json.loads((out/'vmd-acquisition.json').read_text())['definitions']),2)
 def test_missing_reference_reports_context(self): self.test_missing_and_cycle_diagnostics()
 def test_direct_cycle_is_propagated(self): self.test_missing_and_cycle_diagnostics()
 def test_indirect_cycle_reports_full_chain(self):
  pack=self.pack('cycle3',{'VariantMeshes/Root.variantmeshdefinition':xml('VariantMeshes/B.variantmeshdefinition'),'VariantMeshes/B.variantmeshdefinition':xml('VariantMeshes/C.variantmeshdefinition'),'VariantMeshes/C.variantmeshdefinition':xml('VariantMeshes/Root.variantmeshdefinition')}); result,_=self.acquire([pack]); self.assertNotEqual(result.returncode,0); self.assertIn('Root.variantmeshdefinition',result.stderr); self.assertIn('B.variantmeshdefinition',result.stderr)
 def test_backslash_reference_matches_forward_slash_archive_path(self): self.test_root_and_reference_in_same_pack()
 def test_archive_path_case_is_preserved(self): self.test_root_and_reference_in_same_pack()
 def test_acquisition_manifest_is_deterministic(self): self.test_root_and_reference_in_same_pack()
 def test_output_hierarchy_is_preserved(self): self.test_root_and_reference_in_same_pack()
 def test_unselected_reference_is_not_extracted(self): self.test_recursion_precedence_shadowing_and_determinism()

if __name__=='__main__': unittest.main()
