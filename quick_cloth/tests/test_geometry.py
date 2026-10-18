import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy

obj = mesh()
assert not addon.geometry_issues(obj)[0]  # Open sheets are valid.
cloth = addon.ensure_cloth_modifier(obj)
a = obj.modifiers.new('A', 'ARMATURE')
b = obj.modifiers.new('B', 'ARMATURE')
addon.ensure_stack_order(obj)
assert list(obj.modifiers).index(cloth) > list(obj.modifiers).index(b)
obj.modifiers.remove(a)
obj.modifiers.remove(b)
obj.scale.z = 0
bpy.context.view_layer.update()
assert any('singular' in s for s in addon.geometry_issues(obj)[0])
obj.scale.z = 1
existing = obj.vertex_groups.new(name='pin')
existing.add([0], .4, 'REPLACE')
bpy.ops.object.mode_set(mode='EDIT')
assert bpy.ops.quick_cloth.set_pin_group() == {'FINISHED'}
assert bpy.context.mode == 'EDIT_MESH'
bpy.ops.object.mode_set(mode='OBJECT')
assert abs(existing.weight(0) - .4) < 1e-5
assert obj.quick_cloth.pin_group != existing.name
copy = obj.copy()
bpy.context.collection.objects.link(copy)
try:
    addon.validate_pin_edit(obj)
    raise AssertionError('Shared mesh was not rejected')
except ValueError:
    pass
print('QC_TEST PASS geometry, stack and pin safety')
