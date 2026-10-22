"""Reload-stable cache signatures and side-effect-free Simulate rejection on cages."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy
from quick_cloth import baking

scene = bpy.context.scene
garment = mesh()
body = mesh('Collider')
body.modifiers.new('Collision', 'COLLISION')
# Registered add-on settings and nested custom properties are stored as ID
# property groups/arrays whose reprs contain memory addresses.
if hasattr(scene, 'cycles'):
    scene.cycles.samples = 64
    garment.cycles.use_motion_blur = False
scene['studio'] = {'nested': {'value': 1}, 'levels': [1, 2, 3]}
body['weights'] = [.1, .2]
body['reference'] = garment
bpy.context.view_layer.objects.active = garment
p = addon.initialize_setup(garment, scene)
p.frame_end = 2
p.quality_mode = 'PREVIEW'
assert bpy.ops.quick_cloth.simulate() == {'FINISHED'}
assert bpy.ops.quick_cloth.bake() == {'FINISHED'}
original = p.bake_signature
assert original == baking.signature(scene, garment)

path = str(Path(tempfile.mkdtemp(prefix='qc_seventh_')) / 'reload.blend')
bpy.ops.wm.save_as_mainfile(filepath=path)
bpy.ops.wm.open_mainfile(filepath=path)
scene = bpy.context.scene
garment = scene.objects['Garment']
p = garment.quick_cloth
assert p.bake_needs_validation
assert baking.signature(scene, garment) == original, 'Signature changed across save/reload'
bpy.context.view_layer.objects.active = garment
assert bpy.ops.quick_cloth.validate_bake() == {'FINISHED'}
assert p.bake_state == 'BAKED' and not p.bake_needs_validation

# Plain serialization must still detect real custom-property edits.
scene['studio']['nested']['value'] = 2
assert baking.signature(scene, garment) != original
scene['studio']['nested']['value'] = 1
scene.objects['Collider']['reference'] = scene.objects['Collider']
assert baking.signature(scene, garment) != original
scene.objects['Collider']['reference'] = garment
assert baking.signature(scene, garment) == original

# Simulate on the Animator Mode cage must refuse before registering anything.
baking.free(bpy.context, garment)
assert bpy.ops.quick_cloth.enter_animator_mode() == {'FINISHED'}
cage = bpy.context.view_layer.objects.active
assert cage.get('qc_helper') == 'cage'
registry = [(e.uid, e.owner) for e in scene.quick_cloth_registry]
modifiers = [m.name for m in cage.modifiers]
identity = (cage.quick_cloth.setup_id, cage.quick_cloth.owner)
assert identity[0] == ''
try:
    bpy.ops.quick_cloth.simulate()
    raise AssertionError('Simulate accepted the animation cage')
except RuntimeError as exc:
    message = str(exc)
assert (cage.quick_cloth.setup_id, cage.quick_cloth.owner) == identity, 'Cage was initialized'
assert [(e.uid, e.owner) for e in scene.quick_cloth_registry] == registry, 'Registry changed'
assert [m.name for m in cage.modifiers] == modifiers
assert 'animation cage' in message, message
assert garment.quick_cloth.animator_state
assert bpy.ops.quick_cloth.exit_animator_mode() == {'FINISHED'}
print('QC_TEST PASS reload-stable signatures and cage Simulate rejection')
