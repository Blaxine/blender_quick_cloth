"""Fabric list: complete tables, stable stored values, and every fabric bakes a sane pinned panel."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
from bootstrap import addon, bpy

ids = [item[0] for item in addon.PRESET_ITEMS]
assert len(ids) >= 21 and len(set(ids)) == len(ids)
assert set(ids) == set(addon.PRESETS) == set(addon.PRESET_HINTS)
assert len({item[3] for item in addon.PRESET_ITEMS}) == len(ids), 'stored enum numbers must be unique'
keys = set(addon.PRESETS['SIMPLE'])
assert all(set(values) == keys for values in addon.PRESETS.values()), 'every fabric sets every key'
for name, values in addon.PRESETS.items():
    # Measured in 5.2: bend damping far above the weight jitters; large self gaps explode.
    assert values['bending_damping'] <= 8 * values['mass'], name
    assert not values['use_self_collision'] or values['self_distance'] <= .006, name

scene = bpy.context.scene
bpy.ops.mesh.primitive_grid_add(x_subdivisions=16, y_subdivisions=20, size=1, location=(0, 0, 1.5),
                                rotation=(1.5708, 0, 0))
panel = bpy.context.object
panel.name = 'Panel'
bpy.ops.object.transform_apply(rotation=True)
top = max(v.co.z for v in panel.data.vertices)
panel.vertex_groups.new(name='Collar').add([v.index for v in panel.data.vertices if v.co.z > top - 1e-4],
                                           1.0, 'REPLACE')
bpy.context.view_layer.objects.active = panel
p = addon.initialize_setup(panel, scene)
p.pin_group = 'Collar'
p.quality_mode = 'PREVIEW'
p.frame_start, p.frame_end = 1, 24
p.use_collision_objects = False
assert bpy.ops.quick_cloth.simulate() == {'FINISHED'}
n = len(panel.data.vertices)
edges = np.array([e.vertices[:] for e in panel.data.edges])
rest = np.array([v.co[:] for v in panel.data.vertices])
rest_len = np.linalg.norm(rest[edges[:, 0]] - rest[edges[:, 1]], axis=1)

# Stored enum numbers of the original fabrics are what old files hold.
for value, name in enumerate(('SIMPLE', 'COTTON', 'POLYESTER', 'COUCH_LEATHER', 'LEATHER_COAT', 'LATEX',
                              'STRETCH_DENIM', 'RIGID_DENIM', 'SELVEDGE_DENIM')):
    p['preset'] = value
    assert p.preset == name, (value, p.preset)

worst = {}
for name in ids:
    p.preset = name
    assert all(abs(getattr(p, k) - v) < 1e-6 if isinstance(v, float) else getattr(p, k) == v
               for k, v in addon.PRESETS[name].items() if k not in {'quality_steps', 'collision_quality'}), name
    assert bpy.ops.quick_cloth.bake(rebuild=addon.find_cloth_modifier(panel).point_cache.is_baked) == {'FINISHED'}
    frames = []
    for frame in (8, 16, 24):
        scene.frame_set(frame)
        evaluated = panel.evaluated_get(bpy.context.evaluated_depsgraph_get())
        co = np.empty(n * 3)
        evaluated.data.vertices.foreach_get('co', co)
        frames.append(co.reshape(n, 3))
    pos = np.array(frames)
    assert np.isfinite(pos).all(), f'{name}: nonfinite positions'
    stretch = (np.linalg.norm(pos[:, edges[:, 0]] - pos[:, edges[:, 1]], axis=2) / rest_len).max()
    assert stretch < 1.6, f'{name}: edges stretched {stretch:.2f}x'
    assert np.abs(pos).max() < 5, f'{name}: cloth flew off'
    worst[name] = round(float(stretch), 3)
    scene.frame_set(1)
print('max stretch per fabric', worst)
print(f'QC_TEST PASS {len(ids)} fabric presets are complete and bake stably')
