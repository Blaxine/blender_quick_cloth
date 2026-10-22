"""Bake validation and reproducibility metadata for native cloth caches."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import bpy
from .validation import geometry_issues, pin_coverage, editable


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
    # Poll/draw must remain cheap on production meshes; full checks run in execute.
    errors, warnings = (geometry_issues(obj) if storage else ([], []))
    if obj is None or obj.type != 'MESH':
        return ['Select a mesh garment'], warnings
    if not editable(obj) or not editable(obj.data):
        errors.append('Garment object and mesh must be editable')
    p, mod = obj.quick_cloth, cloth(obj)
    if context.mode != 'OBJECT':
        errors.append('Return to Object Mode before baking')
    if not p.setup_id or p.garment:
        errors.append('Select a configured garment, not an animation cage')
    if p.owner != obj or not any(e.uid == p.setup_id and e.owner == obj for e in context.scene.quick_cloth_registry):
        errors.append('Duplicated/uninitialized setup identity: run Simulate Cloth to initialize this garment')
    if len(obj.users_scene) > 1:
        errors.append('Garment is shared between scenes; make a single-scene object copy before baking')
    if mod is None:
        errors.append('Set Up Cloth before baking')
    elif not mod.show_viewport or not mod.show_render or p.animator_state:
        errors.append('Exit Animator Mode and enable the Cloth modifier in viewport and render')
    if mod and mod.point_cache.use_external:
        errors.append('External/imported caches are not managed by Quick Cloth; choose a native internal cache explicitly first')
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
    if storage:
        pinned, total = pin_coverage(obj, p.pin_group)
        if total and pinned == total:
            warnings.append('Every vertex has attachment weights; cloth may follow the rig rigidly')
    if p.body:
        collider = next((m for m in p.body.modifiers if m.type == 'COLLISION'), None)
        if not collider or not collider.show_viewport or not p.body.collision.use:
            warnings.append(f'{p.body.name}: intended body has no enabled collision')
        elif any(m.type == 'ARMATURE' for m in list(p.body.modifiers)[list(p.body.modifiers).index(collider)+1:]):
            errors.append(f'{p.body.name}: move Collision after Armature deformation')
    # Validate all owned fields before a rebuild can discard the old cache.
    from . import owned_helper
    for helper, kind in ((p.wind, 'WIND'), (p.turbulence, 'TURBULENCE')):
        if owned_helper(helper, p) and (helper.field is None or helper.field.type != kind):
            errors.append(f'{helper.name}: owned force field was changed; remove and recreate it')
    if owned_helper(p.wind, p) and (p.wind.parent or p.wind.constraints):
        errors.append('Owned wind has a parent/constraint; remove it before using world-space direction')
    if p.use_wind:
        if sum(v*v for v in p.wind_direction) < 1e-12:
            errors.append('Wind direction cannot be zero')
    if p.use_pressure and storage:
        import bmesh
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            if any(not e.is_manifold for e in bm.edges):
                warnings.append('Pressure on open/nonmanifold geometry requires careful volume validation')
        finally:
            bm.free()
    if storage and p.use_sewing and not any(e.is_loose for e in obj.data.edges):
        warnings.append('Sewing enabled but no loose seam edges exist')
    return errors, warnings


def free(context, obj):
    if not editable(obj) or not obj.quick_cloth.setup_id:
        raise ValueError('Select an editable, adopted garment before freeing its cache')
    if not any(e.uid == obj.quick_cloth.setup_id and e.owner == obj for e in context.scene.quick_cloth_registry):
        raise ValueError('Initialize the duplicated setup before managing its cache')
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
    def curves_data(curves):
        return [(f.data_path, f.array_index, f.mute, f.extrapolation,
                 [(tuple(k.co), tuple(k.handle_left), tuple(k.handle_right), k.interpolation, k.easing) for k in f.keyframe_points],
                 [rna_values(m) for m in f.modifiers], [tuple(k.co) for k in f.sampled_points])
                for f in curves]

    def action(action):
        if not action:
            return None
        curves = list(getattr(action, 'fcurves', ()))
        for layer in getattr(action, 'layers', ()):
            for strip in layer.strips:
                for bag in getattr(strip, 'channelbags', ()):
                    curves.extend(bag.fcurves)
        return [action.name, curves_data(curves)]

    def strip_data(strip):
        # Animated controls are represented by their curves, not the value at
        # the current timeline position. Selection is UI state only.
        excluded = {'select'}
        if not strip.use_animated_time or any(f.data_path == 'strip_time' and not f.mute for f in strip.fcurves):
            excluded.add('strip_time')
        if strip.use_animated_influence:
            excluded.add('influence')
        return [rna_values(strip, excluded), action(strip.action),
                curves_data(strip.fcurves), [rna_values(m) for m in strip.modifiers],
                [strip_data(child) for child in strip.strips]]

    return [rna_values(animation), action(animation.action),
            [(t.mute, t.is_solo, [strip_data(s) for s in t.strips]) for t in animation.nla_tracks],
            [(d.data_path, d.mute, d.driver.type, d.driver.expression, d.driver.use_self, [rna_values(m) for m in d.modifiers], [(v.name, v.type, [rna_values(t, {'is_fallback_used'}) for t in v.targets])
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
            elif getattr(prop, 'is_array', False):
                values[key] = list(value)
            elif isinstance(value, (bool, int, float, str)):
                values[key] = value
        except (AttributeError, TypeError, ValueError):
            continue
    return values


def id_property_value(value):
    """Plain JSON form of a custom property.

    Group/array reprs embed memory addresses (e.g. other add-ons' registered
    settings such as Cycles), which would change the signature on every reload.
    """
    if isinstance(value, bpy.types.ID):
        return value.name_full
    if hasattr(value, 'to_dict'):
        value = value.to_dict()
    elif hasattr(value, 'to_list'):
        value = value.to_list()
    if isinstance(value, dict):
        return {str(k): id_property_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [id_property_value(v) for v in value]
    return value


def static_transform_channels(item, animation, prefix=''):
    """Hash authored channels not driven by actions, NLA, or drivers.

    Evaluated matrices change with timeline position; omitting the whole matrix
    for any animated object also loses unrelated, unanimated channel edits.
    """
    curves = []
    if animation:
        actions = [animation.action]
        if animation.use_nla:
            solo = any(track.is_solo for track in animation.nla_tracks)
            actions.extend(strip.action for track in animation.nla_tracks
                           if not track.mute and (not solo or track.is_solo)
                           for strip in track.strips if not strip.mute)
        curves.extend(animation.drivers)
        for action in actions:
            if action is None:
                continue
            curves.extend(getattr(action, 'fcurves', ()))
            for layer in getattr(action, 'layers', ()):
                for strip in layer.strips:
                    for bag in getattr(strip, 'channelbags', ()):
                        curves.extend(bag.fcurves)
    animated = {(c.data_path, c.array_index) for c in curves if not c.mute}
    result = {'rotation_mode': item.rotation_mode}
    for key in ('location', 'rotation_euler', 'rotation_quaternion', 'rotation_axis_angle',
                'scale', 'delta_location', 'delta_rotation_euler', 'delta_rotation_quaternion', 'delta_scale'):
        if hasattr(item, key):
            result[key] = [(i, value) for i, value in enumerate(getattr(item, key))
                           if (prefix + key, i) not in animated]
    return result


def signature(scene, obj):
    """Conservative scene signature. External driver inputs need explicit validation."""
    p = obj.quick_cloth
    excluded = {'bake_signature', 'bake_state', 'bake_error', 'bake_metadata', 'bake_needs_validation',
                'animator_state', 'cage', 'garment', 'show_fabric_detail', 'custom_steps', 'custom_collision', 'diagnostics', 'coverage_text'}
    state = [bpy.app.version_string, rna_values(p, excluded),
             (scene.render.fps, scene.render.fps_base, tuple(scene.gravity), scene.use_gravity, scene.unit_settings.scale_length),
             effective_range(scene, p)]
    state.append({k: id_property_value(scene[k]) for k in scene.keys()
                  if k not in {'quick_cloth', 'quick_cloth_registry'}})
    for item in sorted(scene.objects, key=lambda o: o.name):
        if item.get('qc_helper') == 'cage':
            continue
        data = [item.name, item.type, item.parent.name if item.parent else None,
                sorted(c.name for c in item.users_collection),
                {k: id_property_value(item[k]) for k in item.keys() if k != 'quick_cloth' and not k.startswith('qc_')},
                action_data(item.animation_data), [rna_values(c) for c in item.constraints]]
        data.append([item.parent_type, item.parent_bone, list(item.parent_vertices),
                     [list(row) for row in item.matrix_parent_inverse]])
        data.append(static_transform_channels(item, item.animation_data))
        if item.type == 'MESH':
            data.extend([[(tuple(v.co), [(g.group, g.weight) for g in v.groups]) for v in item.data.vertices],
                         [tuple(f.vertices) for f in item.data.polygons],
                         [g.name for g in item.vertex_groups]])
            if item.data.shape_keys:
                data.append(action_data(item.data.shape_keys.animation_data))
                data.append([(k.name, k.value, [tuple(v.co) for v in k.data]) for k in item.data.shape_keys.key_blocks])
        if item.type == 'ARMATURE':
            data.append([(b.name, [list(row) for row in b.matrix_local]) for b in item.data.bones])
            data.append([(b.name, [rna_values(c) for c in b.constraints]) for b in item.pose.bones])
            data.append([(b.name, static_transform_channels(b, item.animation_data, b.path_from_id() + '.'))
                         for b in item.pose.bones])
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
                'animator_state', 'cage', 'garment', 'show_fabric_detail', 'custom_steps', 'custom_collision', 'diagnostics', 'coverage_text'}
    return hashlib.sha256(json.dumps(rna_values(p, excluded), sort_keys=True).encode()).hexdigest()


def state(context, obj):
    mod = cloth(obj)
    if not mod or not obj.quick_cloth.setup_id:
        return 'NO_SETUP'
    p = obj.quick_cloth
    if mod.point_cache.is_baking:
        return 'BAKING'
    if mod.point_cache.is_baked:
        try:
            metadata = json.loads(p.bake_metadata or '{}')
        except (ValueError, TypeError):
            return 'NEEDS_VALIDATION'
        if not isinstance(metadata, dict):
            return 'NEEDS_VALIDATION'
        try:
            if effective_range(context.scene, p) != (mod.point_cache.frame_start, mod.point_cache.frame_end):
                return 'DIRTY'
        except ValueError:
            return 'DIRTY'
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
