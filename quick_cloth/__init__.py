"""Quick Cloth: per-garment setup, explicit cache rebuilds and native cloth baking.

Legacy Blender 4.1 and native extension packaging for 4.2+.
See README.md and docs/RELEASE_STATUS.md for tested versions and limitations.
"""

bl_info = {
    "name": "Quick Cloth",
    "author": "Quick Physics Tools",
    "version": (1, 1, 0),
    "blender": (4, 1, 0),
    "location": "3D Viewport > Sidebar (N) > Quick Cloth",
    "description": "One-click preset-driven cloth simulation for animators",
    "category": "Physics",
}

# ---------------------------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------------------------

import bpy
import uuid
import json
import textwrap
from datetime import datetime, timezone
from . import baking
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import AddonPreferences, Operator, Panel, PropertyGroup, UIList
from mathutils import Vector
from .validation import (geometry_issues, pin_coverage, validate_pin_edit, depends_on, editable, contact_warnings,
                         short_edge_length, safe_self_gap)
from .quality import resolve as resolve_quality, selection_update as quality_update, values_update as quality_values_update

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

WIND_EMPTY_NAME = "QC_Wind"
TURBULENCE_EMPTY_NAME = "QC_Wind_Turbulence"

# Animator Mode: lightweight stand-in cages are named by convention so the
# garment<->cage link survives file saves with zero custom data.
CAGE_PREFIX = "QC_Cage_"

# Names accepted for the pin vertex group (normalized: lowercase, no
# spaces/underscores/dashes). Same fuzzy-matcher pattern as Quick Break's
# find_impact_group.
PIN_GROUP_ALIASES = {"pin", "pins", "pingroup", "pinned"}
PIN_GROUP_CANONICAL = "pin"

# ---------------------------------------------------------------------------
# PRESETS + apply_preset
# ---------------------------------------------------------------------------
# Every preset sets EVERY key below, so switching presets is deterministic.
# Keys match QuickClothProps attribute names 1:1 (verified by the build's
# regex self-check).

PRESETS = {
    "SIMPLE": {
        "mass": 0.30,
        "tension_stiffness": 15.0,
        "compression_stiffness": 15.0,
        "shear_stiffness": 5.0,
        "bending_stiffness": 0.5,
        "tension_damping": 5.0,
        "compression_damping": 5.0,
        "shear_damping": 5.0,
        "bending_damping": 0.5,
        "air_damping": 1.0,
        "quality_steps": 5,
        "collision_quality": 3,
        "time_scale": 1.0,
        "use_self_collision": False,
        "self_distance": 0.015,
        "object_distance": 0.015,
        "fit_tightness": 0.0,
        "use_sewing": False,
        "use_internal_springs": False,
        "internal_stiffness": 5.0,
    },
    "COTTON": {
        "mass": 0.28,
        "tension_stiffness": 16.0,
        "compression_stiffness": 12.0,
        "shear_stiffness": 5.0,
        "bending_stiffness": 0.6,
        "tension_damping": 5.0,
        "compression_damping": 5.0,
        "shear_damping": 5.0,
        "bending_damping": 0.5,
        "air_damping": 1.0,
        "quality_steps": 8,
        "collision_quality": 3,
        "time_scale": 1.0,
        "use_self_collision": True,
        "self_distance": 0.005,
        "object_distance": 0.015,
        "fit_tightness": 0.0,
        "use_sewing": False,
        "use_internal_springs": False,
        "internal_stiffness": 5.0,
    },
    "POLYESTER": {
        "mass": 0.20,
        "tension_stiffness": 28.0,
        "compression_stiffness": 22.0,
        "shear_stiffness": 9.0,
        "bending_stiffness": 1.8,
        "tension_damping": 8.0,
        "compression_damping": 8.0,
        "shear_damping": 6.0,
        "bending_damping": 1.0,
        "air_damping": 1.4,
        "quality_steps": 10,
        "collision_quality": 3,
        "time_scale": 1.0,
        "use_self_collision": True,
        "self_distance": 0.005,
        "object_distance": 0.015,
        "fit_tightness": 0.0,
        "use_sewing": False,
        "use_internal_springs": False,
        "internal_stiffness": 5.0,
    },
    "COUCH_LEATHER": {
        "mass": 0.85,
        "tension_stiffness": 80.0,
        "compression_stiffness": 65.0,
        "shear_stiffness": 45.0,
        "bending_stiffness": 90.0,
        "tension_damping": 25.0,
        "compression_damping": 25.0,
        "shear_damping": 20.0,
        "bending_damping": 4.0,    # higher values jitter on this mass (measured in 5.2)
        "air_damping": 1.0,
        "quality_steps": 15,
        "collision_quality": 4,
        "time_scale": 0.9,  # a touch slow-motion = reads as heavy
        "use_self_collision": False,
        "self_distance": 0.005,
        "object_distance": 0.015,
        "fit_tightness": 0.0,
        "use_sewing": False,
        "use_internal_springs": True,   # volume preservation for thick hide
        "internal_stiffness": 5.0,
    },
    "LEATHER_COAT": {
        "mass": 0.50,
        "tension_stiffness": 60.0,
        "compression_stiffness": 45.0,
        "shear_stiffness": 25.0,
        "bending_stiffness": 30.0,
        "tension_damping": 15.0,
        "compression_damping": 15.0,
        "shear_damping": 12.0,
        "bending_damping": 2.0,     # higher values jitter on this mass (measured in 5.2)
        "air_damping": 1.2,
        "quality_steps": 12,
        "collision_quality": 4,
        "time_scale": 1.0,
        "use_self_collision": True,
        "self_distance": 0.005,
        "object_distance": 0.015,
        "fit_tightness": 0.0,
        "use_sewing": False,
        "use_internal_springs": False,
        "internal_stiffness": 5.0,
    },
    "LATEX": {
        "mass": 0.35,
        "tension_stiffness": 8.0,
        "compression_stiffness": 12.0,
        "shear_stiffness": 6.0,
        "bending_stiffness": 0.25,
        "tension_damping": 2.0,
        "compression_damping": 4.0,
        "shear_damping": 3.0,
        "bending_damping": 0.2,
        "air_damping": 0.8,
        "quality_steps": 14,
        "collision_quality": 5,
        "time_scale": 1.0,
        "use_self_collision": True,   # mandatory for skin-tight fits
        "self_distance": 0.004,
        "object_distance": 0.015,
        "fit_tightness": 0.12,        # positive shrink tightens onto the body
        "use_sewing": True,
        "use_internal_springs": False,
        "internal_stiffness": 5.0,
    },
    "STRETCH_DENIM": {
        "mass": 0.60,
        "tension_stiffness": 25.0,
        "compression_stiffness": 28.0,
        "shear_stiffness": 15.0,
        "bending_stiffness": 5.0,
        "tension_damping": 10.0,
        "compression_damping": 10.0,
        "shear_damping": 8.0,
        "bending_damping": 3.0,
        "air_damping": 1.0,
        "quality_steps": 11,
        "collision_quality": 4,
        "time_scale": 1.0,
        "use_self_collision": True,
        "self_distance": 0.005,
        "object_distance": 0.015,
        "fit_tightness": 0.04,        # light hug fit
        "use_sewing": False,
        "use_internal_springs": False,
        "internal_stiffness": 5.0,
    },
    "RIGID_DENIM": {
        "mass": 1.00,
        "tension_stiffness": 40.0,
        "compression_stiffness": 40.0,
        "shear_stiffness": 25.0,
        "bending_stiffness": 10.0,
        "tension_damping": 12.0,
        "compression_damping": 12.0,
        "shear_damping": 10.0,
        "bending_damping": 5.0,
        "air_damping": 1.0,
        "quality_steps": 12,
        "collision_quality": 4,
        "time_scale": 1.0,
        "use_self_collision": True,
        "self_distance": 0.005,
        "object_distance": 0.015,
        "fit_tightness": 0.0,
        "use_sewing": False,
        "use_internal_springs": False,
        "internal_stiffness": 5.0,
    },
    "SELVEDGE_DENIM": {
        "mass": 1.20,
        "tension_stiffness": 55.0,
        "compression_stiffness": 52.0,
        "shear_stiffness": 30.0,
        "bending_stiffness": 18.0,
        "tension_damping": 18.0,
        "compression_damping": 18.0,
        "shear_damping": 14.0,
        "bending_damping": 9.0,
        "air_damping": 1.0,
        "quality_steps": 14,
        "collision_quality": 4,
        "time_scale": 1.0,
        "use_self_collision": True,
        "self_distance": 0.005,
        "object_distance": 0.015,
        "fit_tightness": 0.0,
        "use_sewing": False,
        "use_internal_springs": False,
        "internal_stiffness": 5.0,
    },
}

PRESET_ITEMS = [
    ("SIMPLE", "Simple Cloth (default)",
     "Blender's vanilla cloth feel — light, fast to solve, no self-collision. "
     "The quick-preview fabric"),
    ("COTTON", "Cotton",
     "Shirts, t-shirts, pants, socks — soft micro-wrinkles that drape close "
     "to the body"),
    ("POLYESTER", "Polyester",
     "Polos and slacks — springier than cotton, holds its shape, slightly "
     "floaty with fewer fine wrinkles"),
    ("COUCH_LEATHER", "Couch Leather",
     "Thick upholstery leather/pleather — big heavy soft folds, almost no "
     "flutter, internal springs preserve volume"),
    ("LEATHER_COAT", "Leather Coat",
     "Rain coats and biker jackets — stiff panels that swing as a unit, soft "
     "only where they crease"),
    ("LATEX", "Latex",
     "Skin-tight latex garments — very stretchy, zero drape, tightens onto "
     "the body (positive shrink + self-collision; sewing only affects loose seam edges)"),
    ("STRETCH_DENIM", "Stretch Denim",
     "Jeans with elastane — gives at the knees, light hug fit"),
    ("RIGID_DENIM", "Cotton Rigid Denim",
     "Classic Blender denim — heavy, structured folds that hold a silhouette"),
    ("SELVEDGE_DENIM", "Selvedge Denim",
     "Raw heavyweight denim — the stiffest fabric here; boardy, tube-like "
     "folds that barely wrinkle and hold their creases"),
]


def apply_preset(self, context):
    """EnumProperty update callback.

    Writes the selected preset's full value dictionary into the
    PropertyGroup, and — if the active object already carries a cloth
    modifier — into the live modifier as well, so the viewport responds
    immediately. Presets are starting points: every slider remains editable
    afterwards.
    """
    values = PRESETS.get(self.preset)
    if values is None:
        return
    for key, value in values.items():
        if key not in {'quality_steps', 'collision_quality'}:
            setattr(self, key, value)
    self.legacy_fit = False
    quality_update(self, context)

    # Push into a live modifier if one exists on the active object.
    obj = self.id_data
    if isinstance(obj, bpy.types.Object) and obj.type == 'MESH' and self.setup_id:
        if object_is_override_locked(obj):
            return
        mod = find_cloth_modifier(obj)
        if mod is not None and not mod.point_cache.is_baked and not mod.point_cache.is_baking:
            configure_cloth_from_props(mod, self, preview=(self.quality_mode == 'PREVIEW'))


# ---------------------------------------------------------------------------
# PROPERTY GROUP
# ---------------------------------------------------------------------------

def wind_enabled_update(self, context):
    for obj, strength in ((self.wind, self.wind_strength), (self.turbulence, self.wind_turbulence)):
        if owned_helper(obj, self) and obj.field:
            obj.field.strength = strength if self.use_wind else 0


class QCSetupRef(PropertyGroup):
    uid: StringProperty()
    owner: PointerProperty(type=bpy.types.Object)


class QCColliderItem(PropertyGroup):
    object: PointerProperty(
        name='Collider', type=bpy.types.Object,
        description='A mesh the cloth hits: furniture, a floor, another body',
        poll=lambda self, obj: obj.type == 'MESH' and obj != self.id_data)


