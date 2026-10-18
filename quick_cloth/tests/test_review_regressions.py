"""Regressions found in the second code-review pass."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy
from quick_cloth import baking

obj = mesh('Original')
p = addon.initialize_setup(obj, bpy.context.scene)
identity = p.setup_id
duplicate = obj.copy()
bpy.context.collection.objects.link(duplicate)
addon.initialize_setup(obj, bpy.context.scene)
assert p.setup_id == identity
addon.initialize_setup(duplicate, bpy.context.scene)
assert duplicate.quick_cloth.setup_id != identity
assert p.setup_id == identity and p.owner == obj
bpy.data.objects.remove(duplicate, do_unlink=True)

legacy = mesh('OutsidePanelRange')
mod = addon.ensure_cloth_modifier(legacy)
mod.settings.shrink_min = -.5
try:
    addon.initialize_setup(legacy, bpy.context.scene, adopt=True)
    raise AssertionError('Lossy migration was accepted')
except ValueError as exc:
    assert 'without loss' in str(exc)
assert not legacy.quick_cloth.setup_id
assert mod.settings.shrink_min == -.5
bpy.data.objects.remove(legacy, do_unlink=True)

bpy.context.view_layer.objects.active = obj
obj.select_set(True)
p.use_wind = True
p.frame_end = 2
p.wind_strength = 1
assert bpy.ops.quick_cloth.simulate() == {'FINISHED'}
p.wind_strength = 42
assert bpy.ops.quick_cloth.bake() == {'FINISHED'}
assert p.wind.field.strength == 42
duplicate = obj.copy()
bpy.context.collection.objects.link(duplicate)
bpy.context.view_layer.objects.active = duplicate
original_wind = p.wind
assert addon.remove_wind_rig(bpy.context) == 0
assert p.wind == original_wind and p.wind.name in bpy.data.objects
bpy.data.objects.remove(duplicate, do_unlink=True)
bpy.context.view_layer.objects.active = obj
p.bake_metadata = 'invalid JSON'
assert baking.state(bpy.context, obj) == 'NEEDS_VALIDATION'

original = baking.geometry_issues
def no_mesh_scan(_):
    raise AssertionError('UI polling scanned full mesh')
baking.geometry_issues = no_mesh_scan
try:
    baking.preflight(bpy.context, obj, storage=False)
finally:
    baking.geometry_issues = original
print('QC_TEST PASS second-review regressions')
