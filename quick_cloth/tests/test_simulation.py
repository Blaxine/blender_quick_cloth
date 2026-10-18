"""Small real collision and moving-rig fixtures, not full visual certification."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, -.1))
floor = bpy.context.object
floor.scale = (3, 3, .1)
addon.make_collider(floor, .005)
garment = mesh('Drop')
garment.location.z = .5
p = addon.initialize_setup(garment, bpy.context.scene)
p.frame_end = 40
p.object_distance = .005
p.body = floor
p.quality_mode = 'HIGH'
assert bpy.ops.quick_cloth.simulate() == {'FINISHED'}
assert bpy.ops.quick_cloth.bake() == {'FINISHED'}
bpy.context.scene.frame_set(40)
deps = bpy.context.evaluated_depsgraph_get()
evaluated = garment.evaluated_get(deps)
zs = [(evaluated.matrix_world @ v.co).z for v in evaluated.data.vertices]
assert min(zs) >= -.002, f'Floor penetration: {min(zs)}'
assert max(zs) < .1, f'Cloth did not settle on collider: {max(zs)}'
print('QC_METRIC unrigged_floor_min_z', min(zs), 'max_z', max(zs))

bpy.context.scene.frame_set(1)
rigged = mesh('Rigged')
rigged.location.z = 2
bpy.ops.object.armature_add(location=(0, 0, 2))
rig = bpy.context.object
bone = rig.data.bones[0]
weights = rigged.vertex_groups.new(name=bone.name)
weights.add(list(range(len(rigged.data.vertices))), 1, 'REPLACE')
arm = rigged.modifiers.new('Character Rig', 'ARMATURE')
arm.object = rig
pin = rigged.vertex_groups.new(name='Collar')
top = max(v.co.y for v in rigged.data.vertices)
indices = [v.index for v in rigged.data.vertices if abs(v.co.y - top) < .001]
pin.add(indices, 1, 'REPLACE')
pose = rig.pose.bones[0]
pose.location.x = 0
pose.keyframe_insert('location', frame=1)
pose.location.x = .3
pose.keyframe_insert('location', frame=24)
bpy.context.scene.frame_set(1)
for obj in bpy.context.selected_objects:
    obj.select_set(False)
rigged.select_set(True)
bpy.context.view_layer.objects.active = rigged
p = addon.initialize_setup(rigged, bpy.context.scene)
p.frame_end = 24
p.pin_group = pin.name
p.quality_mode = 'HIGH'
assert bpy.ops.quick_cloth.simulate() == {'FINISHED'}
assert bpy.ops.quick_cloth.bake() == {'FINISHED'}
bpy.context.scene.frame_set(24)
evaluated = rigged.evaluated_get(bpy.context.evaluated_depsgraph_get())
errors = [abs(evaluated.data.vertices[i].co.x - (rigged.data.vertices[i].co.x + .3)) for i in indices]
assert max(errors) < .03, f'Rig attachment error: {max(errors)}'
print('QC_METRIC rig_attachment_max_error', max(errors))
print('QC_TEST PASS unrigged collision and rigged attachment bakes')