class QuickClothProps(PropertyGroup):
    """Per-garment settings; Scene settings are defaults for new setups only."""

    setup_id: StringProperty()
    owner: PointerProperty(type=bpy.types.Object)
    data_version: IntProperty(default=0)
    pin_group: StringProperty(
        name="Pin Group",
        description="Vertex group holding the pinned vertices. Pinned vertices "
                    "stick to the object or its rig; weight 1 holds fully, "
                    "lower weights hold loosely, 0 moves freely",
    )
    cage: PointerProperty(type=bpy.types.Object)
    garment: PointerProperty(type=bpy.types.Object)
    wind: PointerProperty(type=bpy.types.Object)
    turbulence: PointerProperty(type=bpy.types.Object)
    animator_state: StringProperty()
    legacy_fit: BoolProperty(default=False)
    bake_signature: StringProperty()
    bake_state: StringProperty(default='READY')
    bake_error: StringProperty()
    bake_metadata: StringProperty()
    bake_needs_validation: BoolProperty(default=False)
    custom_steps: IntProperty(default=64, min=1, max=1000)
    custom_collision: IntProperty(default=5, min=1, max=20)
    dynamic_mesh: BoolProperty(
        name='Squash & Stretch Rig',
        description='Turn on only if the rig squashes or stretches the garment: '
                    'the cloth then updates its resting shape every frame. '
                    'Normal pinned clothing does not need this',
        default=False)
    use_object_collision: BoolProperty(
        name='Collide With Objects',
        description='Let the cloth hit colliders (bodies, floors, furniture). '
                    'Turn off only for cloth that should pass through everything',
        default=True)
    body: PointerProperty(
        name='Main Body', type=bpy.types.Object,
        description='The character or object this cloth rests on or wraps around',
        poll=lambda self, obj: obj.type == 'MESH')
    colliders: CollectionProperty(type=QCColliderItem)
    collider_index: IntProperty()
    binding_name: StringProperty()
    binding_target: PointerProperty(type=bpy.types.Object)
    diagnostics: StringProperty()
    coverage_text: StringProperty(default='Not inspected')
    collider_thickness: FloatProperty(
        name='New Collider Padding',
        description='Invisible padding added around objects that Quick Cloth '
                    'turns into colliders. Existing colliders keep their own value',
        default=.005, min=.001, max=1, unit='LENGTH')
    impulse_clamp: FloatProperty(
        name='Collision Impulse Limit',
        description='Caps how hard a collision can push the cloth. Try 1–5 if '
                    'the cloth explodes or jitters on contact; 0 means no limit',
        default=0, min=0, max=10000)
    self_impulse_clamp: FloatProperty(
        name='Self-Collision Impulse Limit',
        description='Caps how hard the cloth can push against itself. Try 1–5 '
                    'if folds jitter; 0 means no limit',
        default=0, min=0, max=10000)

    preset: EnumProperty(
        name="Fabric",
        description="What the cloth is made of. Choosing a fabric fills in its "
                    "weight, stiffness, damping, collision gaps, self-collision, "
                    "shrink, seam and volume settings (pins, pressure, wind and gravity are left alone). "
                    "Every value stays editable afterwards",
        items=PRESET_ITEMS,
        default="SIMPLE",
        update=apply_preset,
    )

    # --- Fabric physics -----------------------------------------------------
    mass: FloatProperty(
        name="Weight",
        description="Weight of each vertex. Heavier cloth hangs straighter and "
                    "resists wind. Denser meshes are heavier overall, so treat "
                    "this as a feel dial",
        default=0.30, min=0.001, max=10.0, unit='MASS',
    )
    tension_stiffness: FloatProperty(
        name="Stretch",
        description="How much the cloth resists being pulled longer. High for "
                    "denim and leather, low for latex and jersey",
        default=15.0, min=0.0, max=10000.0,
    )
    compression_stiffness: FloatProperty(
        name="Squash",
        description="How much the cloth resists being pushed shorter. Low "
                    "values make fine wrinkles; high values make big folds",
        default=15.0, min=0.0, max=10000.0,
    )
    shear_stiffness: FloatProperty(
        name="Shear",
        description="How much the cloth resists skewing diagonally (a square "
                    "becoming a diamond). Woven fabric skews less than knits",
        default=5.0, min=0.0, max=10000.0,
    )
    bending_stiffness: FloatProperty(
        name="Bend",
        description="How much the cloth resists folding. The main fabric dial: "
                    "near 0 follows every curve like silk, high makes few big "
                    "folds like leather",
        default=0.5, min=0.0, max=10000.0,
    )
    tension_damping: FloatProperty(
        name="Stretch Damping",
        description="How quickly stretch bounces settle. Higher is calmer and "
                    "less springy",
        default=5.0, min=0.0, max=50.0,
    )
    compression_damping: FloatProperty(
        name="Squash Damping",
        description="How quickly squash bounces settle",
        default=5.0, min=0.0, max=50.0,
    )
    shear_damping: FloatProperty(
        name="Shear Damping",
        description="How quickly diagonal jiggle settles",
        default=5.0, min=0.0, max=50.0,
    )
    bending_damping: FloatProperty(
        name="Bend Damping",
        description="How quickly flapping and folds settle. High values make "
                    "creases look held in place",
        default=0.5, min=0.0, max=1000.0,
    )
    air_damping: FloatProperty(
        name="Air Resistance",
        description="How much the air slows the cloth. Higher floats and falls "
                    "slowly; lower drops fast",
        default=1.0, min=0.0, max=10.0,
    )
    time_scale: FloatProperty(
        name="Speed",
        description="Plays the cloth faster or slower. Below 1 reads as "
                    "heavier, slower fabric. Use this instead of changing the "
                    "scene frame rate",
        default=1.0, min=0.01, max=10.0,
    )
    # Retained for saved files; the panel now uses a collapsible sub-panel.
    show_fabric_detail: BoolProperty(
        name="Fabric Detail",
        description="Show the individual stiffness and damping sliders",
        default=False,
    )
    use_internal_springs: BoolProperty(
        name="Keep Volume",
        description="Adds springs through the inside of closed shapes so "
                    "cushions and thick hide keep their bulk. Used by Couch Leather",
        default=False,
    )
    internal_stiffness: FloatProperty(
        name="Volume Stiffness",
        description="How firmly the inside springs hold the shape",
        default=5.0, min=0.0, max=10000.0,
    )

    # --- Garment ------------------------------------------------------------
    pin_stiffness: FloatProperty(
        name="Pin Strength",
        description="How firmly pinned vertices hold. Higher values lag less "
                    "behind the object or rig. Animate or rig the object to "
                    "move the pinned parts",
        default=1.0, min=0.0, max=50.0,
    )
    fit_tightness: FloatProperty(
        name="Shrink / Grow",
        description="Positive values shrink the cloth to hug a body (add a "
                    "body collider); negative values grow it looser",
        default=0.0, min=-0.3, max=0.3,
    )
    use_sewing: BoolProperty(
        name="Sew Seams",
        description="Pulls loose edges together, for garments modeled as flat "
                    "panels joined by loose seam edges. The Latex fabric uses this",
        default=False,
    )
    sewing_force: FloatProperty(
        name="Sewing Force",
        description="How hard the seam edges are pulled together",
        default=0.5, min=0.0, max=10000.0,
    )
    use_pressure: BoolProperty(
        name="Inflate",
        description="Fills a closed shape with air pressure: puffer jackets, "
                    "pillows, balloons",
        default=False,
    )
    pressure_force: FloatProperty(
        name="Pressure",
        description="Positive inflates, negative deflates",
        default=1.0, min=-10000.0, max=10000.0,
    )
    pressure_target_volume: FloatProperty(
        name="Target Volume",
        description="Volume the pressure tries to keep. 0 uses the pressure "
                    "value alone",
        default=0.0, min=0.0, max=10000.0,
    )

    # --- Forces -------------------------------------------------------------
    use_wind: BoolProperty(
        name="Add Wind",
        description="Adds a wind field (with gusts) that blows the cloth. It "
                    "is created when you press Set Up Cloth",
        default=False, update=wind_enabled_update,
    )
    wind_direction: FloatVectorProperty(
        name="Direction",
        description="World direction the wind blows toward",
        default=(1.0, 0.0, 0.0), subtype='XYZ', size=3,
    )
    wind_strength: FloatProperty(
        name="Strength",
        description="How strong the steady wind is",
        default=1000.0, min=0.0, max=100000.0,
    )
    wind_turbulence: FloatProperty(
        name="Gusts",
        description="How strong the random gusts are. 0 is perfectly steady wind",
        default=250.0, min=0.0, max=100000.0,
    )
    wind_seed: IntProperty(
        name="Gust Pattern",
        description="Change this number for a different gust pattern with the "
                    "same overall strength",
        default=0, min=0, max=10000,
    )
    gravity_influence: FloatProperty(
        name="Gravity",
        description="How much gravity pulls this cloth (0–1). Lower it to make "
                    "fabric float for stylized shots",
        default=1.0, min=0.0, max=1.0, subtype='FACTOR',
    )

    # --- Collisions ---------------------------------------------------------
    use_collision_objects: BoolProperty(
        name="Auto Colliders for Rigid Bodies",
        description="When you press Set Up Cloth or Bake, any rigid-body mesh "
                    "in the scene without a collider gets one, so physics "
                    "props just work. Turn off to leave other objects untouched",
        default=True,
    )
    object_distance: FloatProperty(
        name="Gap to Obstacles",
        description="Space the cloth keeps from colliders. Raise it if the "
                    "cloth pokes through; lower it if it floats above the body",
        default=0.015, min=0.001, max=1.0, unit='LENGTH',
    )
    use_self_collision: BoolProperty(
        name="Collide With Itself",
        description="Stops the cloth passing through itself. Needed for tight "
                    "fits and layered folds; makes the simulation slower",
        default=False,
    )
    self_distance: FloatProperty(
        name="Gap to Itself",
        description="Space the cloth keeps from itself. Keep it under a third of "
                    "the mesh's short edges (about 5 mm for 2 cm edges): larger "
                    "gaps make the cloth jitter or explode",
        default=0.015, min=0.001, max=0.1, unit='LENGTH',
    )

    # --- Simulation ---------------------------------------------------------
    quality_mode: EnumProperty(
        name='Quality',
        description='How carefully the solver works. Changes speed and '
                    'accuracy only, never how the fabric behaves',
        items=[('PREVIEW', 'Preview', '20 steps per frame: fast, for checking timing and broad motion', 0),
               ('LOW', 'Low', '32 steps per frame: quick drafts', 5),
               ('FINAL', 'Legacy Final', 'Values kept from an older Quick Cloth version', 1),
               ('MEDIUM', 'Medium', '64 steps per frame: good for most shots', 2),
               ('HIGH', 'High', '120 steps per frame: slow; fast motion and tight contact', 3),
               ('CUSTOM', 'Custom', 'Your own number of steps per frame', 4)],
        default='MEDIUM', update=quality_update,
    )
    frame_start: IntProperty(
        name="Start Frame",
        description="First frame of the shot",
        default=1,
    )
    frame_end: IntProperty(
        name="End Frame",
        description="Last frame of the simulation",
        default=250,
    )
    settle_frames: IntProperty(
        name="Settle Frames",
        description="Starts the simulation this many frames before the shot so "
                    "the cloth is already draped when the shot begins. The "
                    "shot start must be at least this many frames; nothing is "
                    "retimed. Hold the character still during these frames",
        default=0, min=0, max=120,
    )
    use_preview_range: BoolProperty(
        name="Use Timeline Preview Range",
        description="When the timeline's preview range is on, simulate that "
                    "range instead of the Start/End frames above",
        default=False,
    )
    quality_steps: IntProperty(
        name="Solver Steps",
        description="Calculation steps per frame. More is slower but more "
                    "stable; too few makes stretchy, unstable cloth. Editing "
                    "this switches Quality to Custom",
        default=64, min=1, max=1000, soft_max=300, update=quality_values_update,
    )
    collision_quality: IntProperty(
        name="Collision Steps",
        description="Collision checks per step. Raise it if fast cloth passes "
                    "through obstacles. Editing this switches Quality to Custom",
        default=5, min=1, max=20, update=quality_values_update,
    )
    use_disk_cache: BoolProperty(
        name="Save Bake to Disk",
        description="Store the bake in a blendcache folder next to the saved "
                    ".blend instead of inside it. Needs a saved file; keep the "
                    "folder with the project when moving it",
        default=False,
    )

    # --- Animator Mode --------------------------------------------------
    cage_ratio: FloatProperty(
        name="Stand-in Detail",
        description="How detailed the Animator Mode stand-in is compared with "
                    "the cloth (0.2 = 20% of the faces). It follows the rig "
                    "without solving cloth, so playback stays fast",
        default=0.2, min=0.02, max=1.0, subtype='FACTOR',
    )


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS (pure / context-light where possible)
# ---------------------------------------------------------------------------

