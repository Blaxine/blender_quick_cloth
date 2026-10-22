"""Build animator_demo.blend: a walking rigged mannequin wearing a Quick Cloth cape.

Run from the repository root:
    blender --background --factory-startup --python demo/make_animator_demo.py

The add-on is loaded from ../quick_cloth, so the file works with the installed
extension too (settings live under Object.quick_cloth either way).
"""
import importlib.util
import math
import sys
from pathlib import Path

import bpy

here = Path(__file__).resolve().parent
root = here.parent / 'quick_cloth'
spec = importlib.util.spec_from_file_location('quick_cloth', root / '__init__.py',
                                              submodule_search_locations=[str(root)])
addon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = addon
spec.loader.exec_module(addon)
addon.register()

FRAMES = 120
scene = bpy.context.scene
for obj in list(scene.objects):
    if obj.type == 'MESH':
        bpy.data.objects.remove(obj)
scene.frame_start, scene.frame_end = 1, FRAMES
scene.render.fps = 24


def activate(obj):
    for other in bpy.context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


# --- Rig ---------------------------------------------------------------------
# (name, head, tail, parent). The mannequin faces -Y; the cape hangs behind it.
BONES = [
    ('root', (0, 0, 0), (0, .3, 0), None),
    ('hips', (0, 0, .95), (0, 0, 1.08), 'root'),
    ('spine', (0, 0, 1.08), (0, 0, 1.3), 'hips'),
    ('chest', (0, 0, 1.3), (0, 0, 1.52), 'spine'),
    ('head', (0, 0, 1.52), (0, 0, 1.82), 'chest'),
    ('upper_arm.L', (.24, 0, 1.46), (.26, 0, 1.18), 'chest'),
    ('forearm.L', (.26, 0, 1.18), (.27, 0, .92), 'upper_arm.L'),
    ('upper_arm.R', (-.24, 0, 1.46), (-.26, 0, 1.18), 'chest'),
    ('forearm.R', (-.26, 0, 1.18), (-.27, 0, .92), 'upper_arm.R'),
    ('thigh.L', (.1, 0, .95), (.1, 0, .52), 'hips'),
    ('shin.L', (.1, 0, .52), (.1, 0, .08), 'thigh.L'),
    ('thigh.R', (-.1, 0, .95), (-.1, 0, .52), 'hips'),
    ('shin.R', (-.1, 0, .52), (-.1, 0, .08), 'thigh.R'),
]
arm_data = bpy.data.armatures.new('Rig')
rig = bpy.data.objects.new('Rig', arm_data)
scene.collection.objects.link(rig)
arm_data.display_type = 'STICK'
rig.show_in_front = True
activate(rig)
bpy.ops.object.mode_set(mode='EDIT')
for name, head, tail, parent in BONES:
    bone = arm_data.edit_bones.new(name)
    bone.head, bone.tail = head, tail
    if parent:
        bone.parent = arm_data.edit_bones[parent]
        bone.use_connect = name not in {'hips', 'upper_arm.L', 'upper_arm.R', 'thigh.L', 'thigh.R'}
bpy.ops.object.mode_set(mode='OBJECT')

# --- Mannequin: rigid segments, one bone each ---------------------------------
parts = []


def segment(bone, kind, location, scale, rotation=(0, 0, 0)):
    if kind == 'sphere':
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1, location=location)
    else:
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=1, depth=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    group = obj.vertex_groups.new(name=bone)
    group.add(range(len(obj.data.vertices)), 1.0, 'REPLACE')
    parts.append(obj)


segment('hips', 'cyl', (0, 0, 1.0), (.17, .12, .14))
segment('spine', 'cyl', (0, 0, 1.19), (.15, .11, .24))
segment('chest', 'cyl', (0, 0, 1.4), (.19, .12, .22))
segment('head', 'sphere', (0, 0, 1.66), (.1, .11, .13))
for side, x in (('L', 1), ('R', -1)):
    segment(f'upper_arm.{side}', 'cyl', (.25 * x, 0, 1.32), (.05, .05, .28))
    segment(f'forearm.{side}', 'cyl', (.265 * x, 0, 1.05), (.042, .042, .26))
    segment(f'thigh.{side}', 'cyl', (.1 * x, 0, .735), (.075, .075, .43))
    segment(f'shin.{side}', 'cyl', (.1 * x, 0, .3), (.06, .06, .44))
activate(parts[0])
for obj in parts:
    obj.select_set(True)
bpy.ops.object.join()
body = bpy.context.object
body.name = 'Mannequin'
bpy.ops.object.shade_smooth()
body.parent = rig
body.modifiers.new('Armature', 'ARMATURE').object = rig

# --- Walk cycle ----------------------------------------------------------------
pose = rig.pose.bones
for bone in pose:
    bone.rotation_mode = 'XYZ'
