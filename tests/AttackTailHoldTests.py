import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'build/python-deps/pillow')]
from PIL import Image
from aoe2.build_fast_attack_tail_hold import extend,same_visual_frame,tail_hold_plan
from aoe2.sld import parse_sld,serialize_sld
from aoe2.sld_authoring import author_facet_animation
class AttackTailHoldTests(unittest.TestCase):
 def test_extends_only_tail_and_preserves_native_prefix(self):
  frames=[]
  for direction in range(2):
   for ordinal in range(3):frames.append((Image.new('RGBA',(4,4),(direction*40,ordinal*40,20,255)),None,None))
  source=parse_sld(serialize_sld(author_facet_animation(frames,(2,2),2,3)));extended=extend(source,2,3,2,2);roundtrip=parse_sld(serialize_sld(extended))
  self.assertEqual(10,len(roundtrip.frames));self.assertTrue(all(same_visual_frame(roundtrip.frames[d*5+i],source.frames[d*3+i]) for d in range(2) for i in range(3)));self.assertTrue(all(same_visual_frame(roundtrip.frames[d*5+i],source.frames[d*3+2]) for d in range(2) for i in (3,4)))
 def test_plan_derives_tail_from_unit_timing(self):
  plan=tail_hold_plan(6,.1,1.0,4)
  self.assertEqual({'source_count':6,'hold_ordinal':4,'target_count':10,'extra_count':4,'frame_duration':.1,'reload_time':1.0},plan)
 def test_approved_unit_timing_is_exactly_representable(self):
  plan=tail_hold_plan(27,.05,2.0)
  self.assertEqual((26,13,40),(plan['hold_ordinal'],plan['extra_count'],plan['target_count']))
 def test_plan_rejects_nonrepresentable_or_nonpositive_gap(self):
  with self.assertRaises(ValueError):tail_hold_plan(8,.1,.75)
  with self.assertRaises(ValueError):tail_hold_plan(10,.1,1.0)
if __name__=='__main__':unittest.main()
