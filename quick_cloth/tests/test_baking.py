import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy
from quick_cloth import baking

obj = mesh()
p = addon.initialize_setup(obj, bpy.context.scene)
p.frame_end = 5
p.settle_frames = 15
try:
    baking.effective_range(bpy.context.scene, p)
    raise AssertionError('Silently shortened pre-roll')
except ValueError:
    pass
p.settle_frames = 0
assert bpy.ops.quick_cloth.simulate() == {'FINISHED'}
mod = addon.find_cloth_modifier(obj)
assert mod.point_cache.frame_end == 5
p.quality_mode = 'PREVIEW'
bpy.context.scene.frame_set(3)
assert bpy.ops.quick_cloth.bake() == {'FINISHED'}
assert mod.point_cache.is_baked and mod.settings.quality == 20
assert bpy.context.scene.frame_current == 3
p.quality_mode = 'HIGH'
assert baking.state(bpy.context, obj) == 'DIRTY'
assert bpy.ops.quick_cloth.bake(rebuild=True) == {'FINISHED'}
assert mod.settings.quality == 120
assert bpy.ops.quick_cloth.free_bake() == {'FINISHED'}
assert not mod.point_cache.is_baked
mod.show_viewport = False
assert not bpy.ops.quick_cloth.bake.poll()
mod.show_viewport = True
p.use_disk_cache = True
errors, _ = baking.preflight(bpy.context, obj, storage=True)
assert any('Save the .blend' in e for e in errors)
print('QC_TEST PASS actual bake, rebuild, ranges and preflight')
