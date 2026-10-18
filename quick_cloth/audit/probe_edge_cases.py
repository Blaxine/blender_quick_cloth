"""Read-only source audit; run in a disposable --factory-startup Blender process.

The missing operator declaration is repaired IN MEMORY after checking the stock
import, solely to expose downstream behavior. No source or .blend is saved.
"""
import ast
import json
from pathlib import Path
import bpy

source = (Path(__file__).resolve().parents[1] / '__init__.py').read_text(encoding='utf-8')
results = {'blender': bpy.app.version_string, 'in_memory_repair': 'Insert missing QC_OT_make_colliders class declaration', 'observations': {}}
out = results['observations']
try:
    exec(compile(source, '__init__.py', 'exec'), {'__name__': 'qc_stock_probe'})
    out['stock_import'] = 'success'
except Exception as exc:
    out['stock_import'] = f'{type(exc).__name__}: {exc}'
marker = '    ' + chr(34) * 3 + 'Add a tuned Collision modifier to all selected objects'
assert source.count(marker) == 1
source = source.replace(marker, 'class QC_OT_make_colliders(Operator):\n' + marker)
ns = {'__name__': 'qc_audit_probe'}
exec(compile(source, '__init__.py', 'exec'), ns)
ns['register']()
scene = bpy.context.scene
props = scene.quick_cloth
obj = bpy.context.active_object
mod = ns['ensure_cloth_modifier'](obj)

def observe(name, action):
    try:
        out[name] = action()
    except Exception as exc:
        out[name] = f'{type(exc).__name__}: {exc}'

def quality():
    props.quality_mode = 'PREVIEW'
    ns['configure_cloth_from_props'](mod, props, True)
    before = mod.settings.quality
    props.quality_mode = 'FINAL'
    return {'preview_steps': before, 'after_final_selection': mod.settings.quality, 'authored_steps': props.quality_steps}
observe('quality_toggle', quality)

def disabled_collisions():
    mod.collision_settings.use_collision = False
    ns['configure_cloth_from_props'](mod, props)
    return {'panel_use_collision_objects': props.use_collision_objects, 'modifier_use_collision': mod.collision_settings.use_collision}
observe('disabled_collisions_remain_disabled', disabled_collisions)

def ranges():
    ns['cache_hygiene'](bpy.context, scene, mod.point_cache, -14, 20)
    return {'requested_start': -14, 'requested_end': 20, 'actual_start': mod.point_cache.frame_start,
            'actual_end': mod.point_cache.frame_end, 'scene_start': scene.frame_start,
            'scene_end': scene.frame_end, 'playhead': scene.frame_current}
observe('negative_preroll_and_short_range', ranges)

def multiple_modifiers():
    arm1 = obj.modifiers.new('Arm1', 'ARMATURE')
    arm2 = obj.modifiers.new('Arm2', 'ARMATURE')
    selected = ns['find_cloth_modifier'](obj).name
    ns['ensure_stack_order'](obj)
    result = {'configured_modifier': selected, 'stack': [(m.name, m.type) for m in obj.modifiers]}
    for m in (arm1, arm2):
        obj.modifiers.remove(m)
    return result
observe('multiple_armature_stack', multiple_modifiers)

def cage_checks():
    cage = ns['build_or_update_cage'](bpy.context, obj, 0.2)
    original_count = len(cage.data.vertices)
    old_name = obj.name
    obj.name = 'RenamedGarment'
    lost_pair = ns['find_garment_for_cage'](cage) is None
    obj.name = old_name
    obj.data.vertices[0].co.x += 7
    ns['build_or_update_cage'](bpy.context, obj, 0.3)
    stale = tuple(cage.data.vertices[0].co) != tuple(obj.data.vertices[0].co)
    return {'hide_render': cage.hide_render, 'vertices_before_decimation': original_count,
            'rename_loses_pair': lost_pair, 'reuse_keeps_old_geometry': stale}
observe('cage_lifecycle', cage_checks)

def animator_plain():
    plain = bpy.data.objects.new('Plain', bpy.data.meshes.new('Plain'))
    bpy.context.collection.objects.link(plain)
    bpy.context.view_layer.objects.active = plain
    enter = bpy.ops.quick_cloth.enter_animator_mode.poll()
    result = bpy.ops.quick_cloth.enter_animator_mode()
    return {'entry_allowed': enter, 'entry_result': sorted(result), 'exit_allowed': bpy.ops.quick_cloth.exit_animator_mode.poll(), 'garment_hidden': plain.hide_get()}
observe('animator_without_cloth', animator_plain)
bpy.context.view_layer.objects.active = obj

def wind():
    return ns['ensure_wind_rig'](bpy.context, props).name
observe('wind_creation', wind)

def hidden_bake_poll():
    mod.show_viewport = False
    return bpy.ops.quick_cloth.bake.poll()
observe('bake_allowed_with_muted_cloth', hidden_bake_poll)

def overwrite_collision():
    obstacle = bpy.data.objects.new('Obstacle', bpy.data.meshes.new('Obstacle'))
    scene.collection.objects.link(obstacle)
    obstacle.modifiers.new('AuthoredCollision', 'COLLISION')
    obstacle.collision.thickness_outer = 0.004
    obstacle.collision.damping = 0.7
    ns['make_collider'](obstacle)
    return {'thickness_outer': obstacle.collision.thickness_outer, 'damping': obstacle.collision.damping}
observe('existing_collider_values_overwritten', overwrite_collision)

def preset_remaining():
    props.use_pressure = True
    props.pressure_force = 33
    props.preset = 'COTTON'
    return {'pressure_enabled_after_cotton': props.use_pressure, 'pressure_force': props.pressure_force}
observe('preset_retains_nonpreset_settings', preset_remaining)

def ranges_rna():
    values = {}
    for owner, fields in ((scene, ('frame_start', 'frame_end')), (mod.point_cache, ('frame_start', 'frame_end')), (mod.settings, ('pin_stiffness', 'shrink_min'))):
        for name in fields:
            p = owner.bl_rna.properties[name]
            values[f'{owner.bl_rna.identifier}.{name}'] = [p.hard_min, p.hard_max]
    return values
observe('rna_ranges', ranges_rna)
print('QC_AUDIT_JSON=' + json.dumps(results, sort_keys=True))
