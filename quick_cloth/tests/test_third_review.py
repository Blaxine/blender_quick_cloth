import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy
from quick_cloth import baking
s = bpy.context.scene
obj = mesh()
p = addon.initialize_setup(obj, s)
p.frame_end = 2
p.settle_frames = 0
p.quality_mode = 'PREVIEW'
p.use_wind = True
bpy.ops.quick_cloth.simulate()
m = addon.find_cloth_modifier(obj)
bpy.ops.quick_cloth.bake()
for helper in (p.wind, p.turbulence):
    original = helper.field.type
    helper.field.type = 'FORCE'
    assert baking.preflight(bpy.context, obj, storage=True)[0]
    assert not bpy.ops.quick_cloth.bake.poll()
    assert m.point_cache.is_baked
    helper.field.type = original
baking.free(bpy.context, obj)
p.use_preview_range = True
s.use_preview_range = True
s.frame_preview_start = 1
s.frame_preview_end = 2
bpy.ops.quick_cloth.bake()
s.frame_preview_end = 3
assert p.bake_signature != baking.signature(s, obj)
assert baking.state(bpy.context, obj) == 'DIRTY'
bpy.ops.quick_cloth.validate_bake()
assert p.bake_state == 'DIRTY'
p.settle_frames = 10
assert bpy.ops.quick_cloth.validate_bake() == {'FINISHED'}
assert baking.state(bpy.context, obj) == 'DIRTY'
p.settle_frames = 0
baking.free(bpy.context, obj)
old = mesh('Adopt')
mod = addon.ensure_cloth_modifier(old)
mod.settings.internal_tension_stiffness = 5
mod.settings.internal_compression_stiffness = 23
try:
    addon.initialize_setup(old, s, adopt=True)
    raise AssertionError('Lossy adoption allowed')
except ValueError:
    pass
assert not old.quick_cloth.setup_id
assert mod.settings.internal_compression_stiffness == 23
body = mesh('AnimatedCollider')
body.keyframe_insert(data_path='rotation_euler', frame=1)
bpy.context.view_layer.update()
before = baking.signature(s, obj)
body.location.x += 10
bpy.context.view_layer.update()
assert before != baking.signature(s, obj)
# Evaluating the keyed rotation at another frame must not dirty static channels.
body.rotation_euler.z = 1
body.keyframe_insert(data_path='rotation_euler', frame=3)
s.frame_set(1)
before = baking.signature(s, obj)
s.frame_set(2)
assert before == baking.signature(s, obj)
bpy.ops.object.armature_add()
rig = bpy.context.object
bone = rig.pose.bones[0]
bone.keyframe_insert(data_path='rotation_quaternion', frame=1)
before = baking.signature(s, obj)
bone.location.x += 1
assert before != baking.signature(s, obj)
obstacle = mesh('RigidObstacle')
bpy.ops.rigidbody.object_add()
g = mesh('Thickness')
gp = addon.initialize_setup(g, s)
gp.settle_frames = 0
gp.frame_end = 2
gp.collider_thickness = .003
gp.object_distance = .02
gp.use_collision_objects = True
bpy.ops.quick_cloth.simulate()
assert abs(obstacle.collision.thickness_outer - .003) < 1e-6
print('QC_TEST PASS review: safe rebuild, range, transforms, adoption and thickness')