def _normalize(name):
    return name.lower().replace(" ", "").replace("_", "").replace("-", "")


def find_pin_group(obj):
    """Fuzzy-find the pin vertex group ("pin", "pins", "pin group",
    "pinned", any capitalization). Returns the group or None.
    Same matcher pattern as Quick Break's find_impact_group."""
    if obj is None or obj.type != 'MESH':
        return None
    if obj.quick_cloth.pin_group:
        return obj.vertex_groups.get(obj.quick_cloth.pin_group)
    matches = [g for g in obj.vertex_groups if _normalize(g.name) in PIN_GROUP_ALIASES]
    return matches[0] if len(matches) == 1 else None


def find_cloth_modifier(obj):
    """Return the object's Cloth modifier, or None."""
    for mod in obj.modifiers:
        if mod.type == 'CLOTH':
            return mod
    return None


def ensure_cloth_modifier(obj):
    """Return the existing Cloth modifier or create one. Idempotent."""
    mod = find_cloth_modifier(obj)
    if mod is None:
        mod = obj.modifiers.new(name="Quick Cloth", type='CLOTH')
    return mod


def ensure_stack_order(obj, report=None):
    """Rigged-garment rule: Armature FIRST, Cloth AFTER it, so pinned
    vertices follow the rig while unpinned fabric simulates on top.
    Uses modifiers.move() — no ops. Returns True if the stack was fixed."""
    arm_index = cloth_index = None
    for i, mod in enumerate(obj.modifiers):
        if mod.type == 'ARMATURE':
            arm_index = i
        elif mod.type == 'CLOTH':
            cloth_index = i
    if arm_index is None or cloth_index is None:
        return False
    if cloth_index > arm_index:
        return False  # already correct
    obj.modifiers.move(cloth_index, arm_index)
    if report is not None:
        report({'INFO'}, "Moved Cloth below Armature so pins follow the rig")
    return True


def configure_cloth_from_props(mod, props, preview=False):
    """Write the PropertyGroup values into a Cloth modifier.

    The legacy preview argument is retained for API compatibility. Quality is
    always resolved from the garment's selected tier.
    """
    s = mod.settings
    c = mod.collision_settings

    s.mass = props.mass
    s.tension_stiffness = props.tension_stiffness
    s.compression_stiffness = props.compression_stiffness
    s.shear_stiffness = props.shear_stiffness
    s.bending_stiffness = props.bending_stiffness
    s.tension_damping = props.tension_damping
    s.compression_damping = props.compression_damping
    s.shear_damping = props.shear_damping
    s.bending_damping = props.bending_damping
    s.air_damping = props.air_damping
    s.time_scale = props.time_scale
    s.shrink_min = props.fit_tightness

    # Sewing
    s.use_sewing_springs = props.use_sewing
    s.sewing_force_max = props.sewing_force

    # Pressure
    s.use_pressure = props.use_pressure
    s.uniform_pressure_force = props.pressure_force
    if props.pressure_target_volume > 0.0:
        s.use_pressure_volume = True
        s.target_volume = props.pressure_target_volume
    else:
        s.use_pressure_volume = False

    # Internal springs (Couch Leather volume)
    s.use_internal_springs = props.use_internal_springs
    if props.use_internal_springs:
        s.internal_tension_stiffness = props.internal_stiffness
        s.internal_compression_stiffness = props.internal_stiffness

    # Gravity influence
    s.effector_weights.gravity = props.gravity_influence

    # Pinning
    s.pin_stiffness = props.pin_stiffness
    s.use_dynamic_mesh = props.dynamic_mesh

    # One resolver for setup, preset refresh, UI and baking.
    s.quality, c.collision_quality = resolve_quality(props)
    c.use_self_collision = props.use_self_collision

    c.distance_min = props.object_distance
    c.self_distance_min = props.self_distance
    c.use_collision = props.use_object_collision

    # Authored clamping values; no universal anti-jitter claim.
    c.impulse_clamp = props.impulse_clamp
    c.self_impulse_clamp = props.self_impulse_clamp

    # Existing user collision filters remain intact. New Cloth uses its native default.


def convert_obstacles_to_colliders(scene, cloth_obj, object_distance, report=None):
    """Auto-conversion (mirror of Quick Break's, in reverse): every mesh in
    the scene — other than the cloth itself — that has a Rigid Body (active
    or passive) but no Collision modifier gets one, with tuned defaults.
    Each object is converted individually — no grouping. Idempotent.
    Never applies or freezes existing modifiers, so rigged meshes stay
    intact (Collision evaluates the DEFORMED mesh, so animated characters
    work as moving colliders automatically)."""
    converted = 0
    for obj in scene.objects:
        if obj is cloth_obj or obj.type != 'MESH':
            continue
        if obj.rigid_body is None:
            continue
        if any(m.type == 'COLLISION' for m in obj.modifiers):
            continue
        if object_is_override_locked(obj):
            # Linked data can't take new modifiers; skip quietly but note it.
            if report is not None:
                report({'WARNING'}, f"Skipped linked object '{obj.name}' — "
                                    "can't add a Collision modifier to linked data")
            continue
        make_collider(obj, object_distance)
        converted += 1
    return converted


def make_collider(obj, thickness=.005):
    """Add (or reuse) a tuned Collision modifier on a single object.
    Never touches the rest of the modifier stack — rigged meshes stay
    rigged."""
    if object_is_override_locked(obj):
        raise ValueError(f'{obj.name}: collider object is not editable')
    existing = next((m for m in obj.modifiers if m.type == 'COLLISION'), None)
    if existing is not None:
        return existing
    mod = obj.modifiers.new(name="QC Collision", type='COLLISION')
    obj['qc_collision_created'] = True
    if obj.collision is not None:
        obj.collision.thickness_outer = thickness
        obj.collision.damping = 0.1
    return mod


def owned_helper(obj, props):
    return bool(obj and obj.get('qc_owner') == props.setup_id and props.setup_id
                and obj.quick_cloth.garment == props.id_data)


def ensure_wind_rig(context, props):
    if not props.setup_id:
        raise ValueError('Set up the garment before adding wind')
    direction = Vector(props.wind_direction)
    if props.use_wind and direction.length < 1e-6:
        raise ValueError('Wind direction cannot be zero')
    for obj, kind in ((props.wind, 'WIND'), (props.turbulence, 'TURBULENCE')):
        if owned_helper(obj, props) and (obj.field is None or obj.field.type != kind):
            raise ValueError(f'{obj.name}: owned force field was changed; remove and recreate it')
    if owned_helper(props.wind, props) and (props.wind.parent or props.wind.constraints):
        raise ValueError('Owned wind has a parent/constraint; remove it before using world-space direction')
    if not props.use_wind:
        wind_enabled_update(props, context)
        return props.wind
    selected = list(context.selected_objects)
    active = context.view_layer.objects.active
    try:
        for attr, kind, label in (('wind', 'WIND', 'QC Wind'),
                                  ('turbulence', 'TURBULENCE', 'QC Turbulence')):
            obj = getattr(props, attr)
            if not owned_helper(obj, props):
                bpy.ops.object.effector_add(type=kind, location=(0, 0, 0))
                obj = context.object
                obj.name = label
                obj['qc_owner'] = props.setup_id
                obj.quick_cloth.garment = props.id_data
                setattr(props, attr, obj)
            if obj.field is None or obj.field.type != kind:
                raise ValueError(f'{obj.name}: owned force field was changed; remove and recreate it')
        wind, turb = props.wind, props.turbulence
        direction = Vector(props.wind_direction)
        if direction.length < 1e-6:
            raise ValueError('Wind direction cannot be zero')
        if wind.parent or wind.constraints:
            raise ValueError('Owned wind has a parent/constraint; remove it before using world-space direction')
        wind.rotation_euler = direction.normalized().to_track_quat('Z', 'Y').to_euler()
        wind.field.strength = props.wind_strength if props.use_wind else 0
        turb.parent = wind
        turb.field.strength = props.wind_turbulence if props.use_wind else 0
        turb.field.seed = props.wind_seed
        return wind
    finally:
        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in selected:
            if obj.name in context.view_layer.objects:
                obj.select_set(True)
        context.view_layer.objects.active = active


def remove_wind_rig(context):
    props = get_props(context)
    removed = 0
    for attr in ('turbulence', 'wind'):
        obj = getattr(props, attr)
        if owned_helper(obj, props):
            bpy.data.objects.remove(obj, do_unlink=True)
            removed += 1
        setattr(props, attr, None)
    return removed


def cache_hygiene(context, scene, cache, sim_start, sim_end, report=None):
    if cache.is_baked or cache.is_baking:
        raise ValueError('Existing baked/running cache: use Re-bake or Delete Bake first')
    if sim_start < 0 or sim_end < max(1, sim_start):
        raise ValueError('Invalid simulation range; negative pre-roll is not supported')
    cache.frame_start = sim_start
    cache.frame_end = sim_end
    if (cache.frame_start, cache.frame_end) != (sim_start, sim_end):
        raise ValueError('Blender clamped the requested cache range')
    scene.frame_set(sim_start)


def object_is_override_locked(obj):
    """True for linked or library-override data we must not edit."""
    return not editable(obj)


def get_props(context):
    obj = context.active_object
    if obj is not None and obj.type == 'MESH':
        garment = obj.quick_cloth.garment
        return (garment or obj).quick_cloth
    return context.scene.quick_cloth


