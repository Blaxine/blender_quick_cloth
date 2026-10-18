import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy

obj = mesh()
assert not bpy.ops.quick_cloth.enter_animator_mode.poll()
assert bpy.ops.quick_cloth.simulate() == {'FINISHED'}
assert bpy.ops.quick_cloth.enter_animator_mode() == {'FINISHED'}
cage = bpy.context.object
assert cage.hide_render
obj.name = 'Renamed'
cage.name = 'RenamedCage'
assert addon.find_garment_for_cage(cage) == obj
assert bpy.ops.quick_cloth.exit_animator_mode() == {'FINISHED'}
obj.data.vertices[0].co.x += .5
assert bpy.ops.quick_cloth.enter_animator_mode() == {'FINISHED'}
cage = bpy.context.object
assert cage.data.vertices[0].co == obj.data.vertices[0].co
bpy.data.objects.remove(cage, do_unlink=True)
assert bpy.ops.quick_cloth.exit_animator_mode.poll()
assert bpy.ops.quick_cloth.exit_animator_mode() == {'FINISHED'}
assert not obj.hide_get() and not obj.quick_cloth.animator_state
assert addon.find_cloth_modifier(obj).show_viewport
print('QC_TEST PASS animator rename, refresh and deletion recovery')
