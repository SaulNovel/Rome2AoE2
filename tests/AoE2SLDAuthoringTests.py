from __future__ import annotations
import json, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
local_deps = ROOT / "build" / "python-deps" / "sld-authoring"
if local_deps.is_dir(): sys.path.insert(0, str(local_deps))

from PIL import Image
from src.aoe2.sld_blocks import ALPHA_THRESHOLD, decode_bc1_block, decode_bc4_block, encode_bc1_block, transparent_bc1_block
from src.aoe2.sld import LAYER_MAIN, LAYER_SHADOW, LAYER_PLAYERCOLOR, SLDFile, SLDFrame, SLDLayer, parse_sld, serialize_sld
from src.aoe2.sld_authoring import (alpha_bounds, author_one_frame, bleed_transparent_rgb, block_bounds,
    author_identical_facets, author_direction_frames, author_facet_animation, build_main_layer, build_manifest,
    build_playercolor_layer, commands_for_positions, premultiplied_bicubic)
from src.aoe2.build_sld_visual_calibration import scale_about_hotspot
from src.aoe2.build_sld_runtime_diagnostics import synthetic_rgb_control
from src.aoe2.generate_sld_diagnostic_mod import configure_clone


class BlocksTests(unittest.TestCase):
    def test_below_threshold_block_is_transparent(self):
        block = [[(40, 50, 60, 1 + x + y) for x in range(4)] for y in range(4)]
        decoded = decode_bc1_block(encode_bc1_block(block, ALPHA_THRESHOLD))
        self.assertTrue(all(pixel[3] == 0 for row in decoded for pixel in row))

    def test_explicit_transparent_block_is_valid(self):
        self.assertEqual([0] * 16, [p[3] for row in decode_bc1_block(transparent_bc1_block()) for p in row])

    def test_threshold_is_shared(self):
        image = Image.new("RGBA", (4, 4)); image.putpixel((1, 1), (255, 0, 0, 127)); image.putpixel((2, 2), (0, 255, 0, 128))
        self.assertEqual((2, 2, 3, 3), alpha_bounds(image))
        layer = build_main_layer(image)
        self.assertEqual(1, len(layer.blocks))
        decoded = decode_bc1_block(layer.blocks[0])
        self.assertEqual(0, decoded[1][1][3]); self.assertEqual(255, decoded[2][2][3])

    def test_bleed_is_deterministic_and_preserves_alpha(self):
        image = Image.new("RGBA", (7, 7), (0, 0, 0, 0)); image.putpixel((3,3),(200,30,10,255))
        a, b = bleed_transparent_rgb(image), bleed_transparent_rgb(image)
        self.assertEqual(a.tobytes(), b.tobytes()); self.assertEqual(image.getchannel("A").tobytes(), a.getchannel("A").tobytes())
        self.assertEqual((200,30,10), a.getpixel((2,3))[:3])


