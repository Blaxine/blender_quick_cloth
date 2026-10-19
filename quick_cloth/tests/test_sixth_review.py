"""Bone-weight safety, failure preservation, and local dependency signatures."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy
from quick_cloth import baking
from mathutils import Matrix

scene = bpy.context.scene
garment = mesh()
p = addon.initialize_setup(garment, scene)
p.frame_end = 2
p.quality_mode = 'PREVIEW'
bpy.ops.quick_cloth.simulate()
body = mesh('Collider')
body.modifiers.new('Collision', 'COLLISION')
parent = bpy.data.objects.new('Parent', None)
scene.collection.objects.link(parent)
body.parent = parent
bpy.context.view_layer.objects.active = garment
bpy.ops.quick_cloth.bake()
original = p.bake_signature
body.matrix_parent_inverse = Matrix.Translation((10, 0, 0))
bpy.context.view_layer.update()
assert body.matrix_world.translation.x == 10
assert original != baking.signature(scene, garment)
bpy.ops.quick_cloth.validate_bake()
assert baking.state(bpy.context, garment) == 'DIRTY'
body.matrix_parent_inverse = Matrix.Identity(4)
assert original == baking.signature(scene, garment)
baking.free(bpy.context, garment)
control = bpy.data.objects.new('Control', None)
scene.collection.objects.link(control)
control.location = (2, 7, 0)
curve = body.driver_add('location', 0)
curve.driver.type = 'AVERAGE'
variable = curve.driver.variables.new()
variable.type = 'TRANSFORMS'
target = variable.targets[0]
target.id = control
target.transform_type = 'LOC_X'
bpy.context.view_layer.update()
bpy.ops.quick_cloth.bake()
original = p.bake_signature
assert body.location.x == 2
target.transform_type = 'LOC_Y'
body.update_tag()
bpy.context.view_layer.update()
assert body.location.x == 7
assert original != baking.signature(scene, garment)
bpy.ops.quick_cloth.validate_bake()
assert baking.state(bpy.context, garment) == 'DIRTY'
for attr, value in (('transform_space', 'LOCAL_SPACE'), ('bone_target', 'Bone')):
    before = baking.signature(scene, garment)
    setattr(target, attr, value)
    assert before != baking.signature(scene, garment), attr

bpy.ops.object.armature_add()
rig = bpy.context.object
bpy.ops.object.mode_set(mode='EDIT')
bone = rig.data.edit_bones.new('Other')
bone.head, bone.tail = (1, 0, 0), (1, 0, 1)
bpy.ops.object.mode_set(mode='OBJECT')
obj = mesh('Rigged')
obj.modifiers.new('Rig', 'ARMATURE').object = rig
first = obj.vertex_groups.new(name='Bone')
first.add([0], .2, 'REPLACE')
second = obj.vertex_groups.new(name='Other')
second.add([0], .5, 'REPLACE')
obj.quick_cloth.pin_group = 'Bone'
try:
    bpy.ops.quick_cloth.pin_from_rig_weights()
    raise AssertionError('Bone destination accepted')
except RuntimeError as exc:
    assert 'rig bone group' in str(exc)
assert abs(first.weight(0) - .2) < 1e-6
assert abs(second.weight(0) - .5) < 1e-6
assert len(obj.vertex_groups) == 2 and obj.quick_cloth.pin_group == 'Bone'
obj.quick_cloth.pin_group = ''
assert bpy.ops.quick_cloth.pin_from_rig_weights() == {'FINISHED'}
pins = obj.vertex_groups[obj.quick_cloth.pin_group]
assert abs(pins.weight(0) - .7) < 1e-6
assert abs(first.weight(0) - .2) < 1e-6
# Failed rebuild must retain pins and group selection.
first.remove([0])
second.remove([0])
count, name = len(obj.vertex_groups), pins.name
try:
    bpy.ops.quick_cloth.pin_from_rig_weights()
    raise AssertionError('Empty rig weights accepted')
except RuntimeError as exc:
    assert 'no weight' in str(exc)
assert abs(pins.weight(0) - .7) < 1e-6
assert len(obj.vertex_groups) == count and obj.quick_cloth.pin_group == name
obj.quick_cloth.pin_group = ''
try:
    bpy.ops.quick_cloth.pin_from_rig_weights()
except RuntimeError:
    pass
assert len(obj.vertex_groups) == count and obj.quick_cloth.pin_group == ''
# Successful refresh removes obsolete pins only after valid source weights exist.
first.add([1], .4, 'REPLACE')
obj.quick_cloth.pin_group = name
assert bpy.ops.quick_cloth.pin_from_rig_weights() == {'FINISHED'}
assert not any(g.group == pins.index for g in obj.data.vertices[0].groups)
assert abs(pins.weight(1) - .4) < 1e-6
print('QC_TEST PASS safe automatic pins and parenting/driver dependency invalidation')
