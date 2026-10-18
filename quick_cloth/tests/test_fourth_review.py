"""Regressions from the review following bdbe9c9."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from bootstrap import addon, mesh, bpy
from quick_cloth import baking

scene = bpy.context.scene
garment = mesh()
p = addon.initialize_setup(garment, scene)
p.settle_frames = 0
p.frame_end = 2
p.quality_mode = 'PREVIEW'
bpy.ops.quick_cloth.simulate()

body = mesh('NlaCollider')
bpy.ops.object.modifier_add(type='COLLISION')
body.location.x = 3
body.keyframe_insert(data_path='location', frame=1)
body.keyframe_insert(data_path='location', frame=3)
action = body.animation_data.action
track = body.animation_data.nla_tracks.new()
strip = track.strips.new('Move', 1, action)
body.animation_data.action = None
bpy.context.view_layer.objects.active = garment
scene.frame_set(1)
bpy.ops.quick_cloth.bake()
original_signature = p.bake_signature
assert original_signature == baking.signature(scene, garment)
strip.mute = True
scene.frame_set(2)
assert body.location.x == 0
assert original_signature != baking.signature(scene, garment)
bpy.ops.quick_cloth.validate_bake()
assert baking.state(bpy.context, garment) == 'DIRTY'
strip.mute = False
scene.frame_set(1)
assert original_signature == baking.signature(scene, garment)

# Adjacent playback controls must be represented, too.
for owner, key, value in ((body.animation_data, 'use_nla', False),
                          (track, 'is_solo', True),
                          (strip, 'action_frame_start', 2.0)):
    before = baking.signature(scene, garment)
    previous = getattr(owner, key)
    setattr(owner, key, value)
    assert before != baking.signature(scene, garment), key
    setattr(owner, key, previous)
strip.use_animated_influence = True
strip.influence = .2
strip.keyframe_insert(data_path='influence', frame=1)
strip.influence = .8
strip.keyframe_insert(data_path='influence', frame=3)
scene.frame_set(1)
before = baking.signature(scene, garment)
scene.frame_set(2)
assert before == baking.signature(scene, garment), 'Animated strip control is frame dependent'
strip.mute = True
scene.frame_set(1)
before = baking.signature(scene, garment)
body.location.x = 10
assert before != baking.signature(scene, garment), 'Muted NLA hides authored transforms'

legacy = mesh('GravityOutsidePanelRange')
mod = addon.ensure_cloth_modifier(legacy)
mod.settings.effector_weights.gravity = 2
before = dict(legacy.quick_cloth.items())
try:
    addon.initialize_setup(legacy, scene, adopt=True)
    raise AssertionError('Lossy gravity adoption allowed')
except ValueError as exc:
    assert 'gravity_influence' in str(exc)
assert dict(legacy.quick_cloth.items()) == before
assert mod.settings.effector_weights.gravity == 2
assert not legacy.quick_cloth.setup_id
mod.settings.effector_weights.gravity = .4
adopted = addon.initialize_setup(legacy, scene, adopt=True)
addon.configure_cloth_from_props(mod, adopted)
assert abs(mod.settings.effector_weights.gravity - .4) < 1e-6
print('QC_TEST PASS NLA mute invalidates real bake; gravity adoption is lossless or rejected')