def initialize_setup(obj, scene, adopt=False):
    """Explicit adoption preserves live values; never migrate by panel draw."""
    if object_is_override_locked(obj):
        raise ValueError('Object is not editable')
    p = obj.quick_cloth
    mod = find_cloth_modifier(obj)
    if not p.setup_id:
        if mod is not None and not adopt:
            raise ValueError('Existing cloth found. Use Adopt Existing Cloth to preserve its settings.')
        if mod is not None:
            # Reject lossy adoption before touching ANY authored properties.
            if mod.settings.internal_tension_stiffness != mod.settings.internal_compression_stiffness:
                raise ValueError('Cannot adopt unequal internal tension/compression stiffness without loss; '
                                 'Quick Cloth has one internal stiffness control. Original cloth is unchanged.')
            native = {prop.identifier: getattr(mod.settings, prop.identifier)
                      for prop in p.bl_rna.properties
                      if hasattr(mod.settings, prop.identifier)
                      and prop.type in {'INT', 'FLOAT'} and not prop.is_array}
            native.update(fit_tightness=mod.settings.shrink_min,
                          quality_steps=mod.settings.quality,
                          collision_quality=mod.collision_settings.collision_quality,
                          object_distance=mod.collision_settings.distance_min,
                          self_distance=mod.collision_settings.self_distance_min,
                          pressure_force=mod.settings.uniform_pressure_force,
                          gravity_influence=mod.settings.effector_weights.gravity,
                          sewing_force=mod.settings.sewing_force_max,
                          internal_stiffness=mod.settings.internal_tension_stiffness)
            for key, value in native.items():
                limits = p.bl_rna.properties[key]
                if not limits.hard_min <= value <= limits.hard_max:
                    raise ValueError(f'Cannot adopt {key}={value:g} without loss; supported panel range '
                                     f'is {limits.hard_min:g}–{limits.hard_max:g}. Original cloth is unchanged.')
        # New setups use scene defaults; adoption reads the live modifier below.
        excluded = {'rna_type', 'setup_id', 'data_version', 'cage', 'garment', 'wind',
                    'turbulence', 'animator_state', 'legacy_fit', 'preset',
                    'bake_state', 'bake_error', 'bake_signature', 'bake_metadata', 'bake_needs_validation',
                    'binding_name', 'binding_target', 'quality_steps', 'collision_quality', 'diagnostics', 'coverage_text',
                    'colliders', 'collider_index'}
        for prop in p.bl_rna.properties:
            key = prop.identifier
            if (key not in excluded and not prop.is_readonly and prop.type != 'POINTER'
                    and not p.is_property_set(key) and scene.quick_cloth.is_property_set(key)):
                setattr(p, key, getattr(scene.quick_cloth, key))
        # Avoid firing the fabric callback during migration.
        if not p.is_property_set('preset'):
            p['preset'] = scene.quick_cloth['preset'] if 'preset' in scene.quick_cloth else 0
        if mod is not None:
            s, c = mod.settings, mod.collision_settings
            mapping = {'fit_tightness': 'shrink_min', 'use_sewing': 'use_sewing_springs',
                       'sewing_force': 'sewing_force_max', 'pressure_force': 'uniform_pressure_force',
                       'pressure_target_volume': 'target_volume', 'quality_steps': 'quality',
                       'internal_stiffness': 'internal_tension_stiffness'}
            for prop in p.bl_rna.properties:
                key = prop.identifier
                if key in excluded or prop.is_readonly or prop.type == 'POINTER':
                    continue
                native = mapping.get(key, key)
                if hasattr(s, native) and isinstance(getattr(s, native), (int, float, bool)):
                    setattr(p, key, getattr(s, native))
            p.use_self_collision = c.use_self_collision
            p.use_object_collision = c.use_collision
            p.impulse_clamp = c.impulse_clamp
            p.self_impulse_clamp = c.self_impulse_clamp
            p.collision_quality = c.collision_quality
            p.object_distance = c.distance_min
            p.self_distance = c.self_distance_min
            p.pin_group = s.vertex_group_mass
            p.gravity_influence = s.effector_weights.gravity
            p.frame_start, p.frame_end = mod.point_cache.frame_start, mod.point_cache.frame_end
            p.use_disk_cache = mod.point_cache.use_disk_cache
            p.use_preview_range = False
            p.settle_frames = 0
            p.legacy_fit = True
            p.quality_mode = 'CUSTOM'
            p.quality_steps = s.quality
            p.collision_quality = c.collision_quality
            p.dynamic_mesh = s.use_dynamic_mesh
            if not s.use_pressure_volume:
                p.pressure_target_volume = 0
            p.bake_needs_validation = mod.point_cache.is_baked
        p.setup_id = uuid.uuid4().hex
        p.data_version = 1
    elif any(entry.uid == p.setup_id and entry.owner != obj and entry.owner is not None
             for entry in scene.quick_cloth_registry):
        p.setup_id = uuid.uuid4().hex
        p.cage = p.wind = p.turbulence = None
        p.animator_state = ''
        p.bake_signature = p.bake_metadata = ''
        p.bake_needs_validation = True
    p.owner = obj
    if not any(entry.uid == p.setup_id and entry.owner == obj for entry in scene.quick_cloth_registry):
        entry = scene.quick_cloth_registry.add()
        entry.uid, entry.owner = p.setup_id, obj
    return p


class QC_OT_quality(Operator):
    """Choose how carefully the cloth is solved: faster and rougher, or slower and more accurate"""
    bl_idname = 'quick_cloth.quality'
    bl_label = 'Set Simulation Quality'
    bl_options = {'REGISTER', 'UNDO'}
    tier: StringProperty()

    def execute(self, context):
        if self.tier not in {'PREVIEW', 'LOW', 'MEDIUM', 'HIGH', 'CUSTOM'}:
            return {'CANCELLED'}
        if baking.any_baking():
            self.report({'ERROR'}, 'Wait for the running bake before changing quality')
            return {'CANCELLED'}
        get_props(context).quality_mode = self.tier
        return {'FINISHED'}


class QC_OT_adopt(Operator):
    """Manage this mesh's existing cloth with Quick Cloth. Its settings and any bake stay exactly as they are"""
    bl_idname = 'quick_cloth.adopt'
    bl_label = 'Adopt Existing Cloth'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj and obj.type == 'MESH' and find_cloth_modifier(obj)
                    and (not obj.quick_cloth.setup_id or not any(
                        e.uid == obj.quick_cloth.setup_id and e.owner == obj
                        for e in context.scene.quick_cloth_registry)))

    def execute(self, context):
        try:
            initialize_setup(context.active_object, context.scene, adopt=True)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Existing cloth adopted; live settings and cache preserved')
        return {'FINISHED'}


OVERRIDE_MESSAGE = ("This object is a linked override — make the cloth "
                    "modifier editable in the override hierarchy first")


def cage_name_for(obj):
    return CAGE_PREFIX + obj.name


def find_cage(obj):
    cage = obj.quick_cloth.cage
    return cage if owned_helper(cage, obj.quick_cloth) and cage.quick_cloth.garment == obj else None


def find_garment_for_cage(cage):
    return cage.quick_cloth.garment


def resolve_animator_pair(obj):
    if obj is None or obj.type != 'MESH':
        return None, None
    if obj.get('qc_helper') == 'cage':
        return obj.quick_cloth.garment, obj
    return obj, find_cage(obj)


def animator_mode_active(obj):
    garment, cage = resolve_animator_pair(obj)
    return bool(garment and garment.quick_cloth.animator_state)


def build_or_update_cage(context, garment, ratio):
    # Rebuild each entry so edited geometry, weights, actions and constraints cannot go stale.
    p = garment.quick_cloth
    old = find_cage(garment)
    if old:
        old_data = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if old_data.users == 0 and old_data.get('qc_owner') == p.setup_id:
            bpy.data.meshes.remove(old_data)
    cage = garment.copy()
    cage.data = garment.data.copy()
    cage.name = cage_name_for(garment)
    cage['qc_owner'] = p.setup_id
    cage['qc_helper'] = 'cage'
    cage.data['qc_owner'] = p.setup_id
    cage.quick_cloth.setup_id = ''
    cage.quick_cloth.garment = garment
    cage.quick_cloth.cage = None
    cage.quick_cloth.wind = None
    cage.quick_cloth.turbulence = None
    cage.quick_cloth.animator_state = ''
    cage.quick_cloth.bake_signature = ''
    context.collection.objects.link(cage)
    for mod in list(cage.modifiers):
        if mod.type in {'CLOTH', 'COLLISION'}:
            cage.modifiers.remove(mod)
    dec = cage.modifiers.new(name='QC Cage Decimate', type='DECIMATE')
    dec.ratio = ratio
    cage.hide_render = True
    cage.hide_viewport = False
    cage.hide_set(False)
    cage.show_wire = True
    p.cage = cage
    return cage


# ---------------------------------------------------------------------------
# OPERATORS
# ---------------------------------------------------------------------------

class QC_OT_simulate(Operator):
    """Turn the selected mesh into cloth using the panel settings, or apply changed settings.
Also hooks up pins, places the cloth after the rig, adds wind if enabled and sets the frame range.
Press Play afterwards to preview. A baked cloth is updated with Re-bake instead"""
    bl_idname = "quick_cloth.simulate"
    bl_label = "Set Up Cloth"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT')

    def execute(self, context):
        scene = context.scene
        obj = context.active_object
        if baking.any_baking():
            self.report({'ERROR'}, 'Wait for the running cloth bake')
            return {'CANCELLED'}
        existing = find_cloth_modifier(obj)
        if existing and existing.point_cache.is_baked:
            self.report({'ERROR'}, 'This cloth is baked. Use Re-bake to apply new settings, or Delete Bake first.')
            return {'CANCELLED'}
        try:
            baking.effective_range(scene, obj.quick_cloth)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        errors, warnings = geometry_issues(obj)
        if errors:
            self.report({'ERROR'}, '; '.join(errors))
            return {'CANCELLED'}
        for warning in warnings:
            self.report({'WARNING'}, warning)

        # Reject before initialize_setup so a refused run registers nothing.
        # Never simulate the cage itself — it's a deform-only stand-in.
        if obj.get('qc_helper') == 'cage':
            self.report({'ERROR'},
                        "This is the animation cage — select the real "
                        "garment to simulate")
            return {'CANCELLED'}

        if object_is_override_locked(obj):
            self.report({'ERROR'}, OVERRIDE_MESSAGE)
            return {'CANCELLED'}

        if animator_mode_active(obj):
            self.report({'ERROR'},
                        "Animator Mode is on (the cloth is muted) — press "
                        "Exit Animator Mode first, then Set Up Cloth")
            return {'CANCELLED'}

        try:
            props = initialize_setup(obj, scene)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        # 1. Cloth modifier — reuse existing (idempotent: running twice
        #    updates, never stacks a second one).
        mod = ensure_cloth_modifier(obj)

        # 2. Configure from the panel values (Preview scaling is applied at
        #    configure time only — stored sliders untouched).
        configure_cloth_from_props(mod, props,
                                   preview=(props.quality_mode == 'PREVIEW'))

        # 3. Pinning: fuzzy-find the pin group and wire it up.
        pin_group = find_pin_group(obj)
        if pin_group is not None:
            props.pin_group = pin_group.name
            mod.settings.vertex_group_mass = pin_group.name
            pinned, total = pin_coverage(obj, pin_group.name)
            props.coverage_text = f'{pinned}/{total} vertices (last setup check)'
            if pinned == total:
                self.report({'WARNING'}, 'All vertices have attachment weights; paint weights down where cloth should move freely')
            self.report({'INFO'}, f"Pin group '{pin_group.name}' found and "
                                  "wired to the cloth")
        else:
            mod.settings.vertex_group_mass = ""

        # 4. Rigged-garment stack order: Armature FIRST, Cloth AFTER.
        ensure_stack_order(obj, report=self.report)

        # 5. Collision auto-conversion (no collision collection, ever —
        #    each obstacle converted individually).
        if props.use_collision_objects:
            n = convert_obstacles_to_colliders(scene, obj,
                                               props.collider_thickness,
                                               report=self.report)
            if n:
                self.report({'INFO'},
                            f"Gave {n} rigid-body obstacle(s) a Collision "
                            "modifier")

        # 6. Owned wind pointers; names do not grant ownership.
        if props.use_wind or props.wind:
            try:
                ensure_wind_rig(context, props)
            except ValueError as exc:
                self.report({'ERROR'}, str(exc))
                return {'CANCELLED'}

        # 7. Frame range: shot range from the panel (or the timeline's
        #    preview range), minus the settle pre-roll.
        sim_start, sim_end = baking.effective_range(scene, props)

        # 8. Cache hygiene + disk cache.
        cache = mod.point_cache
        cache_hygiene(context, scene, cache, sim_start, sim_end,
                      report=self.report)
        cache.use_disk_cache = props.use_disk_cache
        if props.use_disk_cache:
            cache.use_library_path = False

        self.report({'INFO'},
                    f"Cloth configured on '{obj.name}' "
                    f"({props.preset.replace('_', ' ').title()}, "
                    f"frames {cache.frame_start}–{cache.frame_end}"
                    + (f", {props.settle_frames} settle frames" if props.settle_frames else "")
                    + "). Press Play from the first frame to preview")
        return {'FINISHED'}


