import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy

obj = mesh()
p = addon.initialize_setup(obj, bpy.context.scene)
m = addon.ensure_cloth_modifier(obj)
m.collision_settings.use_collision = False
collection = bpy.data.collections.new('User filter')
m.collision_settings.collection = collection
addon.configure_cloth_from_props(m, p)
assert m.collision_settings.use_collision
assert m.collision_settings.collection == collection
body = mesh('Body')
addon.make_collider(body)
body.collision.thickness_outer = .004
body.collision.damping = .7
addon.make_collider(body)
assert abs(body.collision.thickness_outer - .004) < 1e-5
assert abs(body.collision.damping - .7) < 1e-5
bpy.context.view_layer.objects.active = obj
stranger = bpy.data.objects.new('QC_Wind', None)
bpy.context.collection.objects.link(stranger)
p.use_wind = True
wind = addon.ensure_wind_rig(bpy.context, p)
assert wind != stranger and wind.field.type == 'WIND'
assert p.turbulence.field.type == 'TURBULENCE'
p.use_wind = False
assert wind.field.strength == 0 and p.turbulence.field.strength == 0
assert addon.remove_wind_rig(bpy.context) == 2
assert stranger.name in bpy.data.objects
p.preset = 'LATEX'
assert m.settings.shrink_min > 0
print('QC_TEST PASS collision preservation and owned wind')
