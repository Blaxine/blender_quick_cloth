import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy
from quick_cloth import baking

obj = mesh()
p = addon.initialize_setup(obj, bpy.context.scene)
p.frame_end = 2
assert bpy.ops.quick_cloth.simulate() == {'FINISHED'}
assert bpy.ops.quick_cloth.bake() == {'FINISHED'}
original = baking.free
def cannot_free(context, target):
    raise RuntimeError('injected cache invalidation failure')
baking.free = cannot_free
try:
    try:
        result = bpy.ops.quick_cloth.bake(rebuild=True)
        assert result == {'CANCELLED'}
    except RuntimeError as exc:
        assert 'injected cache invalidation failure' in str(exc)
finally:
    baking.free = original
assert addon.find_cloth_modifier(obj).point_cache.is_baked
assert p.bake_state == 'FAILED' and 'injected' in p.bake_error
print('QC_TEST PASS invalidation failure preserves old cache')