class QC_OT_set_pin_group(Operator):
    """Pin the vertices selected in Edit Mode (replaces the pin group's previous selection).
Pinned vertices stick to the object or rig: pin the collar or waistband and let the rest move"""
    bl_idname = "quick_cloth.set_pin_group"
    bl_label = "Pin Selected Vertices"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'EDIT_MESH')

    def execute(self, context):
        obj = context.active_object

        try:
            validate_pin_edit(obj)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}

        # BMesh edits keep the user's mode/selection intact, including failures.
        import bmesh
        bm = bmesh.from_edit_mesh(obj.data)
        selected = [v for v in bm.verts if v.select]
        if not selected:
            self.report({'ERROR'}, 'Select vertices to pin first')
            return {'CANCELLED'}
        name = obj.quick_cloth.pin_group
        group = obj.vertex_groups.get(name) if name else None
        if group is None:
            group = obj.vertex_groups.new(name='QC Attachment')
        layer = bm.verts.layers.deform.verify()
        for v in bm.verts:
            if group.index in v[layer]:
                del v[layer][group.index]
        for v in selected:
            v[layer][group.index] = 1.0
        obj.quick_cloth.pin_group = group.name
        obj.quick_cloth.coverage_text = f'{len(selected)}/{len(bm.verts)} vertices (last pin edit)'
        bmesh.update_edit_mesh(obj.data)
        self.report({'INFO'}, f'Updated {group.name}: {len(selected)} attachment vertices')
        return {'FINISHED'}


class QC_OT_pin_from_rig_weights(Operator):
    """Pin every vertex by how strongly the rig moves it, so the garment follows the rig.
Then lower the pin weights in Weight Paint mode wherever the fabric should swing freely.
Bone weights are never changed"""
    bl_idname = "quick_cloth.pin_from_rig_weights"
    bl_label = "Pin From Rig Weights"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH' or context.mode != 'OBJECT':
            return False
        return any(m.type == 'ARMATURE' and m.object is not None
                   for m in obj.modifiers)

    def execute(self, context):
        obj = context.active_object

        try:
            validate_pin_edit(obj)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        rigs = [m for m in obj.modifiers if m.type == 'ARMATURE' and m.object]
        if len(rigs) != 1 or not rigs[0].use_vertex_groups:
            self.report({'ERROR'}, 'Automatic pinning requires one vertex-weight armature; choose an attachment group manually for other rigs')
            return {'CANCELLED'}

        if object_is_override_locked(obj):
            self.report({'ERROR'}, OVERRIDE_MESSAGE)
            return {'CANCELLED'}

        # The rig driving this garment.
        arm_mod = next(m for m in obj.modifiers
                       if m.type == 'ARMATURE' and m.object is not None)
        armature = arm_mod.object.data

        # Vertex-group indices that correspond to DEFORM bones of that rig.
        deform_bones = {b.name for b in armature.bones if b.use_deform}
        deform_group_indices = {g.index for g in obj.vertex_groups
                                if g.name in deform_bones}
        if not deform_group_indices:
            self.report({'ERROR'},
                        "No vertex groups match the rig's deform bones — "
                        "parent with automatic weights (or paint weights) "
                        "first")
            return {'CANCELLED'}

        # Sum each vertex's bone weights, clamped to 0–1. Reading weights
        # via vertex.groups is direct data access — no ops, no mode
        # switches, selection untouched.
        pin_group = obj.vertex_groups.get(obj.quick_cloth.pin_group)
        if pin_group is not None and pin_group.name in armature.bones:
            self.report({'ERROR'}, 'Attachment destination is a rig bone group; choose a separate '
                        'attachment group or clear the attachment field to create one. Bone weights are unchanged.')
            return {'CANCELLED'}

        # Stage and validate the complete result before creating or editing pins.
        weights = [(v.index, min(sum(g.weight for g in v.groups
                                    if g.group in deform_group_indices), 1.0))
                   for v in obj.data.vertices]
        weighted = sum(weight > 0.0 for _, weight in weights)
        if weighted == 0:
            self.report({'ERROR'},
                        "The rig's deform bones carry no weight on this "
                        "mesh — automatic weighting may have failed "
                        "(overlapping or non-manifold geometry). Existing attachments are unchanged.")
            return {'CANCELLED'}

        if pin_group is None:
            pin_group = obj.vertex_groups.new(name='QC Attachment')
        pin_index = pin_group.index
        for index, weight in weights:
            if weight > 0.0:
                pin_group.add([index], weight, 'REPLACE')
            elif any(g.group == pin_index for g in obj.data.vertices[index].groups):
                pin_group.remove([index])
        obj.quick_cloth.pin_group = pin_group.name

        self.report({'INFO'},
                    f"Pin group '{pin_group.name}' built from rig weights "
                    f"({weighted}/{len(obj.data.vertices)} vertices). Paint "
                    "the pin weights DOWN where fabric should swing free")
        if weighted == len(obj.data.vertices):
            self.report({'WARNING'}, 'All vertices are weighted: paint attachment weights down to allow free cloth motion')
        obj.quick_cloth.coverage_text = f'{weighted}/{len(obj.data.vertices)} vertices (last pin edit)'
        return {'FINISHED'}



class QC_OT_make_colliders(Operator):
    """Make the selected objects colliders so the cloth can rest on them: chairs, bodies, tables.
Rigged characters keep working and collide as they move. Existing colliders are left as they are"""
    bl_idname = "quick_cloth.make_colliders"
    bl_label = "Make Selected Colliders"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'OBJECT'
                and any(o.type == 'MESH' for o in context.selected_objects))

    def execute(self, context):
        count = 0
        skipped = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            if object_is_override_locked(obj):
                skipped += 1
                continue
            make_collider(obj)
            count += 1
        if skipped:
            self.report({'WARNING'},
                        f"Skipped {skipped} linked/override object(s) — "
                        "make them local or editable first")
        if count == 0:
            self.report({'ERROR'}, "No editable mesh objects selected")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Collision modifier ensured on {count} "
                              "object(s)")
        return {'FINISHED'}


class QC_OT_fit_self_gap(Operator):
    """Set Gap to Itself to a quarter of this mesh's short edges, the largest gap that stays stable"""
    bl_idname = 'quick_cloth.fit_self_gap'
    bl_label = 'Use Safe Gap'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and editable(obj)

    def execute(self, context):
        obj = context.active_object
        short = short_edge_length(obj)
        if short <= 0:
            self.report({'ERROR'}, 'The mesh has no edges to measure')
            return {'CANCELLED'}
        p = obj.quick_cloth
        p.self_distance = safe_self_gap(short)
        mod = find_cloth_modifier(obj)
        if mod is not None and not mod.point_cache.is_baked and not object_is_override_locked(obj):
            mod.collision_settings.self_distance_min = p.self_distance
        self.report({'INFO'}, f'Gap to Itself set to {p.self_distance * 1000:.1f} mm')
        return {'FINISHED'}


class QC_OT_body_collider(Operator):
    """Make the main body and every mesh in the collider list colliders, so the cloth rests on them.
No rigid-body physics is added, and existing colliders are left as they are"""
    bl_idname = 'quick_cloth.body_collider'
    bl_label = 'Make Them Colliders'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        targets = baking.collision_targets(get_props(context))
        if not targets:
            self.report({'ERROR'}, 'Choose a main body or add meshes to the collider list first')
            return {'CANCELLED'}
        made, failed = 0, []
        for obj in targets:
            if baking.is_collider(obj):
                continue
            try:
                make_collider(obj, get_props(context).collider_thickness)
                made += 1
            except ValueError as exc:
                failed.append(str(exc))
        if failed:
            self.report({'ERROR'}, '; '.join(failed))
            return {'CANCELLED'} if not made else {'FINISHED'}
        self.report({'INFO'}, f'{made} new collider(s); {len(targets)} in total')
        return {'FINISHED'}


class QC_OT_collider_add(Operator):
    """Add meshes for the cloth to collide with. Selected meshes other than the cloth are added;
with nothing else selected, an empty row is added for you to pick a mesh in"""
    bl_idname = 'quick_cloth.collider_add'
    bl_label = 'Add Collider'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj and obj.type == 'MESH' and not is_cage(obj) and editable(obj))

    def execute(self, context):
        p = get_props(context)
        present = baking.collision_targets(p)
        picks = [o for o in context.selected_objects
                 if o.type == 'MESH' and o != p.id_data and not is_cage(o) and o not in present]
        for obj in picks or [None]:
            p.colliders.add().object = obj
        p.collider_index = len(p.colliders) - 1
        if picks:
            self.report({'INFO'}, f'Added {len(picks)} collider(s)')
        return {'FINISHED'}


class QC_OT_collider_remove(Operator):
    """Take the highlighted mesh off the collider list. Its Collision modifier is kept"""
    bl_idname = 'quick_cloth.collider_remove'
    bl_label = 'Remove Collider'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or is_cage(obj):
            return False
        p = get_props(context)
        return 0 <= p.collider_index < len(p.colliders)

    def execute(self, context):
        p = get_props(context)
        p.colliders.remove(p.collider_index)
        p.collider_index = min(p.collider_index, len(p.colliders) - 1)
        return {'FINISHED'}


class QC_OT_remove_wind(Operator):
    """Delete the wind and gust fields Quick Cloth created for this cloth"""
    bl_idname = "quick_cloth.remove_wind"
    bl_label = "Remove Wind"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        props = get_props(context)
        return owned_helper(props.wind, props) or owned_helper(props.turbulence, props)

    def execute(self, context):
        removed = remove_wind_rig(context)
        self.report({'INFO'}, f"Removed {removed} wind rig object(s)")
        return {'FINISHED'}


class QC_OT_diagnose(Operator):
    """Look for setup problems, and check whether the cloth already cuts into the body on this frame"""
    bl_idname = 'quick_cloth.diagnose'
    bl_label = 'Check for Problems'

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return {'CANCELLED'}
        errors, warnings = baking.preflight(context, obj, storage=True)
        for target in baking.collision_targets(obj.quick_cloth):
            warnings += contact_warnings(context, obj, target)
        weighted, total = pin_coverage(obj, obj.quick_cloth.pin_group)
        obj.quick_cloth.coverage_text = f'{weighted}/{total} vertices (last inspection)'
        messages = errors + warnings
        obj.quick_cloth.diagnostics = '\n'.join(messages) or 'Preflight passed. Full-shot visual collision acceptance is still required.'
        self.report({'WARNING'} if messages else {'INFO'}, obj.quick_cloth.diagnostics)
        return {'FINISHED'}


class QC_OT_validate_bake(Operator):
    """Compare the scene with how it was when the cloth was baked, to see whether a Re-bake is needed"""
    bl_idname = 'quick_cloth.validate_bake'
    bl_label = 'Check Bake'

    def execute(self, context):
        obj = context.active_object
        if not obj or not baking.cloth(obj):
            return {'CANCELLED'}
        p = obj.quick_cloth
        try:
            same = bool(p.bake_signature and p.bake_signature == baking.signature(context.scene, obj))
        except ValueError:
            # An invalid requested range cannot match a previously valid bake.
            same = False
        p.bake_needs_validation = not same
        p.bake_state = 'BAKED' if same else 'DIRTY'
        self.report({'INFO'} if same else {'WARNING'},
                    'Bake matches the scene; still check the result visually (outside driver inputs can\'t be tracked)' if same
                    else 'The scene changed since this bake (or it has no record); Re-bake to update it')
        return {'FINISHED'}


