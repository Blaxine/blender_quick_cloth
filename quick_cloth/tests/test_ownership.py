import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy

a = mesh('A')
a.quick_cloth.mass = 0.8
pa = addon.initialize_setup(a, bpy.context.scene)
assert abs(pa.mass - 0.8) < 1e-5
ma = addon.ensure_cloth_modifier(a)
addon.configure_cloth_from_props(ma, pa)
b = mesh('B')
pb = addon.initialize_setup(b, bpy.context.scene)
pb.preset = 'COTTON'
assert abs(a.quick_cloth.mass - 0.8) < 1e-5
assert pa.setup_id != pb.setup_id
old = mesh('Existing')
m = addon.ensure_cloth_modifier(old)
m.settings.mass = 0.67
m.settings.shrink_min = -0.12
try:
    addon.initialize_setup(old, bpy.context.scene)
    raise AssertionError('implicit adoption allowed')
except ValueError:
    pass
p = addon.initialize_setup(old, bpy.context.scene, adopt=True)
assert abs(p.mass - .67) < 1e-5 and abs(m.settings.shrink_min + .12) < 1e-5
assert p.legacy_fit
copy = old.copy()
bpy.context.collection.objects.link(copy)
addon.initialize_setup(copy, bpy.context.scene)
assert copy.quick_cloth.setup_id != p.setup_id
print('QC_TEST PASS ownership and migration')
