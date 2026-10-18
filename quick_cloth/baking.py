"""Bake validation and reproducibility metadata for native cloth caches."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import bpy
from .validation import geometry_issues, pin_coverage


def cloth(obj):
    return next((m for m in obj.modifiers if m.type == 'CLOTH'), None) if obj else None


def any_baking():
    return any(m.type == 'CLOTH' and m.point_cache.is_baking for o in bpy.data.objects for m in o.modifiers)


def effective_range(scene, p):
    start, end = ((scene.frame_preview_start, scene.frame_preview_end)
                  if p.use_preview_range and scene.use_preview_range else (p.frame_start, p.frame_end))
    sim_start = start - p.settle_frames
    if start > end:
        raise ValueError('Shot start must not be after shot end')
    if sim_start < 0:
        raise ValueError(f'{p.settle_frames} settle frames require shot start at least {p.settle_frames}; '
                         'move the shot range or reduce Settle Frames. Animation was not retimed.')
    if end < 1 or end > 1048574 or sim_start > 1048574:
        raise ValueError('Simulation range exceeds Blender cache bounds (start >= 0, end 1–1048574)')
    return sim_start, end


def cache_directory():
    if not bpy.data.is_saved:
        raise ValueError('Save the .blend before using disk cache')
    path = Path(bpy.data.filepath)
    return path.parent / ('blendcache_' + path.stem)


def check_storage(obj, start, end):
    directory = cache_directory()
    target = directory if directory.exists() else directory.parent
    if not target.is_dir():
        raise ValueError(f'Cache parent directory is unavailable: {target}')
    try:
        with tempfile.TemporaryFile(dir=str(target)) as stream:
            stream.write(b'QC cache storage probe')
            stream.flush()
        # Conservative planning floor, not a complete RAM/cache size prediction.
        floor = len(obj.data.vertices) * (end - start + 1) * 32 + 16 * 1024 * 1024
        if shutil.disk_usage(target).free < floor:
            raise ValueError(f'Not enough free cache storage (planning floor {floor / 1048576:.1f} MiB): {target}')
    except OSError as exc:
        raise ValueError(f'Cache storage is not writable: {target}: {exc}') from exc
    return str(directory)


def preflight(context, obj, storage=False):
    errors, warnings = geometry_issues(obj)
    if obj is None or obj.type != 'MESH':
        return errors, warnings
    p, mod = obj.quick_cloth, cloth(obj)
    if context.mode != 'OBJECT':
        errors.append('Return to Object Mode before baking')
    if not p.setup_id or p.garment:
        errors.append('Select a configured garment, not an animation cage')
    if len(obj.users_scene) > 1:
        errors.append('Garment is shared between scenes; make a single-scene object copy before baking')
    if mod is None:
        errors.append('Set Up Cloth before baking')
    elif not mod.show_viewport or not mod.show_render or p.animator_state:
        errors.append('Exit Animator Mode and enable the Cloth modifier in viewport and render')
    if obj.name not in context.view_layer.objects or obj.hide_get() or obj.hide_viewport:
        errors.append('Garment must be visible in the active view layer')
    if any_baking():
        errors.append('Another cloth bake is running')
    try:
        start, end = effective_range(context.scene, p)
        if p.use_disk_cache and storage:
            check_storage(obj, start, end)
    except ValueError as exc:
        errors.append(str(exc))
    if p.pin_group and not obj.vertex_groups.get(p.pin_group):
        errors.append(f'Attachment group is missing: {p.pin_group}')
    pinned, total = pin_coverage(obj, p.pin_group)
    if total and pinned == total:
        warnings.append('Every vertex has attachment weights; cloth may follow the rig rigidly')
    if p.body:
        collider = next((m for m in p.body.modifiers if m.type == 'COLLISION'), None)
        if not collider or not collider.show_viewport or not p.body.collision.use:
            warnings.append(f'{p.body.name}: intended body has no enabled collision')
        elif any(m.type == 'ARMATURE' for m in list(p.body.modifiers)[list(p.body.modifiers).index(collider)+1:]):
            errors.append(f'{p.body.name}: move Collision after Armature deformation')
    if p.use_pressure:
        import bmesh
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            if any(not e.is_manifold for e in bm.edges):
                warnings.append('Pressure on open/nonmanifold geometry requires careful volume validation')
        finally:
            bm.free()
    if p.use_sewing and not any(e.is_loose for e in obj.data.edges):
        warnings.append('Sewing enabled but no loose seam edges exist')
    return errors, warnings


def free(context, obj):
    mod = cloth(obj)
    if not mod:
        raise ValueError('No cloth cache on target')
    cache = mod.point_cache
    if cache.is_baking:
        raise ValueError('Cannot free a running bake; cancel it first')
    with context.temp_override(object=obj, active_object=obj, scene=context.scene, point_cache=cache):
        result = bpy.ops.ptcache.free_bake()
    if result != {'FINISHED'} or cache.is_baked:
        raise RuntimeError('Blender did not free the target cloth cache')
    obj.quick_cloth.bake_signature = ''
    obj.quick_cloth.bake_state = 'READY'


def action_data(animation):
    if not animation:
        return None
    def action(action):
        if not action:
            return None
        curves = list(getattr(action, 'fcurves', ()))
        for layer in getattr(action, 'layers', ()):
            for strip in layer.strips:
                for bag in getattr(strip, 'channelbags', ()):
                    curves.extend(bag.fcurves)
        return [action.name, [(f.data_path, f.array_index,
                 [(tuple(k.co), tuple(k.handle_left), tuple(k.handle_right), k.interpolation) for k in f.keyframe_points])
                for f in curves]]
    return [action(animation.action),
            [(t.mute, [(s.name, s.frame_start, s.frame_end, s.scale, s.repeat, s.influence, s.blend_type, action(s.action))
                       for s in t.strips]) for t in animation.nla_tracks],
            [(d.data_path, d.driver.expression, [(v.name, [(t.id.name if t.id else '', t.data_path) for t in v.targets])
                                               for v in d.driver.variables]) for d in animation.drivers]]


def rna_values(data, excluded=()):
    values = {}
    for prop in data.bl_rna.properties:
        key = prop.identifier
        if key in excluded or key == 'rna_type' or prop.type == 'COLLECTION':
            continue
        try:
            value = getattr(data, key)
            if prop.type == 'POINTER':
                values[key] = getattr(value, 'name_full', None)
            elif prop.is_array:
                values[key] = list(value)
            elif isinstance(value, (bool, int, float, str)):
                values[key] = value
        except (AttributeError, TypeError, ValueError):
            continue
    return values


def signature(scene, obj):
    """Conservative scene signature. External driver inputs need explicit validation."""
    p = obj.quick_cloth
    excluded = {'bake_signature', 'bake_state', 'bake_error', 'bake_metadata', 'bake_needs_validation',
                'animator_state', 'cage', 'garment', 'show_fabric_detail', 'custom_steps', 'custom_collision'}
    state = [bpy.app.version_string, rna_values(p, excluded),
             (scene.render.fps, scene.render.fps_base, tuple(scene.gravity), scene.use_gravity, scene.unit_settings.scale_length)]
    for item in sorted(scene.objects, key=lambda o: o.name):
        if item.get('qc_helper') == 'cage':
            continue
        data = [item.name, item.type, item.parent.name if item.parent else None,
                action_data(item.animation_data), [rna_values(c) for c in item.constraints]]
        if not item.animation_data:
            data.append([list(row) for row in item.matrix_basis])
        if item.type == 'MESH':
            data.extend([[(tuple(v.co), [(g.group, g.weight) for g in v.groups]) for v in item.data.vertices],
                         [tuple(f.vertices) for f in item.data.polygons],
                         [g.name for g in item.vertex_groups]])
            if item.data.shape_keys:
                data.append(action_data(item.data.shape_keys.animation_data))
                data.append([(k.name, k.value, [tuple(v.co) for v in k.data]) for k in item.data.shape_keys.key_blocks])
        if item.type == 'ARMATURE':
            data.append([(b.name, [list(row) for row in b.matrix_local]) for b in item.data.bones])
            if not item.animation_data:
                data.append([(b.name, [list(row) for row in b.matrix_basis]) for b in item.pose.bones])
        data.append([rna_values(m, {'execution_time', 'persistent_uid'}) for m in item.modifiers if m.type != 'CLOTH'])
        if item.collision:
            data.append(rna_values(item.collision))
        if item.field:
            data.append(rna_values(item.field))
        state.append(data)
    mod = cloth(obj)
    if mod:
        state.extend([rna_values(mod.settings), rna_values(mod.collision_settings),
                      (mod.point_cache.frame_start, mod.point_cache.frame_end)])
    return hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()


def settings_signature(p):
    excluded = {'bake_signature', 'bake_state', 'bake_error', 'bake_metadata', 'bake_needs_validation',
                'animator_state', 'cage', 'garment', 'show_fabric_detail', 'custom_steps', 'custom_collision'}
    return hashlib.sha256(json.dumps(rna_values(p, excluded), sort_keys=True).encode()).hexdigest()


def state(context, obj):
    mod = cloth(obj)
    if not mod or not obj.quick_cloth.setup_id:
        return 'NO_SETUP'
    p = obj.quick_cloth
    if mod.point_cache.is_baking:
        return 'BAKING'
    if mod.point_cache.is_baked:
        metadata = json.loads(p.bake_metadata or '{}')
        if metadata.get('settings') != settings_signature(p) or p.bake_state == 'DIRTY':
            return 'DIRTY'
        if p.bake_needs_validation or not p.bake_signature:
            return 'NEEDS_VALIDATION'
        # Full signatures are checked explicitly; UI avoids hashing large meshes on redraw.
        return 'BAKED' if not mod.point_cache.is_outdated else 'DIRTY'
    return p.bake_state if p.bake_state in {'FAILED', 'CANCELLED'} else 'READY'


@bpy.app.handlers.persistent
def on_load(_):
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.quick_cloth.setup_id:
            obj.quick_cloth.bake_needs_validation = True


@bpy.app.handlers.persistent
def on_update(scene, depsgraph):
    # Conservative: scene evaluation can include driver inputs we cannot fingerprint.
    # Frame changes may request validation too; they never destroy an existing bake.
    if any_baking():
        return
    if any(u.is_updated_geometry or u.is_updated_transform for u in depsgraph.updates):
        for obj in scene.objects:
            mod = cloth(obj)
            if mod and mod.point_cache.is_baked and obj.quick_cloth.setup_id:
                if not obj.quick_cloth.bake_needs_validation:
                    obj.quick_cloth.bake_needs_validation = True