class QC_OT_bake(Operator):
    """Apply the current settings and save the simulation for the shown frames, so it plays back fast and renders the same every time"""
    bl_idname = 'quick_cloth.bake'
    bl_label = 'Bake Cloth'
    rebuild: BoolProperty(default=False)
    _timer = None
    _ticks = 0

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return False
        errors, _ = baking.preflight(context, obj)
        if errors:
            cls.poll_message_set(errors[0])
        return not errors

    def invoke(self, context, event):
        self._interactive = True
        if self.rebuild:
            return context.window_manager.invoke_confirm(self, event)
        return self.execute(context)

    def execute(self, context):
        obj = context.active_object
        errors, warnings = baking.preflight(context, obj, storage=True)
        if errors:
            self.report({'ERROR'}, '; '.join(errors))
            return {'CANCELLED'}
        for warning in warnings:
            self.report({'WARNING'}, warning)
        p, mod = obj.quick_cloth, find_cloth_modifier(obj)
        if mod.point_cache.is_baked and not self.rebuild:
            self.report({'ERROR'}, 'A bake already exists. Use Re-bake to replace it.')
            return {'CANCELLED'}
        self._obj = obj
        self._scene = context.scene
        self._frame = context.scene.frame_current
        try:
            if mod.point_cache.is_baked:
                baking.free(context, obj)
            configure_cloth_from_props(mod, p)
            ensure_stack_order(obj)
            mod.settings.vertex_group_mass = p.pin_group
            if p.use_collision_objects:
                convert_obstacles_to_colliders(context.scene, obj, p.collider_thickness, report=self.report)
            if p.use_wind or p.wind:
                ensure_wind_rig(context, p)
            start, end = baking.effective_range(context.scene, p)
            cache_hygiene(context, context.scene, mod.point_cache, start, end)
            mod.point_cache.use_disk_cache = p.use_disk_cache
            mod.point_cache.use_library_path = False
            p.bake_state, p.bake_error = 'BAKING', ''
            with context.temp_override(object=obj, active_object=obj, point_cache=mod.point_cache):
                if getattr(self, '_interactive', False) and not bpy.app.background:
                    result = bpy.ops.ptcache.bake('INVOKE_DEFAULT', bake=True)
                else:
                    result = bpy.ops.ptcache.bake(bake=True)
            if result == {'CANCELLED'}:
                p.bake_state = 'CANCELLED'
                self._scene.frame_set(self._frame)
                self.report({'WARNING'}, 'Bake cancelled; no complete cache recorded')
                return {'CANCELLED'}
            if result not in ({'FINISHED'}, {'RUNNING_MODAL'}):
                raise RuntimeError(f'Unexpected native bake status: {result}')
            if getattr(self, '_interactive', False) and not bpy.app.background:
                self._timer = context.window_manager.event_timer_add(.5, window=context.window)
                context.window_manager.modal_handler_add(self)
                return {'RUNNING_MODAL'}
            return self.finish(context)
        except Exception as exc:
            p.bake_state, p.bake_error = 'FAILED', str(exc)
            self._scene.frame_set(self._frame)
            self.report({'ERROR'}, f'Bake failed: {exc}')
            return {'CANCELLED'}

    def modal(self, context, event):
        if event.type == 'TIMER':
            self._ticks += 1
            if not self._obj or not find_cloth_modifier(self._obj):
                self.cleanup(context)
                return {'CANCELLED'}
            if not find_cloth_modifier(self._obj).point_cache.is_baking and self._ticks > 2:
                self.cleanup(context)
                try:
                    return self.finish(context)
                except Exception as exc:
                    self._obj.quick_cloth.bake_state = 'FAILED'
                    self._obj.quick_cloth.bake_error = str(exc)
                    self.report({'ERROR'}, f'Bake completion validation failed: {exc}')
                    return {'CANCELLED'}
            for area in context.screen.areas:
                area.tag_redraw()
        # Pass Escape through to Blender's native point-cache job.
        return {'PASS_THROUGH'}

    def cleanup(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

    def finish(self, context):
        obj, p = self._obj, self._obj.quick_cloth
        cache = find_cloth_modifier(obj).point_cache
        expected = baking.effective_range(self._scene, p)
        self._scene.frame_set(self._frame)
        if not cache.is_baked or cache.is_baking or (cache.frame_start, cache.frame_end) != expected:
            p.bake_state = 'CANCELLED'
            self.report({'WARNING'}, 'Bake incomplete or cancelled; no complete result recorded')
            return {'CANCELLED'}
        p.bake_state = 'BAKED'
        p.bake_signature = baking.signature(self._scene, obj)
        p.bake_metadata = json.dumps({'tier': p.quality_mode, 'range': expected,
                                     'blender': bpy.app.version_string,
                                     'utc': datetime.now(timezone.utc).isoformat(),
                                     'settings': baking.settings_signature(p)})
        p.bake_needs_validation = False
        self.report({'INFO'}, f'Baked {p.quality_mode.title()} frames {expected[0]}–{expected[1]}')
        return {'FINISHED'}


class QC_OT_free_bake(Operator):
    """Delete this cloth's saved bake so its settings can be changed and simulated live again"""
    bl_idname = 'quick_cloth.free_bake'
    bl_label = 'Delete Bake'

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        mod = baking.cloth(obj) if obj and obj.type == 'MESH' else None
        return bool(mod and obj.quick_cloth.setup_id and mod.point_cache.is_baked and not baking.any_baking())

    def execute(self, context):
        try:
            baking.free(context, context.active_object)
        except Exception as exc:
            self.report({'ERROR'}, f'Delete Bake failed: {exc}')
            return {'CANCELLED'}
        self.report({'INFO'}, 'Deleted the bake for this cloth')
        return {'FINISHED'}


class QC_OT_apply_as_shape(Operator):
    """Copy the cloth as it looks on this frame into a new, separate object.
Handy for a draped cushion or hung coat; the simulation itself is unchanged"""
    bl_idname = "quick_cloth.apply_as_shape"
    bl_label = "Freeze Frame as New Object"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT'
                and find_cloth_modifier(obj) is not None)

    def execute(self, context):
        obj = context.active_object
        deps = context.evaluated_depsgraph_get()
        obj_eval = obj.evaluated_get(deps)
        try:
            mesh = bpy.data.meshes.new_from_object(
                obj_eval, preserve_all_data_layers=True, depsgraph=deps)
        except Exception as exc:
            self.report({'ERROR'}, f"Could not evaluate the mesh: {exc}")
            return {'CANCELLED'}
        new_obj = bpy.data.objects.new(obj.name + "_Draped", mesh)
        new_obj.matrix_world = obj.matrix_world.copy()
        new_obj.color = obj.color
        for index, slot in enumerate(obj.material_slots):
            if index < len(mesh.materials) and slot.material:
                mesh.materials[index] = slot.material
        context.collection.objects.link(new_obj)
        self.report({'INFO'},
                    f"Created '{new_obj.name}' from frame "
                    f"{context.scene.frame_current}")
        return {'FINISHED'}


class QC_OT_bind_render_mesh(Operator):
    """Make a detailed render mesh follow this simpler cloth (select the render mesh, then the cloth last).
Bind attaches, Rebind re-attaches after edits, Unbind detaches. Do it on the first simulation frame"""
    bl_idname = "quick_cloth.bind_render_mesh"
    bl_label = "Bind Render Mesh"
    bl_options = {'REGISTER', 'UNDO'}
    action: EnumProperty(items=[('BIND', 'Bind', ''), ('REBIND', 'Rebind', ''), ('UNBIND', 'Unbind', '')], default='BIND')

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT':
            return False
        meshes = [o for o in context.selected_objects if o.type == 'MESH']
        return (len(meshes) == 2 and context.active_object in meshes)

    def execute(self, context):
        sim_obj = context.active_object
        render_obj = next(o for o in context.selected_objects
                          if o.type == 'MESH' and o is not sim_obj)

        if object_is_override_locked(render_obj):
            self.report({'ERROR'}, OVERRIDE_MESSAGE)
            return {'CANCELLED'}

        if baking.any_baking():
            self.report({'ERROR'}, 'Wait for the running bake')
            return {'CANCELLED'}
        if any(m.type in {'ARMATURE', 'CLOTH'} for m in render_obj.modifiers):
            self.report({'ERROR'}, 'Use a render mesh without Armature/Cloth; the rig and cloth belong on the simulation proxy')
            return {'CANCELLED'}
        if depends_on(sim_obj, render_obj):
            self.report({'ERROR'}, 'Binding would create a dependency cycle')
            return {'CANCELLED'}
        source_mod = find_cloth_modifier(sim_obj)
        if not source_mod or not sim_obj.quick_cloth.setup_id:
            self.report({'ERROR'}, 'Active object must be the configured simulation proxy')
            return {'CANCELLED'}
        if self.action != 'UNBIND' and context.scene.frame_current != source_mod.point_cache.frame_start:
            self.report({'ERROR'}, 'Move to the simulation start/rest frame before binding')
            return {'CANCELLED'}

        rp = render_obj.quick_cloth
        mod = render_obj.modifiers.get(rp.binding_name) if rp.binding_name else None
        if rp.binding_name and (not mod or mod.type != 'SURFACE_DEFORM' or mod.target != rp.binding_target):
            self.report({'ERROR'}, 'Managed binding was renamed, removed or retargeted; restore its modifier/target before continuing')
            return {'CANCELLED'}
        if mod and mod.is_bound and self.action == 'BIND':
            self.report({'ERROR'}, 'Already bound; choose Rebind or Unbind explicitly')
            return {'CANCELLED'}
        if self.action == 'UNBIND' and (not mod or not mod.is_bound):
            self.report({'ERROR'}, 'No owned bound modifier to unbind')
            return {'CANCELLED'}
        if mod is None:
            mod = render_obj.modifiers.new(name="QC Surface Deform",
                                           type='SURFACE_DEFORM')
            rp.binding_name = mod.name

        was_bound = mod.is_bound
        try:
            with context.temp_override(object=render_obj,
                                       active_object=render_obj,
                                       selected_objects=[render_obj]):
                if mod.is_bound:
                    result = bpy.ops.object.surfacedeform_bind(modifier=mod.name)
                    if result != {'FINISHED'} or mod.is_bound:
                        raise ValueError('Could not unbind owned modifier')
                if self.action != 'UNBIND':
                    mod.target = sim_obj
                    rp.binding_target = sim_obj
                    result = bpy.ops.object.surfacedeform_bind(modifier=mod.name)
                    if result != {'FINISHED'} or not mod.is_bound:
                        raise ValueError('Binding failed; check mesh topology and rest pose')
        except Exception as exc:
            self.report({'ERROR'}, f"Bind failed: {exc}")
            return {'CANCELLED'}

        if self.action == 'UNBIND':
            self.report({'INFO'},
                        f"Unbound '{render_obj.name}' from "
                        f"'{sim_obj.name}'")
        elif mod.is_bound:
            self.report({'INFO'},
                        f"Bound '{render_obj.name}' to sim mesh "
                        f"'{sim_obj.name}' — the render mesh now follows "
                        "the proxy simulation")
        else:
            self.report({'ERROR'},
                        "Binding failed — check for non-manifold geometry, "
                        "extreme scale differences, or an unapplied "
                        "object scale on either mesh")
            return {'CANCELLED'}
        return {'FINISHED'}


class QC_OT_enter_animator_mode(Operator):
    """Hide the cloth and show a light stand-in that follows the rig, so playback stays fast while you animate"""
    bl_idname = 'quick_cloth.enter_animator_mode'
    bl_label = 'Start Animator Mode'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj and obj.type == 'MESH' and context.mode == 'OBJECT'
                    and obj.quick_cloth.setup_id and find_cloth_modifier(obj)
                    and not obj.quick_cloth.garment and not animator_mode_active(obj)
                    and not baking.any_baking())

    def execute(self, context):
        garment = context.active_object
        if object_is_override_locked(garment):
            self.report({'ERROR'}, 'Garment is not editable')
            return {'CANCELLED'}
        p = garment.quick_cloth
        mod = find_cloth_modifier(garment)
        state = {'hidden': garment.hide_get(), 'hide_viewport': garment.hide_viewport,
                 'cloth_viewport': mod.show_viewport}
        try:
            cage = build_or_update_cage(context, garment, p.cage_ratio)
        except Exception as exc:
            self.report({'ERROR'}, f'Cage creation failed: {exc}')
            return {'CANCELLED'}
        p.animator_state = json.dumps(state)
        mod.show_viewport = False
        garment.hide_set(True)
        for obj in context.selected_objects:
            obj.select_set(False)
        cage.select_set(True)
        context.view_layer.objects.active = cage
        self.report({'INFO'}, 'Animator Mode: cloth muted; cage excluded from rendering')
        return {'FINISHED'}