STEP = 30                                         # frames per stride
SPEED = 1.1 / STEP                                # metres per frame
x = y = 0.0
for frame in range(1, FRAMES + 1):
    phase = 2 * math.pi * (frame - 1) / (2 * STEP)
    swing = math.sin(phase)
    # Turn left over frames 60-100 so the cape swings sideways too; walk where it faces.
    heading = math.radians(70) * min(max((frame - 60) / 40, 0), 1)
    if frame > 1:
        x, y = x + SPEED * math.sin(heading), y - SPEED * math.cos(heading)
    if (frame - 1) % 5:
        continue
    rig.location = (x, y, 0)
    rig.rotation_euler = (0, 0, heading)
    rig.keyframe_insert('location', frame=frame)
    rig.keyframe_insert('rotation_euler', frame=frame)
    pose['hips'].location = (0, .03 * abs(math.cos(phase)), 0)
    pose['chest'].rotation_euler = (0, math.radians(8) * swing, 0)
    pose['upper_arm.L'].rotation_euler = (math.radians(35) * swing, 0, 0)
    pose['upper_arm.R'].rotation_euler = (math.radians(-35) * swing, 0, 0)
    pose['forearm.L'].rotation_euler = (math.radians(-20 - 15 * swing), 0, 0)
    pose['forearm.R'].rotation_euler = (math.radians(-20 + 15 * swing), 0, 0)
    pose['thigh.L'].rotation_euler = (math.radians(-30) * swing, 0, 0)
    pose['thigh.R'].rotation_euler = (math.radians(30) * swing, 0, 0)
    pose['shin.L'].rotation_euler = (math.radians(25 * max(swing, 0)), 0, 0)
    pose['shin.R'].rotation_euler = (math.radians(25 * max(-swing, 0)), 0, 0)
    for bone in pose:
        bone.keyframe_insert('rotation_euler', frame=frame)
    pose['hips'].keyframe_insert('location', frame=frame)
scene.frame_set(1)

# --- Cape ----------------------------------------------------------------------
bpy.ops.mesh.primitive_grid_add(x_subdivisions=24, y_subdivisions=38, size=1,
                                location=(0, .2, 1.0), rotation=(math.radians(90), 0, 0))
cape = bpy.context.object
cape.name = 'Cape'
cape.scale = (.62, .95, 1)
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
top = max((cape.matrix_world @ v.co).z for v in cape.data.vertices)
collar = [v.index for v in cape.data.vertices if (cape.matrix_world @ v.co).z > top - .03]
# The whole cape rides on the chest bone (so the Animator Mode stand-in follows the walk);
# only the collar is pinned, everything below it is free cloth.
cape.vertex_groups.new(name='chest').add(range(len(cape.data.vertices)), 1.0, 'REPLACE')
cape.vertex_groups.new(name='Pins').add(collar, 1.0, 'REPLACE')
cape.parent = rig
cape.matrix_parent_inverse = rig.matrix_world.inverted()
cape.modifiers.new('Armature', 'ARMATURE').object = rig
bpy.ops.object.shade_smooth()

bpy.ops.mesh.primitive_plane_add(size=12, location=(0, -2, 0))
ground = bpy.context.object
ground.name = 'Ground'

# --- Quick Cloth -------------------------------------------------------------
activate(cape)
p = addon.initialize_setup(cape, scene)
p.preset = 'COTTON'
p.pin_group = 'Pins'
p.body = body
p.frame_start, p.frame_end = 1, FRAMES
p.quality_mode = 'PREVIEW'
assert bpy.ops.quick_cloth.body_collider() == {'FINISHED'}
activate(ground)
assert bpy.ops.quick_cloth.make_colliders() == {'FINISHED'}
activate(cape)
assert bpy.ops.quick_cloth.simulate() == {'FINISHED'}

# --- Camera and notes --------------------------------------------------------
camera = scene.camera
if camera:
    camera.location = (6.5, -2.0, 1.9)
    camera.data.lens = 35
    track = camera.constraints.new('TRACK_TO')
    track.target, track.subtarget = rig, 'spine'
# Open with the sidebar showing and the view on the mannequin.
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            space.show_region_ui = True
            space.region_3d.view_location = (0, -1.2, 1.0)
            space.region_3d.view_distance = 5.5
text = bpy.data.texts.new('READ ME - Quick Cloth demo')
text.write("""Quick Cloth: Animator Mode demo

A walking mannequin (Rig, 13 bones) wears a cotton Cape pinned to the chest bone.
Quick Cloth is already set up on the Cape at Preview quality; nothing is baked.

1. Select Cape and open the Quick Cloth tab in the 3D view sidebar (N).
2. Press Play from frame 1 to watch the live cloth. It is slow: every frame is solved.
3. Open Animator Mode and press Start Animator Mode. The cape is hidden and a light
   stand-in that follows the rig takes its place, so playback runs at full speed.
4. Select Rig, go to Pose Mode and change the walk: rotate bones, insert keys.
5. Select the stand-in (or the Cape) and press Exit Animator Mode.
6. In step 4 of the panel, press Bake. Try Medium or High for the final look.
""")

out = here / 'animator_demo.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
print('QC_DEMO saved', out)