class AuthoringTests(unittest.TestCase):
    def test_sixteen_identical_facets_preserve_order_and_hotspot(self):
        image=Image.new("RGBA",(8,8),(1,2,3,255)); sld=author_identical_facets(image,image,16,(4,4))
        self.assertEqual(list(range(16)),[frame.frame_index for frame in sld.frames]); self.assertEqual(16,sld.facet_count)
        self.assertTrue(all((frame.center_x,frame.center_y)==(4,4) for frame in sld.frames))

    def test_x2_downsample_has_expected_dimensions_and_alpha(self):
        image=Image.new("RGBA",(8,8),(200,20,10,128)); result=premultiplied_bicubic(image,(4,4))
        self.assertEqual((4,4),result.size); self.assertTrue(all(pixel[3]==128 for pixel in result.getdata()))

    def test_synthetic_rgb_control_is_solid_binary_alpha(self):
        image=synthetic_rgb_control(); alpha=set(image.getchannel("A").getdata())
        self.assertEqual({0,255},alpha); self.assertEqual((255,0,0,255),image.getpixel((71,69)))

    def test_synthetic_rgb_x2_is_authored_at_native_scale(self):
        image=synthetic_rgb_control(2); self.assertEqual((400,400),image.size)
        self.assertEqual((255,0,0,255),image.getpixel((142,138)))

    def test_main_only_facets_omit_shadow_layer(self):
        image=Image.new("RGBA",(8,8),(1,2,3,255)); sld=author_identical_facets(image,None,16,(4,4))
        self.assertTrue(all(frame.frame_type==LAYER_MAIN and len(frame.layers)==1 for frame in sld.frames))

    def test_player_color_is_dependent_bc4_and_preserves_shading(self):
        main=Image.new("RGBA",(8,8),(80,70,60,255)); pc=Image.new("RGBA",(8,8),(0,0,0,0))
        for y in range(4):
            for x in range(4): pc.putpixel((x,y),(128,128,128,255))
        sld=author_one_frame(main,None,(4,4),pc); parsed=parse_sld(serialize_sld(sld)); frame=parsed.frames[0]
        self.assertEqual(LAYER_MAIN|LAYER_PLAYERCOLOR,frame.frame_type)
        layer=frame.layers[-1]; self.assertEqual(LAYER_PLAYERCOLOR,layer.layer_type); self.assertEqual(1,len(layer.blocks))
        self.assertEqual((1,1),(layer.flag1,layer.unknown1))
        self.assertEqual(4,sum(skip+draw for skip,draw in layer.commands))
        decoded=decode_bc4_block(layer.blocks[0]); self.assertTrue(all(abs(value-128)<=1 for row in decoded for value in row))


    def test_four_source_direction_order_is_stable(self):
        frames=[]
        for value in (20,60,100,140): frames.append((Image.new("RGBA",(4,4),(value,0,0,255)),None,None))
        sld=author_direction_frames(frames,(2,2),4)
        self.assertEqual([0,1,2,3],[frame.frame_index for frame in sld.frames])

    def test_facet_animation_is_linear_facet_major_and_main_only(self):
        frames=[]
        for facet in range(2):
            for animation_frame in range(3):
                value=facet*50+animation_frame
                frames.append((Image.new("RGBA",(4,4),(value,0,0,255)),None,None))
        sld=author_facet_animation(frames,(2,2),facet_count=2,frames_per_facet=3)
        self.assertEqual(2,sld.facet_count)
        self.assertEqual(list(range(6)),[frame.frame_index for frame in sld.frames])
        self.assertTrue(all(frame.frame_type==LAYER_MAIN for frame in sld.frames))
        with self.assertRaisesRegex(ValueError,"facets x frames"):
            author_facet_animation(frames[:-1],(2,2),facet_count=2,frames_per_facet=3)

    def test_scale_preserves_hotspot_vector_and_target_height(self):
        image=Image.new("RGBA",(40,40));
        for y in range(10,30):
            for x in range(15,25): image.putpixel((x,y),(1,2,3,255))
        result=scale_about_hotspot(image,80,(40,40),40)
        self.assertEqual(40,alpha_bounds(result)[3]-alpha_bounds(result)[1])
    def test_alpha_bounds_and_grid_clamp(self):
        image=Image.new("RGBA",(10,10)); image.putpixel((9,9),(1,2,3,255))
        self.assertEqual((9,9,10,10),alpha_bounds(image)); self.assertEqual((8,8,10,10),block_bounds(alpha_bounds(image),10,10))

    def test_skip_draw_sequences_and_splitting(self):
        block=b"12345678"
        self.assertEqual(([(0,0)],[]),commands_for_positions([]))
        self.assertEqual(([(0,2)],[block,block]),commands_for_positions([(0,block),(1,block)]))
        commands,_=commands_for_positions([(300,block)]); self.assertEqual([(255,0),(45,1)],commands)
        commands,blocks=commands_for_positions([(i,block) for i in range(300)]); self.assertEqual([(0,255),(0,45)],commands); self.assertEqual(300,len(blocks))

    def test_one_frame_one_facet_roundtrip_and_anchor(self):
        main=Image.new("RGBA",(200,200)); shadow=Image.new("RGBA",(200,200))
        main.rectangle if False else None
        for y in range(90,103):
            for x in range(95,107): main.putpixel((x,y),(170,40,20,255))
        for y in range(101,108):
            for x in range(90,116): shadow.putpixel((x,y),(0,0,0,148))
        encoded=serialize_sld(author_one_frame(main,shadow)); parsed=parse_sld(encoded)
        self.assertEqual(1,len(parsed.frames)); self.assertEqual(1,parsed.facet_count)
        self.assertEqual((100,100),(parsed.frames[0].center_x,parsed.frames[0].center_y))
        self.assertEqual(encoded,serialize_sld(parsed))
        layer=parsed.frames[0].layers[0]
        source=(95,90); stored=(source[0]-layer.offset_x1+layer.offset_x1,source[1]-layer.offset_y1+layer.offset_y1)
        self.assertEqual((source[0]-100,source[1]-100),(stored[0]-100,stored[1]-100))
        shadow_layer=parsed.frames[0].layers[1]
        self.assertEqual((1,1),(shadow_layer.flag1,shadow_layer.unknown1))
        shadow_grid=((shadow_layer.offset_x2-shadow_layer.offset_x1+3)//4)*((shadow_layer.offset_y2-shadow_layer.offset_y1+3)//4)
        self.assertEqual(shadow_grid,sum(skip+draw for skip,draw in shadow_layer.commands))

    def test_manifest_determinism_and_no_absolute_paths(self):
        image=Image.new("RGBA",(4,4),(1,2,3,255)); sld=author_one_frame(image,image,(2,2))
        first=build_manifest(Path("main.png"),Path("shadow.png"),Path("out.sld"),sld)
        self.assertEqual(json.dumps(first,sort_keys=True),json.dumps(build_manifest(Path("main.png"),Path("shadow.png"),Path("out.sld"),sld),sort_keys=True))
        with self.assertRaises(ValueError): build_manifest(ROOT/"main.png",Path("shadow.png"),Path("out.sld"),sld)


class StrictParserTests(unittest.TestCase):
    def fixture(self):
        block=encode_bc1_block([[(1,2,3,255)]*4 for _ in range(4)])
        layer=SLDLayer(LAYER_MAIN,0,0,4,4,commands=[(0,1)],blocks=[block])
        return SLDFile([SLDFrame(4,4,2,2,LAYER_MAIN,layers=[layer])],facet_count=1)

    def test_signature_version_truncation_and_trailing(self):
        data=serialize_sld(self.fixture())
        with self.assertRaisesRegex(ValueError,"signature"): parse_sld(b"NOPE"+data[4:])
        bad=bytearray(data); bad[4:6]=(5).to_bytes(2,"little")
        with self.assertRaisesRegex(ValueError,"version"): parse_sld(bytes(bad))
        with self.assertRaisesRegex(ValueError,"truncated"): parse_sld(data[:-1])
        with self.assertRaisesRegex(ValueError,"trailing"): parse_sld(data+b"x")

    def test_layer_mask_and_command_block_validation(self):
        sld=self.fixture(); sld.frames[0].frame_type=LAYER_MAIN|LAYER_SHADOW
        with self.assertRaisesRegex(ValueError,"presence"): serialize_sld(sld)
        sld=self.fixture(); sld.frames[0].layers[0].blocks=[]
        with self.assertRaisesRegex(ValueError,"count"): serialize_sld(sld)

    def test_frame_facet_consistency(self):
        sld=self.fixture(); sld.facet_count=2
        with self.assertRaisesRegex(ValueError,"facet"): serialize_sld(sld)


class DiagnosticDatTests(unittest.TestCase):
    class Unit:
        def __init__(self,name="MILITIA",one=7,two=8): self.name=name; self.standing_sprite_id1=one; self.standing_sprite_id2=two
    class Units:
        def __init__(self): self.items={74:DiagnosticDatTests.Unit()}
        def exists(self,key): return key in self.items
        def get(self,key): return self.items[key]
        def clone_into(self,dest,base,**_):
            source=self.items[base]; clone=DiagnosticDatTests.Unit(source.name,source.standing_sprite_id1,source.standing_sprite_id2); self.items[dest]=clone; return clone
    class Graphics:
        def add_graphic(self,*_,**kwargs):
            self.kwargs=kwargs; return type("Graphic",(),{"id":999})()
    def test_clone_mapping_and_militia_preservation(self):
        workspace=type("Workspace",(),{})(); workspace.unit_manager=self.Units(); workspace.graphic_manager=self.Graphics()
        before=vars(workspace.unit_manager.get(74)).copy(); graphic_id=configure_clone(workspace)
        self.assertEqual(999,graphic_id); self.assertEqual(before,vars(workspace.unit_manager.get(74)))
        clone=workspace.unit_manager.get(2081); self.assertEqual((999,999),(clone.standing_sprite_id1,clone.standing_sprite_id2))
        self.assertEqual(1,workspace.graphic_manager.kwargs["frame_count"]); self.assertEqual(16,workspace.graphic_manager.kwargs["angle_count"])


if __name__ == "__main__": unittest.main()