class QC_OT_exit_animator_mode(Operator):
    """Bring the cloth back and hide the stand-in. Also recovers cloth left hidden by Animator Mode"""
    bl_idname = 'quick_cloth.exit_animator_mode'
    bl_label = 'Exit Animator Mode'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return not baking.any_baking() and any(o.type == 'MESH' and o.quick_cloth.animator_state
                                              for o in context.scene.objects)

    def execute(self, context):
        garment, cage = resolve_animator_pair(context.active_object)
        if not garment or not garment.quick_cloth.animator_state:
            candidates = [o for o in context.scene.objects if o.type == 'MESH' and o.quick_cloth.animator_state]
            if len(candidates) != 1:
                self.report({'ERROR'}, 'Select the garment to recover; multiple Animator Mode setups exist')
                return {'CANCELLED'}
            garment = candidates[0]
            cage = find_cage(garment)
        if garment.name not in context.view_layer.objects:
            self.report({'ERROR'}, 'Include the garment collection in this view layer before recovery')
            return {'CANCELLED'}
        p = garment.quick_cloth
        try:
            state = json.loads(p.animator_state)
            if not isinstance(state, dict) or not {'hidden', 'hide_viewport', 'cloth_viewport'} <= state.keys():
                raise ValueError('missing visibility fields')
        except (ValueError, TypeError) as exc:
            self.report({'ERROR'}, f'Saved Animator Mode state is damaged; restore garment visibility manually: {exc}')
            return {'CANCELLED'}
        garment.hide_viewport = state['hide_viewport']
        garment.hide_set(state['hidden'])
        mod = find_cloth_modifier(garment)
        if mod:
            mod.show_viewport = state['cloth_viewport']
        if cage:
            cage.hide_set(True)
            cage.hide_render = True
        p.animator_state = ''
        p.bake_needs_validation = True
        for obj in context.selected_objects:
            obj.select_set(False)
        if not garment.hide_get():
            garment.select_set(True)
        context.view_layer.objects.active = garment
        self.report({'INFO'}, 'Cloth restored; its bake was kept. After animation edits, use Check Bake or Re-bake.')
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# PANELS
# ---------------------------------------------------------------------------
# The parent panel says what the selected object needs next. Numbered child
# panels follow the setup order; rarely changed settings live in closed
# "More ..." sub-panels.

PRESET_HINTS = {
    'SIMPLE': 'Light and quick to solve. Good for testing.',
    'COTTON': 'T-shirts and pants: soft, with small wrinkles.',
    'POLYESTER': 'Springy and floaty; holds its shape.',
    'COUCH_LEATHER': 'Thick upholstery: heavy, big soft folds.',
    'LEATHER_COAT': 'Stiff panels that swing together.',
    'LATEX': 'Skin-tight and stretchy; shrinks onto the body.',
    'STRETCH_DENIM': 'Jeans with stretch: a light hug fit.',
    'RIGID_DENIM': 'Classic heavy denim with structured folds.',
    'SELVEDGE_DENIM': 'The stiffest fabric: boardy, holds creases.',
}

QUALITY_HINTS = {
    'PREVIEW': '20 steps per frame. Fast: for checking timing.',
    'LOW': '32 steps per frame. Quick drafts.',
    'MEDIUM': '64 steps per frame. Good for most shots.',
    'HIGH': '120 steps per frame. Slow: fast motion, tight contact.',
    'CUSTOM': 'Type any number of steps per frame. More is smoother and slower.',
    'FINAL': 'Values kept from an older Quick Cloth version.',
}

# Cache state -> (icon, headline, explanation)
STATE_TEXT = {
    'READY': ('PLAY', 'Set up and ready',
              'Press Play (Space) from the first frame to preview, or Bake to save the result.'),
    'BAKING': ('TIME', 'Baking...', 'Press Esc to cancel.'),
    'BAKED': ('CHECKMARK', 'Baked and up to date',
              'Playback and renders use the saved result. To change settings, edit them and Re-bake.'),
    'DIRTY': ('ERROR', 'Bake is out of date',
              'Settings or frames changed since the bake. Re-bake to see the changes.'),
    'NEEDS_VALIDATION': ('QUESTION', 'Bake needs a check',
                         'The scene changed or the file was reopened. Press Check Bake, or Re-bake.'),
    'FAILED': ('CANCEL', 'Last bake failed', 'See the message in step 4, fix it, then Bake again.'),
    'CANCELLED': ('CANCEL', 'Last bake was cancelled', 'Press Bake to try again.'),
}


def show_hints(context):
    addon = context.preferences.addons.get(__package__)
    prefs = addon.preferences if addon else None
    return prefs is None or prefs.show_hints


def wrapped(layout, context, text, icon='NONE'):
    """Labels don't wrap in Blender; split text to the sidebar width."""
    width = context.region.width if context.region else 300
    margin = 70 if icon != 'NONE' else 45
    chars = max(18, int((width - margin) / (5.8 * context.preferences.view.ui_scale)))
    col = layout.column(align=True)
    col.scale_y = .8
    for index, line in enumerate(textwrap.wrap(text, chars) or ['']):
        col.label(text=line, icon=icon if index == 0 else ('BLANK1' if icon != 'NONE' else 'NONE'))


def hint(layout, context, text):
    """Help text the user can hide with the ? button in the panel header."""
    if show_hints(context):
        wrapped(layout, context, text, icon='INFO')


_short_edges = {}


def cached_short_edge(obj):
    """short_edge_length for drawing; recomputed when topology or scale changes."""
    if obj is None or obj.type != 'MESH' or obj.mode == 'EDIT':
        return 0.0
    key = (obj.data.as_pointer(), len(obj.data.vertices), len(obj.data.edges),
           tuple(round(v, 5) for v in obj.matrix_world.to_scale()))
    if key not in _short_edges:
        if len(_short_edges) > 64:
            _short_edges.clear()
        _short_edges[key] = short_edge_length(obj)
    return _short_edges[key]


def is_cage(obj):
    return bool(obj and obj.get('qc_helper') == 'cage')


def is_set_up(obj):
    return bool(obj.quick_cloth.setup_id and find_cloth_modifier(obj))


class QCPanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Quick Cloth'


class QCStepPanel(QCPanel):
    """Child panel shown for a garment mesh (not the Animator Mode stand-in)."""
    bl_parent_id = 'QC_PT_panel'

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj and obj.type == 'MESH' and not is_cage(obj))


class QC_PT_panel(QCPanel, Panel):
    bl_label = "Quick Cloth"
    bl_idname = "QC_PT_panel"

    def draw_header_preset(self, context):
        addon = context.preferences.addons.get(__package__)
        if addon and addon.preferences:
            self.layout.prop(addon.preferences, 'show_hints', text='', icon='HELP')

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        box = layout.box()
        if obj is None or obj.type != 'MESH':
            box.label(text='Nothing to simulate yet', icon='RESTRICT_SELECT_OFF')
            wrapped(box, context, 'Select the mesh you want to turn into cloth.')
            return
        if is_cage(obj) or obj.quick_cloth.animator_state:
            box.label(text='Animator Mode is on', icon='ARMATURE_DATA')
            wrapped(box, context, 'The cloth is hidden and a light stand-in follows the rig '
                                  'so playback stays fast. Exit to bring the cloth back.')
            box.operator('quick_cloth.exit_animator_mode', icon='LOOP_BACK')
            return
        p = obj.quick_cloth
        if QC_OT_adopt.poll(context):
            if p.setup_id:
                box.label(text='Copied cloth setup', icon='DUPLICATE')
                wrapped(box, context, 'Give this copy its own settings so it can be baked separately.')
                box.operator('quick_cloth.adopt', text='Make Independent Copy', icon='IMPORT')
            else:
                box.label(text='This mesh already has cloth', icon='MOD_CLOTH')
                wrapped(box, context, 'Adopt it to manage it here. Its settings and any bake '
                                      'stay exactly as they are.')
                box.operator('quick_cloth.adopt', icon='IMPORT')
            return
        if not is_set_up(obj):
            box.label(text='Not set up yet', icon='MOD_CLOTH')
            wrapped(box, context, 'Go through steps 1-3 (only Fabric is required), '
                                  'then press Set Up Cloth in step 4.')
            return
        icon, headline, text = STATE_TEXT[baking.state(context, obj)]
        box.label(text=headline, icon=icon)
        wrapped(box, context, text)


class QC_PT_fabric(QCStepPanel, Panel):
    bl_label = "1. Fabric"
    bl_idname = "QC_PT_fabric"

    def draw(self, context):
        layout = self.layout
        layout.enabled = not baking.any_baking()
        props = get_props(context)
        hint(layout, context, 'What is the cloth made of? A fabric fills in the settings below; '
                              'you can still change them.')
        layout.prop(props, "preset", text="")
        wrapped(layout, context, PRESET_HINTS.get(props.preset, ''))
        col = layout.column(align=True)
        col.prop(props, "mass")
        col.prop(props, "air_damping")


class QC_PT_fabric_detail(QCStepPanel, Panel):
    bl_label = "Fine-Tune Fabric"
    bl_parent_id = "QC_PT_fabric"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.enabled = not baking.any_baking()
        props = get_props(context)
        hint(layout, context, 'Stiffness: how much the cloth resists each kind of change. '
                              'Damping: how quickly bouncing settles.')
        col = layout.column(align=True)
        col.label(text="Stiffness")
        col.prop(props, "tension_stiffness")
        col.prop(props, "compression_stiffness")
        col.prop(props, "shear_stiffness")
        col.prop(props, "bending_stiffness")
        col = layout.column(align=True)
        col.label(text="Damping")
        col.prop(props, "tension_damping")
        col.prop(props, "compression_damping")
        col.prop(props, "shear_damping")
        col.prop(props, "bending_damping")
        layout.prop(props, "time_scale")
        layout.prop(props, "use_internal_springs")
        if props.use_internal_springs:
            layout.prop(props, "internal_stiffness")


class QC_PT_fabric_shape(QCStepPanel, Panel):
    bl_label = "Shrink, Seams & Inflation"
    bl_parent_id = "QC_PT_fabric"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.enabled = not baking.any_baking()
        props = get_props(context)
        layout.prop(props, "fit_tightness")
        if props.legacy_fit:
            wrapped(layout, context, 'Kept the adopted cloth\'s original shrink value.', icon='INFO')
        layout.prop(props, "use_sewing")
        if props.use_sewing:
            layout.prop(props, "sewing_force")
        layout.prop(props, "use_pressure")
        if props.use_pressure:
            col = layout.column(align=True)
            col.prop(props, "pressure_force")
            col.prop(props, "pressure_target_volume")


class QC_PT_pins(QCStepPanel, Panel):
    bl_label = "2. Pins"
    bl_idname = "QC_PT_pins"

    def draw(self, context):
        layout = self.layout
        layout.enabled = not baking.any_baking()
        obj = context.active_object
        props = get_props(context)
        hint(layout, context, 'Pinned vertices stick to the object or its rig, like a collar or '
                              'waistband; the rest hangs freely. A loose sheet needs no pins.')
        col = layout.column(align=True)
        col.label(text='Pin Group')
        col.prop_search(props, 'pin_group', obj, 'vertex_groups', text='')
        if not props.pin_group:
            found = find_pin_group(obj)
            if found is not None:
                layout.label(text=f"Will use the '{found.name}' group", icon='GROUP_VERTEX')
        else:
            layout.label(text=f'Pinned: {props.coverage_text}', icon='GROUP_VERTEX')
        layout.operator("quick_cloth.set_pin_group", icon='PINNED')
        if context.mode != 'EDIT_MESH':
            hint(layout, context, 'To pin by hand: Tab into Edit Mode, select vertices, '
                                  'then press Pin Selected Vertices.')
        if any(m.type == 'ARMATURE' and m.object for m in obj.modifiers):
            layout.operator("quick_cloth.pin_from_rig_weights", icon='ARMATURE_DATA')
            hint(layout, context, 'Pins every vertex the rig moves. Afterwards, paint pin '
                                  'weights down where the cloth should swing.')
        layout.prop(props, "pin_stiffness")


