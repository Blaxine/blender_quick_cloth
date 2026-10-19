import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy
from quick_cloth import baking
scene = bpy.context.scene
obj = mesh()
p = addon.initialize_setup(obj, scene)
p.frame_end = 2
p.quality_mode = 'PREVIEW'
bpy.ops.quick_cloth.simulate()
bpy.ops.quick_cloth.bake()
cloth = addon.find_cloth_modifier(obj)
obj.modifiers.new('ChangingTopology', 'BUILD')
rigmod = obj.modifiers.new('Rig', 'ARMATURE')
bpy.ops.object.armature_add()
rigmod.object = bpy.context.object
bpy.context.view_layer.objects.active = obj
before = list(obj.modifiers)
assert any('topology' in e for e in baking.preflight(bpy.context, obj, storage=True)[0])
try:
    bpy.ops.quick_cloth.bake(rebuild=True)
    raise AssertionError('Unsafe planned stack accepted')
except RuntimeError as exc:
    assert 'topology' in str(exc)
assert list(obj.modifiers) == before and cloth.point_cache.is_baked

with tempfile.TemporaryDirectory(prefix='qc_adoption_') as folder:
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(folder) / 'adoption.blend'))
    legacy = mesh('DiskCache')
    mod = addon.ensure_cloth_modifier(legacy)
    mod.point_cache.use_disk_cache = True
    mod.point_cache.frame_start = 5
    mod.point_cache.frame_end = 8
    scene.quick_cloth.use_preview_range = True
    scene.use_preview_range = True
    scene.frame_preview_start = 1
    scene.frame_preview_end = 2
    props = addon.initialize_setup(legacy, scene, adopt=True)
    assert props.use_disk_cache and mod.point_cache.use_disk_cache
    assert not props.use_preview_range
    assert baking.effective_range(scene, props) == (5, 8)
    bpy.ops.quick_cloth.simulate()
    assert mod.point_cache.use_disk_cache
    assert (mod.point_cache.frame_start, mod.point_cache.frame_end) == (5, 8)
print('QC_TEST PASS planned stack safety and cache adoption')
