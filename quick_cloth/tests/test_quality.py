import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy

obj = mesh()
p = addon.initialize_setup(obj, bpy.context.scene)
mod = addon.ensure_cloth_modifier(obj)
p.preset = 'COTTON'
p.use_self_collision = True
p.quality_mode = 'PREVIEW'
addon.configure_cloth_from_props(mod, p)
assert (mod.settings.quality, mod.collision_settings.collision_quality) == (6, 3)
assert mod.collision_settings.use_self_collision
p.quality_steps = 17
p.collision_quality = 7
assert p.quality_mode == 'CUSTOM'
p.quality_mode = 'HIGH'
assert addon.resolve_quality(p) == (20, 8)
p.quality_mode = 'CUSTOM'
assert addon.resolve_quality(p) == (17, 7)
p.preset = 'LATEX'
assert addon.resolve_quality(p) == (17, 7)
p.quality_mode = 'HIGH'
assert addon.resolve_quality(p) == (21, 8)
physical = (p.mass, p.tension_stiffness, p.object_distance, p.time_scale)
p.quality_mode = 'MEDIUM'
assert physical == (p.mass, p.tension_stiffness, p.object_distance, p.time_scale)
print('QC_TEST PASS quality and Custom restoration')