class QC_PT_pins_more(QCStepPanel, Panel):
    bl_label = "More Pin Options"
    bl_parent_id = "QC_PT_pins"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.layout.enabled = not baking.any_baking()
        self.layout.prop(get_props(context), 'dynamic_mesh')


class QC_PT_collisions(QCStepPanel, Panel):
    bl_label = "3. Collisions"
    bl_idname = "QC_PT_collisions"

    def draw(self, context):
        layout = self.layout
        layout.enabled = not baking.any_baking()
        props = get_props(context)
        hint(layout, context, 'Choose what the cloth rests on or wraps around: the main body, '
                              'plus any other meshes in the list. Only colliders are felt by the cloth.')
        col = layout.column(align=True)
        col.label(text='Main Body')
        col.prop(props, 'body', text='')
        layout.label(text='More Colliders')
        row = layout.row()
        row.template_list('QC_UL_colliders', '', props, 'colliders', props, 'collider_index', rows=3)
        side = row.column(align=True)
        side.operator('quick_cloth.collider_add', icon='ADD', text='')
        side.operator('quick_cloth.collider_remove', icon='REMOVE', text='')
        targets = baking.collision_targets(props)
        missing = [o for o in targets if not baking.is_collider(o)]
        if missing:
            wrapped(layout, context, f"Not colliders yet: {', '.join(o.name for o in missing)}", icon='ERROR')
            layout.operator('quick_cloth.body_collider', icon='MOD_PHYSICS')
        elif targets:
            layout.label(text=f'{len(targets)} collider(s) ready', icon='CHECKMARK')
        layout.operator("quick_cloth.make_colliders", icon='MESH_ICOSPHERE')
        layout.prop(props, "use_self_collision")
        if props.use_self_collision:
            layout.prop(props, "self_distance")
            short = cached_short_edge(context.active_object)
            if short > 0 and props.self_distance > short / 3:
                wrapped(layout, context, f'Too large for this mesh (short edges {short * 1000:.1f} mm): '
                                         'the cloth will jitter or explode', icon='ERROR')
                layout.operator('quick_cloth.fit_self_gap', icon='CHECKMARK')
            elif short > 0:
                hint(layout, context, f'Keep it under a third of the short edges ({short * 1000:.1f} mm).')
        layout.operator('quick_cloth.diagnose', icon='VIEWZOOM')
        for message in props.diagnostics.splitlines():
            wrapped(layout, context, message, icon='INFO')


class QC_UL_colliders(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, 'object', text='', emboss=True)
        if item.object is not None:
            ready = baking.is_collider(item.object)
            row.label(text='', icon='CHECKMARK' if ready else 'ERROR')


class QC_PT_collisions_more(QCStepPanel, Panel):
    bl_label = "More Collision Options"
    bl_parent_id = "QC_PT_collisions"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.enabled = not baking.any_baking()
        props = get_props(context)
        obj = context.active_object
        layout.prop(props, 'use_object_collision')
        layout.prop(props, "object_distance")
        layout.prop(props, 'collider_thickness')
        col = layout.column(align=True)
        col.prop(props, 'impulse_clamp')
        col.prop(props, 'self_impulse_clamp')
        layout.prop(props, "use_collision_objects")
        colliders = [o for o in context.scene.objects if o != obj and any(
            m.type == 'COLLISION' and m.show_viewport for m in o.modifiers)]
        layout.label(text=f'{len(colliders)} collider(s) in this scene')


class QC_PT_bake(QCStepPanel, Panel):
    bl_label = "4. Simulate & Bake"
    bl_idname = "QC_PT_bake"

    def draw(self, context):
        layout = self.layout
        layout.enabled = not baking.any_baking()
        obj = context.active_object
        props = get_props(context)
        hint(layout, context, 'Set Up Cloth applies your settings; press Play to preview. '
                              'Bake saves the result so it plays fast and renders the same every time.')
        row = layout.row(align=True)
        row.prop(props, "frame_start", text="Start")
        row.prop(props, "frame_end", text="End")
        try:
            start, end = baking.effective_range(context.scene, props)
            layout.label(text=f'Simulates frames {start}–{end} ({end - start + 1} frames)')
        except ValueError as exc:
            wrapped(layout, context, str(exc), icon='ERROR')

        layout.label(text="Quality")
        # Five tiers don't fit one row in the default sidebar width.
        grid = layout.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
        for tier in ('PREVIEW', 'LOW', 'MEDIUM', 'HIGH', 'CUSTOM'):
            op = grid.operator('quick_cloth.quality', text=tier.title(), depress=props.quality_mode == tier)
            op.tier = tier
        if props.quality_mode == 'CUSTOM':
            layout.prop(props, 'quality_steps', text='Steps per Frame')
        wrapped(layout, context, QUALITY_HINTS.get(props.quality_mode, ''))

        mod = baking.cloth(obj)
        baked = bool(mod and mod.point_cache.is_baked)
        set_up = is_set_up(obj)
        layout.separator()
        if not baked:
            row = layout.row()
            row.scale_y = 1.5
            row.operator("quick_cloth.simulate", icon='MOD_CLOTH',
                         text='Update Cloth Settings' if set_up else 'Set Up Cloth')
        if set_up:
            row = layout.row(align=True)
            row.scale_y = 1.3
            op = row.operator('quick_cloth.bake', text='Re-bake' if baked else 'Bake',
                              icon='RENDER_ANIMATION')
            op.rebuild = baked
            row.operator("quick_cloth.free_bake", icon='TRASH')
            if baked and baking.state(context, obj) in {'DIRTY', 'NEEDS_VALIDATION'}:
                layout.operator('quick_cloth.validate_bake', icon='CHECKMARK')
            errors, warnings = baking.preflight(context, obj)
            for error in errors[:2]:
                wrapped(layout, context, error, icon='ERROR')
            for warning in warnings[:2]:
                wrapped(layout, context, warning, icon='INFO')
        if props.bake_error:
            wrapped(layout, context, props.bake_error, icon='ERROR')


class QC_PT_bake_more(QCStepPanel, Panel):
    bl_label = "More Simulation Options"
    bl_parent_id = "QC_PT_bake"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.enabled = not baking.any_baking()
        props = get_props(context)
        layout.prop(props, "settle_frames")
        layout.prop(props, "use_preview_range")
        layout.prop(props, "use_disk_cache")
        if props.use_disk_cache:
            try:
                wrapped(layout, context, str(baking.cache_directory()), icon='FILE_FOLDER')
            except ValueError as exc:
                wrapped(layout, context, str(exc), icon='ERROR')
        col = layout.column(align=True)
        col.prop(props, "quality_steps")
        col.prop(props, "collision_quality")
        steps, collisions = resolve_quality(props)
        layout.label(text=f'In use: {steps} solver / {collisions} collision steps')


class QC_PT_forces(QCStepPanel, Panel):
    bl_label = "Wind & Gravity"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.enabled = not baking.any_baking()
        props = get_props(context)
        layout.prop(props, "gravity_influence")
        layout.prop(props, "use_wind")
        if props.use_wind:
            hint(layout, context, 'The wind is created or updated when you press Set Up Cloth.')
            layout.prop(props, "wind_direction")
            col = layout.column(align=True)
            col.prop(props, "wind_strength")
            col.prop(props, "wind_turbulence")
            col.prop(props, "wind_seed")
        layout.operator("quick_cloth.remove_wind", icon='X')


class QC_PT_animator(QCStepPanel, Panel):
    bl_label = "Animator Mode"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.enabled = not baking.any_baking()
        props = get_props(context)
        hint(layout, context, 'Hides the cloth and shows a light stand-in that follows the rig, '
                              'so playback stays fast while you animate. No cloth is solved.')
        layout.prop(props, "cage_ratio")
        layout.operator("quick_cloth.enter_animator_mode", icon='MESH_GRID')
        if QC_OT_exit_animator_mode.poll(context):
            layout.operator('quick_cloth.exit_animator_mode', text='Recover Hidden Cloth',
                            icon='HIDE_OFF')


class QC_PT_proxy(QCStepPanel, Panel):
    bl_label = "Render Mesh & Snapshot"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.enabled = not baking.any_baking()
        hint(layout, context, 'Let a detailed render mesh follow this simpler cloth: select the '
                              'render mesh, Shift-click this cloth last, go to the first frame, '
                              'then press Bind.')
        row = layout.row(align=True)
        for action in ('BIND', 'REBIND', 'UNBIND'):
            op = row.operator('quick_cloth.bind_render_mesh', text=action.title())
            op.action = action
        hint(layout, context, 'Freeze the cloth as it looks on this frame into a new object.')
        layout.operator("quick_cloth.apply_as_shape", icon='MESH_DATA')


class QCPreferences(AddonPreferences):
    bl_idname = __package__

    show_hints: BoolProperty(
        name="Show Help Text",
        description="Show short explanations in the Quick Cloth panel. "
                    "Toggle with the ? button in the panel header",
        default=True,
    )

    def draw(self, context):
        self.layout.prop(self, 'show_hints')


# ---------------------------------------------------------------------------
# REGISTRATION
# ---------------------------------------------------------------------------

classes = (
    QCPreferences,
    QCSetupRef,
    QCColliderItem,
    QuickClothProps,
    QC_OT_adopt,
    QC_OT_quality,
    QC_OT_simulate,
    QC_OT_set_pin_group,
    QC_OT_pin_from_rig_weights,
    QC_OT_make_colliders,
    QC_OT_fit_self_gap,
    QC_OT_body_collider,
    QC_OT_collider_add,
    QC_OT_collider_remove,
    QC_OT_remove_wind,
    QC_OT_bake,
    QC_OT_validate_bake,
    QC_OT_diagnose,
    QC_OT_free_bake,
    QC_OT_apply_as_shape,
    QC_OT_bind_render_mesh,
    QC_OT_enter_animator_mode,
    QC_OT_exit_animator_mode,
    QC_PT_panel,
    QC_PT_fabric,
    QC_PT_fabric_detail,
    QC_PT_fabric_shape,
    QC_PT_pins,
    QC_PT_pins_more,
    QC_PT_collisions,
    QC_UL_colliders,
    QC_PT_collisions_more,
    QC_PT_bake,
    QC_PT_bake_more,
    QC_PT_forces,
    QC_PT_animator,
    QC_PT_proxy,
)

_registered = []


def register():
    if _registered:
        return
    try:
        for cls in classes:
            bpy.utils.register_class(cls)
            _registered.append(cls)
        bpy.types.Scene.quick_cloth = PointerProperty(type=QuickClothProps)
        bpy.types.Object.quick_cloth = PointerProperty(type=QuickClothProps)
        bpy.types.Scene.quick_cloth_registry = CollectionProperty(type=QCSetupRef)
        bpy.app.handlers.load_post.append(baking.on_load)
        bpy.app.handlers.depsgraph_update_post.append(baking.on_update)
    except Exception:
        unregister()
        raise


def unregister():
    for handlers, callback in ((bpy.app.handlers.load_post, baking.on_load),
                               (bpy.app.handlers.depsgraph_update_post, baking.on_update)):
        if callback in handlers:
            handlers.remove(callback)
    if hasattr(bpy.types.Scene, "quick_cloth"):
        del bpy.types.Scene.quick_cloth
    if hasattr(bpy.types.Scene, 'quick_cloth_registry'):
        del bpy.types.Scene.quick_cloth_registry
    if hasattr(bpy.types.Object, 'quick_cloth'):
        del bpy.types.Object.quick_cloth
    for cls in reversed(_registered):
        bpy.utils.unregister_class(cls)
    _registered.clear()


if __name__ == "__main__":
    register()
