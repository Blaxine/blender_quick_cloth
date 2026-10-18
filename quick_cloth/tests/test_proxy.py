import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy

sim = mesh('Simulation')
assert bpy.ops.quick_cloth.simulate() == {'FINISHED'}
render = mesh('Render')
render.location.z = .01
unrelated = render.modifiers.new('User deformation', 'SURFACE_DEFORM')
unrelated.show_viewport = False
sim.select_set(True)
bpy.context.view_layer.objects.active = sim
assert bpy.ops.quick_cloth.bind_render_mesh(action='BIND') == {'FINISHED'}
managed = render.modifiers[render.quick_cloth.binding_name]
assert managed != unrelated and managed.is_bound
assert bpy.ops.quick_cloth.bind_render_mesh(action='REBIND') == {'FINISHED'}
assert bpy.ops.quick_cloth.bind_render_mesh(action='UNBIND') == {'FINISHED'}
assert not managed.is_bound and unrelated.name in render.modifiers
print('QC_TEST PASS owned bind/rebind/unbind')
