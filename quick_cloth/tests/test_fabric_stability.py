"""Self-gap safeguard and settled leather presets (they used to jitter and explode)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
from bootstrap import addon, bpy
from quick_cloth import validation

scene = bpy.context.scene


def floor():
    bpy.ops.mesh.primitive_plane_add(size=4)
    plane = bpy.context.object
    plane.modifiers.new('Collision', 'COLLISION')
    return plane


def cushion(name):
    # Closed box with 1 cm side edges: the case that exploded with a 10-12 mm gap.
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, .2))
    obj = bpy.context.object
    obj.name = name
    obj.scale = (.6, .6, .15)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=14)
    bpy.ops.object.mode_set(mode='OBJECT')
    return obj


def activate(obj):
    for other in bpy.context.view_layer.objects:
        other.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


ground = floor()

# A gap of half the short edge is refused before anything is registered.
probe = cushion('Probe')
activate(probe)
short = validation.short_edge_length(probe)
assert abs(short - .01) < .001, short
probe.quick_cloth.use_self_collision = True
probe.quick_cloth.self_distance = .012
registry = len(scene.quick_cloth_registry)
try:
    bpy.ops.quick_cloth.simulate()
    raise AssertionError('Simulate accepted a gap larger than the edges')
except RuntimeError as exc:
    assert 'Use Safe Gap' in str(exc), exc
assert not probe.quick_cloth.setup_id and len(scene.quick_cloth_registry) == registry

# Between a third and 0.45 of the edge only warns.
probe.quick_cloth.self_distance = .004
errors, warnings = validation.geometry_issues(probe)
assert not errors and any('Gap to Itself' in w for w in warnings), (errors, warnings)

# Use Safe Gap picks a quarter of the short edge, and the check passes.
assert bpy.ops.quick_cloth.fit_self_gap() == {'FINISHED'}
assert abs(probe.quick_cloth.self_distance - .0025) < 1e-6, probe.quick_cloth.self_distance
assert validation.self_gap_issue(probe) is None
probe.quick_cloth.use_self_collision = False
assert validation.self_gap_issue(probe) is None
bpy.data.objects.remove(probe)

# Both leather presets settle on a floor instead of jittering or blowing up.
for preset in ('COUCH_LEATHER', 'LEATHER_COAT'):
    garment = cushion(preset)
    activate(garment)
    p = addon.initialize_setup(garment, scene)
    p.preset = preset
    p.quality_mode = 'MEDIUM'
    p.frame_start, p.frame_end = 1, 60
    p.use_collision_objects = False
    p.body = ground
    try:
        bpy.ops.quick_cloth.simulate()
    except RuntimeError:
        assert bpy.ops.quick_cloth.fit_self_gap() == {'FINISHED'}
        assert bpy.ops.quick_cloth.simulate() == {'FINISHED'}
    assert bpy.ops.quick_cloth.bake() == {'FINISHED'}

    n = len(garment.data.vertices)
    rest = np.empty(n * 3)
    garment.data.vertices.foreach_get('co', rest)
    rest = rest.reshape(n, 3)
    edges = np.empty(len(garment.data.edges) * 2, dtype=np.int64)
    garment.data.edges.foreach_get('vertices', edges)
    edges = edges.reshape(-1, 2)
    rest_len = np.linalg.norm(rest[edges[:, 0]] - rest[edges[:, 1]], axis=1)
    frames = []
    for frame in range(1, 61):
        scene.frame_set(frame)
        evaluated = garment.evaluated_get(bpy.context.evaluated_depsgraph_get())
        co = np.empty(n * 3)
        evaluated.data.vertices.foreach_get('co', co)
        frames.append((np.array(evaluated.matrix_world.to_3x3()) @ co.reshape(n, 3).T).T
                      + np.array(evaluated.matrix_world.translation))
    pos = np.array(frames)
    assert np.isfinite(pos).all(), f'{preset}: nonfinite positions'
    late = np.linalg.norm(np.diff(pos[-16:], axis=0), axis=2).mean() * 1000
    stretch = (np.linalg.norm(pos[:, edges[:, 0]] - pos[:, edges[:, 1]], axis=2) / rest_len).max()
    assert late < .5, f'{preset}: still moving {late:.3f} mm/frame after settling'
    assert stretch < 1.5, f'{preset}: edges stretched {stretch:.2f}x'
    assert pos[-1, :, 2].min() > -.005, f'{preset}: fell through the floor'
    print(f'{preset}: late {late:.3f} mm/frame, max stretch {stretch:.3f}')
    scene.frame_set(1)

print('QC_TEST PASS self-gap safeguard and settled leather presets')
