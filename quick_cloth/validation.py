"""Context-light preflight shared by setup and baking."""
import math


def editable(data):
    if data is None:
        return False
    override = getattr(data, 'override_library', None)
    return (getattr(data, 'is_editable', data.library is None or override is not None)
            and not (override and getattr(override, 'is_system_override', False)))


def geometry_issues(obj, depsgraph=None):
    errors, warnings = [], []
    if obj is None or obj.type != 'MESH':
        return ['Select a mesh garment'], []
    if not editable(obj) or not editable(obj.data):
        errors.append('Garment object and mesh must be editable')
    if abs(obj.matrix_world.determinant()) < 1e-12:
        errors.append('Garment has a singular transform (zero scale)')
    scale = obj.matrix_world.to_scale()
    if min(scale) < 0 or max(abs(v) for v in scale) - min(abs(v) for v in scale) > 1e-5:
        warnings.append('Nonuniform or negative world scale: check physical clearances; transforms were not applied')
    data = obj.data
    if not data.vertices or not data.polygons:
        errors.append('Garment needs vertices and faces; an empty or edge-only mesh cannot simulate cloth')
    if any(not math.isfinite(c) for v in data.vertices for c in v.co):
        errors.append('Mesh has nonfinite coordinates')
    if any(p.area < 1e-12 for p in data.polygons):
        errors.append('Mesh contains zero-area faces; repair them before simulation')
    for mod in obj.modifiers:
        if mod.type == 'CLOTH':
            break
        if not mod.show_viewport:
            continue
        if mod.type in {'NODES', 'REMESH', 'BUILD', 'MESH_SEQUENCE_CACHE', 'FLUID'}:
            errors.append(f"Unsupported pre-cloth topology source '{mod.name}': use a stable mesh proxy")
        if mod.type == 'ARMATURE' and mod.object is None:
            errors.append(f"Armature '{mod.name}' has no rig target")
        if mod.type == 'ARMATURE' and not mod.use_vertex_groups:
            warnings.append('Envelope-only rig: choose attachment weights explicitly')
    if data.users > 1:
        warnings.append('Mesh data is shared; make it single-user before editing pin weights')
    if len(obj.users_scene) > 1:
        errors.append('Garment is shared across scenes; use a single-scene object copy for independent simulation')
    if len(data.vertices) > 100000:
        warnings.append('More than 100,000 simulation vertices: consider a lower-resolution proxy')
    return errors, warnings


def contact_warnings(context, obj, body):
    """Current evaluated pose only; not a continuous collision certificate."""
    if not body or body.type != 'MESH':
        return []
    from mathutils.bvhtree import BVHTree
    deps = context.evaluated_depsgraph_get()
    source = obj.evaluated_get(deps)
    target = body.evaluated_get(deps)
    points = [target.matrix_world @ v.co for v in target.data.vertices]
    faces = [tuple(f.vertices) for f in target.data.polygons]
    if not points or not faces:
        return [f'{body.name}: evaluated collider has no surface']
    tree = BVHTree.FromPolygons(points, faces)
    source_points = [source.matrix_world @ v.co for v in source.data.vertices]
    source_tree = BVHTree.FromPolygons(source_points, [tuple(f.vertices) for f in source.data.polygons])
    if source_tree.overlap(tree):
        return ['Current evaluated cloth/body surfaces overlap; inspect intersections before delivery baking']
    return []


def pin_coverage(obj, name):
    group = obj.vertex_groups.get(name)
    if not group:
        return 0, len(obj.data.vertices)
    pinned = sum(any(g.group == group.index and g.weight > 0 for g in v.groups)
                 for v in obj.data.vertices)
    return pinned, len(obj.data.vertices)


def validate_pin_edit(obj):
    if not editable(obj) or not editable(obj.data):
        raise ValueError('Object and mesh must be editable')
    if obj.data.users > 1:
        raise ValueError('Pin weights affect shared mesh data. Make the mesh single-user first.')


def depends_on(obj, target, seen=None):
    seen = set() if seen is None else seen
    if obj == target:
        return True
    if obj is None or obj.as_pointer() in seen:
        return False
    seen.add(obj.as_pointer())
    dependencies = [obj.parent]
    for mod in obj.modifiers:
        dependencies.extend(getattr(mod, name, None) for name in ('object', 'target', 'origin'))
    dependencies.extend(getattr(c, 'target', None) for c in obj.constraints)
    if obj.animation_data:
        for driver in obj.animation_data.drivers:
            dependencies.extend(t.id for v in driver.driver.variables for t in v.targets
                                if t.id and hasattr(t.id, 'modifiers'))
    return any(depends_on(d, target, seen) for d in dependencies if d is not None)
