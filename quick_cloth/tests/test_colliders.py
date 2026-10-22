"""Several collision meshes per garment: list editing, checks, and a bake that rests on all of them."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, bpy
from quick_cloth import baking

scene = bpy.context.scene


def box(name, x, height):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, height / 2))
    obj = bpy.context.object
    obj.name = name
    obj.scale = (1.0, 1.2, height)
    bpy.ops.object.transform_apply(scale=True)
    return obj


def activate(obj, *others):
    for other in bpy.context.selected_objects:
        other.select_set(False)
    for other in others:
        other.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


seat = box('Seat', -.52, .4)               # boxes side by side, 4 cm apart
table = box('Table', .52, .7)
bpy.ops.mesh.primitive_plane_add(size=6)
floor = bpy.context.object
floor.name = 'Floor'
bpy.ops.mesh.primitive_grid_add(x_subdivisions=30, y_subdivisions=15, size=1, location=(0, 0, 1.0))
cloth = bpy.context.object
cloth.name = 'Throw'
cloth.scale = (1.6, 1.0, 1)
bpy.ops.object.transform_apply(scale=True)

activate(cloth)
p = addon.initialize_setup(cloth, scene)
p.preset = 'COTTON'
p.quality_mode = 'PREVIEW'
p.frame_start, p.frame_end = 1, 30
p.use_collision_objects = False
p.body = seat

# + adds every selected mesh except the cloth; with nothing else selected it adds an empty row.
activate(cloth, table, floor)
assert bpy.ops.quick_cloth.collider_add() == {'FINISHED'}
assert [item.object for item in p.colliders] == [table, floor]
activate(cloth, table)
assert bpy.ops.quick_cloth.collider_add() == {'FINISHED'}, 'already listed meshes are skipped'
assert len(p.colliders) == 3 and p.colliders[2].object is None
p.colliders[2].object = seat                    # the body again: not counted twice
assert baking.collision_targets(p) == [seat, table, floor]
p.collider_index = 2
assert bpy.ops.quick_cloth.collider_remove() == {'FINISHED'}
assert [item.object for item in p.colliders] == [table, floor] and p.collider_index == 1

# Checks name every listed mesh that isn't a collider yet; one button fixes them all.
activate(cloth)
assert bpy.ops.quick_cloth.simulate() == {'FINISHED'}
_, warnings = baking.preflight(bpy.context, cloth)
assert all(any(o.name in w and 'Make Them Colliders' in w for w in warnings) for o in (seat, table, floor)), warnings
assert bpy.ops.quick_cloth.body_collider() == {'FINISHED'}
assert all(baking.is_collider(o) for o in (seat, table, floor))
_, warnings = baking.preflight(bpy.context, cloth)
assert not any("isn't a collider" in w for w in warnings), warnings

# Picking a row in the list is not a scene change.
before = baking.signature(scene, cloth)
p.collider_index = 0
assert baking.signature(scene, cloth) == before

# The throw rests on both boxes: neither the seat (main body) nor the table (list) lets it through.
assert bpy.ops.quick_cloth.bake() == {'FINISHED'}
scene.frame_set(30)
evaluated = cloth.evaluated_get(bpy.context.evaluated_depsgraph_get())
points = [evaluated.matrix_world @ v.co for v in evaluated.data.vertices]
on_seat = [v.z for v in points if -.8 < v.x < -.25 and abs(v.y) < .4]
on_table = [v.z for v in points if .25 < v.x < .8 and abs(v.y) < .4]
assert on_seat and min(on_seat) > .4 - .01, f'cloth sank into the seat: {min(on_seat):.3f}'
assert on_table and min(on_table) > .7 - .01, f'cloth sank into the table: {min(on_table):.3f}'
print(f'Seat rest {min(on_seat):.3f} m, table rest {min(on_table):.3f} m')
print('QC_TEST PASS several collision meshes per garment')
