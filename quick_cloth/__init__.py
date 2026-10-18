"""
Quick Cloth — one-click, preset-driven cloth simulation for animators.

Sister addon to Quick Break. Wraps Blender's native cloth simulator in a
single clean N-panel: pick a fabric preset, click "Simulate Cloth!", and get
believable cloth — with every raw parameter still exposed for tweaking.

Key design rules (shared with Quick Break):
  * Presets are STARTING POINTS. Selecting one writes a full dictionary of
    values into the PropertyGroup (and into a live cloth modifier if one
    exists); every slider stays editable afterwards.
  * NO collision collections are ever created or assigned. The cloth
    modifier's collision collection stays None so the cloth interacts with
    every collision object in the scene, each one independently.
  * Point-cache hygiene is built in: the cache never starts on a frame the
    timeline cannot reach, stale bakes are freed, and the playhead is
    rewound so simulations never silently freeze.
  * Idempotent everywhere: re-running the main operator reuses the existing
    cloth modifier, wind rig, and colliders. Nothing stacks or duplicates.

Blender 4.1+ (legacy addon) and 4.2+ (native Extension via manifest).
NOTE on 4.4 slotted/layered actions: this addon never reads
object.animation_data.action.fcurves directly; if that ever becomes
necessary, wrap it in try/except (the data model changed in 4.4).
"""

bl_info = {
    "name": "Quick Cloth",
    "author": "Quick Physics Tools",
    "version": (1, 0, 3),
    "blender": (4, 1, 0),
    "location": "3D Viewport > Sidebar (N) > Quick Cloth",
    "description": "One-click preset-driven cloth simulation for animators",
    "category": "Physics",
}

# ---------------------------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------------------------

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
)
from bpy.types import Operator, Panel, PropertyGroup
from mathutils import Vector

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
        "self_distance": 0.010,
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
        "self_distance": 0.010,
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
        "bending_damping": 15.0,
        "air_damping": 1.0,
        "quality_steps": 15,
        "collision_quality": 4,
        "time_scale": 0.9,  # a touch slow-motion = reads as heavy
        "use_self_collision": False,
        "self_distance": 0.020,
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
        "bending_damping": 8.0,
        "air_damping": 1.2,
        "quality_steps": 12,
        "collision_quality": 4,
        "time_scale": 1.0,
        "use_self_collision": True,
        "self_distance": 0.012,
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
        "self_distance": 0.006,
        "object_distance": 0.015,
        "fit_tightness": -0.12,       # negative shrink tightens onto the body
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
        "self_distance": 0.010,
        "object_distance": 0.015,
        "fit_tightness": -0.04,       # light hug fit
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
        "self_distance": 0.012,
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
        "self_distance": 0.012,
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
     "the body (negative fit + self-collision + sewing)"),
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
        setattr(self, key, value)

    # Push into a live modifier if one exists on the active object.
    obj = getattr(context, "active_object", None)
    if obj is not None and obj.type == 'MESH':
        mod = find_cloth_modifier(obj)
        if mod is not None:
            configure_cloth_from_props(mod, self, preview=(self.quality_mode == 'PREVIEW'))


# ---------------------------------------------------------------------------
# PROPERTY GROUP
# ---------------------------------------------------------------------------

class QuickClothProps(PropertyGroup):
    """All Quick Cloth settings, stored on the Scene."""

    preset: EnumProperty(
        name="Fabric Preset",
        description="One-click fabric starting point. Selecting a preset "
                    "rewrites every physics value below (and updates a live "
                    "cloth modifier immediately) — then every slider stays "
                    "fully editable",
        items=PRESET_ITEMS,
        default="SIMPLE",
        update=apply_preset,
    )

    # --- Fabric physics -----------------------------------------------------
    mass: FloatProperty(
        name="Vertex Mass",
        description="Mass per vertex in kilograms. Heavier fabric hangs "
                    "straighter and resists wind. Nominal — the visual weight "
                    "also depends on mesh density, so treat this as a feel "
                    "dial, not a scale reading",
        default=0.30, min=0.001, max=10.0, unit='MASS',
    )
    tension_stiffness: FloatProperty(
        name="Tension",
        description="Resistance to being stretched. High values keep edge "
                    "lengths fixed (denim, leather); low values let the "
                    "fabric elongate (latex, jersey)",
        default=15.0, min=0.0, max=10000.0,
    )
    compression_stiffness: FloatProperty(
        name="Compression",
        description="Resistance to being squashed along its surface. Low "
                    "values buckle into fine wrinkles; high values push back "
                    "into large folds",
        default=15.0, min=0.0, max=10000.0,
    )
    shear_stiffness: FloatProperty(
        name="Shear",
        description="Resistance to diagonal distortion (a square becoming a "
                    "rhombus). Woven fabrics shear less than knits",
        default=5.0, min=0.0, max=10000.0,
    )
    bending_stiffness: FloatProperty(
        name="Bending",
        description="Resistance to folding out of plane. THE fabric-character "
                    "dial: near zero = silk/latex follows every curve, high = "
                    "leather/cardboard makes few big folds",
        default=0.5, min=0.0, max=10000.0,
    )
    tension_damping: FloatProperty(
        name="Tension Damping",
        description="How fast stretch oscillations die out. Higher = less "
                    "springy, more settled motion",
        default=5.0, min=0.0, max=50.0,
    )
    compression_damping: FloatProperty(
        name="Compression Damping",
        description="How fast squash oscillations die out",
        default=5.0, min=0.0, max=50.0,
    )
    shear_damping: FloatProperty(
        name="Shear Damping",
        description="How fast diagonal jiggle dies out",
        default=5.0, min=0.0, max=50.0,
    )
    bending_damping: FloatProperty(
        name="Bending Damping",
        description="How fast flapping and fold oscillation dies out. High "
                    "values make creases read as 'held' (selvedge denim)",
        default=0.5, min=0.0, max=1000.0,
    )
    air_damping: FloatProperty(
        name="Air Damping",
        description="Air resistance. Higher values make fabric floaty and "
                    "slow-falling (polyester); lower values let it drop fast",
        default=1.0, min=0.0, max=10.0,
    )
    time_scale: FloatProperty(
        name="Time Scale",
        description="Simulation speed multiplier. Below 1.0 reads as heavier/"
                    "slower fabric. Use this instead of changing scene FPS — "
                    "bakes are FPS-dependent",
        default=1.0, min=0.01, max=10.0,
    )
    show_fabric_detail: BoolProperty(
        name="Fabric Detail",
        description="Show the individual stiffness and damping sliders",
        default=False,
    )
    use_internal_springs: BoolProperty(
        name="Internal Springs",
        description="Add volume-preserving springs through the cloth's "
                    "thickness. Used by the Couch Leather preset so cushions "
                    "keep their bulk",
        default=False,
    )
    internal_stiffness: FloatProperty(
        name="Internal Stiffness",
        description="Stiffness of the internal volume springs",
        default=5.0, min=0.0, max=10000.0,
    )

    # --- Garment ------------------------------------------------------------
    pin_stiffness: FloatProperty(
        name="Pin Stiffness",
        description="How rigidly pinned vertices hold to their animated "
                    "position. 1.0 = welded; lower values let pins lag and "
                    "stretch. Pinned vertices follow the object's own "
                    "animation — animate or rig the object to drag a cape "
                    "around",
        default=1.0, min=0.0, max=1.0, subtype='FACTOR',
    )
    fit_tightness: FloatProperty(
        name="Fit Tightness",
        description="Shrink factor. NEGATIVE values shrink the garment onto "
                    "the body (latex, stretch denim); positive values let it "
                    "slacken. Needs a body collider to hug against",
        default=0.0, min=-0.3, max=0.3,
    )
    use_sewing: BoolProperty(
        name="Use Sewing",
        description="Pull sewing-spring edges together — for garments "
                    "modeled as flat panels joined by loose edges (marvelous-"
                    "designer style). The Latex preset enables this",
        default=False,
    )
    sewing_force: FloatProperty(
        name="Sewing Force",
        description="Maximum force pulling sewing edges together",
        default=0.5, min=0.0, max=10000.0,
    )
    use_pressure: BoolProperty(
        name="Pressure",
        description="Inflate the cloth with internal pressure — puffer "
                    "jackets, balloons, inflatables",
        default=False,
    )
    pressure_force: FloatProperty(
        name="Pressure Force",
        description="Uniform internal pressure. Positive inflates, negative "
                    "deflates",
        default=1.0, min=-10000.0, max=10000.0,
    )
    pressure_target_volume: FloatProperty(
        name="Target Volume",
        description="Volume the pressure tries to maintain (0 = disabled, "
                    "use raw force only)",
        default=0.0, min=0.0, max=10000.0,
    )

    # --- Forces -------------------------------------------------------------
    use_wind: BoolProperty(
        name="Add Wind",
        description="On Simulate, create (or reuse) the QC_Wind force-field "
                    "rig: a Wind empty aimed along the direction below plus a "
                    "parented Turbulence field for gusts",
        default=False,
    )
    wind_direction: FloatVectorProperty(
        name="Direction",
        description="World-space direction the wind blows toward",
        default=(1.0, 0.0, 0.0), subtype='XYZ', size=3,
    )
    wind_strength: FloatProperty(
        name="Strength",
        description="Wind force-field strength",
        default=1000.0, min=0.0, max=100000.0,
    )
    wind_turbulence: FloatProperty(
        name="Turbulence",
        description="Strength of the gust/noise field parented to the wind. "
                    "0 = perfectly steady wind",
        default=250.0, min=0.0, max=100000.0,
    )
    wind_seed: IntProperty(
        name="Wind Seed",
        description="Random seed for the turbulence noise. Re-roll it for a "
                    "different gust pattern without changing the wind's "
                    "average behavior — same idea as Quick Break's Break/"
                    "Shrapnel seeds",
        default=0, min=0, max=10000,
    )
    gravity_influence: FloatProperty(
        name="Gravity Influence",
        description="How much scene gravity affects this cloth (0–1). Lower "
                    "it to float heavy fabrics for stylized shots",
        default=1.0, min=0.0, max=1.0, subtype='FACTOR',
    )

    # --- Collisions ---------------------------------------------------------
    use_collision_objects: BoolProperty(
        name="Use Collision Objects",
        description="On Simulate, automatically give a Collision modifier to "
                    "every rigid-body mesh in the scene that lacks one, so "
                    "obstacles just work. Each object is converted "
                    "individually — no collision collection is ever created; "
                    "the cloth collides with everything in the scene",
        default=True,
    )
    object_distance: FloatProperty(
        name="Object Distance",
        description="Minimum distance kept between the cloth and collision "
                    "objects. Raise it if the cloth pokes through obstacles",
        default=0.015, min=0.001, max=1.0, unit='LENGTH',
    )
    use_self_collision: BoolProperty(
        name="Self Collision",
        description="Stop the cloth passing through itself. Required for "
                    "skin-tight fits and layered folds; costs solve time",
        default=False,
    )
    self_distance: FloatProperty(
        name="Self Distance",
        description="Minimum distance the cloth keeps from itself. Too large "
                    "= puffy; too small = misses collisions and explodes",
        default=0.015, min=0.001, max=0.1, unit='LENGTH',
    )

    # --- Simulation ---------------------------------------------------------
    quality_mode: EnumProperty(
        name="Quality Mode",
        description="Preview halves Quality Steps and Collision Quality and "
                    "disables self-collision (unless the preset mandates it, "
                    "like Latex) — non-destructively, at configure time. "
                    "Final uses your stored values verbatim",
        items=[
            ("PREVIEW", "Preview",
             "Fast blocking quality: halved steps, self-collision off unless "
             "the preset requires it. Your stored slider values are untouched"),
            ("FINAL", "Final",
             "Full quality using the stored values verbatim — flip to this "
             "before baking"),
        ],
        default="FINAL",
    )
    frame_start: IntProperty(
        name="Start Frame",
        description="First frame of the SHOT. The simulation itself starts "
                    "Settle Frames earlier so the garment is already draped "
                    "here",
        default=1,
    )
    frame_end: IntProperty(
        name="End Frame",
        description="Last frame of the simulation",
        default=250,
    )
    settle_frames: IntProperty(
        name="Settle Frames",
        description="Pre-roll: the simulation starts this many frames BEFORE "
                    "the shot's start frame so the garment is already draped "
                    "when the shot begins. The scene start frame is extended "
                    "down automatically if needed (the cache must always be "
                    "reachable on the timeline). Animate the character "
                    "holding its first pose during the settle window",
        default=15, min=0, max=120,
    )
    use_preview_range: BoolProperty(
        name="Use Preview Range",
        description="When the timeline's preview range is active, take the "
                    "shot start/end from it instead of the fields above",
        default=False,
    )
    quality_steps: IntProperty(
        name="Quality Steps",
        description="Simulation substeps per frame. The main speed/accuracy "
                    "dial: scale it down for viewport previews, up for final "
                    "bakes. Too low = stretchy, unstable cloth",
        default=5, min=1, max=80,
    )
    collision_quality: IntProperty(
        name="Collision Quality",
        description="Collision solver iterations. Raise it if fast-moving "
                    "cloth tunnels through obstacles",
        default=3, min=1, max=20,
    )
    use_disk_cache: BoolProperty(
        name="Disk Cache",
        description="Store the bake on disk next to the .blend (library-path "
                    "aware) so it survives file relinking and render farms",
        default=False,
    )

    # --- Animator Mode --------------------------------------------------
    cage_ratio: FloatProperty(
        name="Cage Detail",
        description="Polygon ratio of the animation cage relative to the "
                    "garment (0.05 = 5% of the faces). The cage is a "
                    "decimated stand-in that follows the same rig with the "
                    "cloth sim fully muted — no solving, no cache RAM — so "
                    "playback stays fast while you animate",
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
    for group in obj.vertex_groups:
        if _normalize(group.name) in PIN_GROUP_ALIASES:
            return group
    return None


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
        if mod.type == 'ARMATURE' and arm_index is None:
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

    `preview` applies the Preview/Final scaling NON-destructively: it scales
    values at configure time and never overwrites the stored sliders.
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
        s.internal_spring_max_length = 0.0
        s.internal_tension_stiffness = props.internal_stiffness
        s.internal_compression_stiffness = props.internal_stiffness

    # Gravity influence
    s.effector_weights.gravity = props.gravity_influence

    # Pinning
    s.pin_stiffness = props.pin_stiffness

    # Quality — Preview halves steps (min 3) and collision quality (min 2)
    # and drops self-collision unless the preset mandates it (LATEX).
    if preview:
        # Stiffness-aware floor: stiff springs oscillate (jitter) when the
        # substep count is too low for them, so Preview may halve the steps
        # but never below what the fabric's stiffness can tolerate.
        stiffness = max(props.tension_stiffness, props.bending_stiffness)
        if stiffness >= 50.0:
            steps_floor = 8
        elif stiffness >= 20.0:
            steps_floor = 6
        else:
            steps_floor = 3
        s.quality = max(steps_floor, props.quality_steps // 2)
        c.collision_quality = max(2, props.collision_quality // 2)
        preset_mandates_self = PRESETS.get(props.preset, {}).get("use_self_collision", False) and props.preset == 'LATEX'
        c.use_self_collision = props.use_self_collision if preset_mandates_self else False
    else:
        s.quality = props.quality_steps
        c.collision_quality = props.collision_quality
        c.use_self_collision = props.use_self_collision

    c.distance_min = props.object_distance
    c.self_distance_min = props.self_distance

    # Anti-jitter: cap collision repulsion impulses. Unclamped impulses are
    # the main source of at-rest micro-jitter when self-collision or tight
    # collision distances are active (0 = unclamped in Blender, so we set a
    # finite ceiling).
    c.impulse_clamp = 25.0
    c.self_impulse_clamp = 25.0

    # CRITICAL: no collision collection, ever. Leaving it None makes the
    # cloth interact with EVERY collision object in the scene, each one
    # independently. (The word "collection" appears here only to document
    # that none is used.)
    c.collection = None


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
        if obj.library is not None:
            # Linked data can't take new modifiers; skip quietly but note it.
            if report is not None:
                report({'WARNING'}, f"Skipped linked object '{obj.name}' — "
                                    "can't add a Collision modifier to linked data")
            continue
        obj.modifiers.new(name="QC Collision", type='COLLISION')
        col = obj.collision
        if col is not None:
            col.thickness_outer = 0.02
            col.damping = 0.1
        converted += 1
    return converted


def make_collider(obj):
    """Add (or reuse) a tuned Collision modifier on a single object.
    Never touches the rest of the modifier stack — rigged meshes stay
    rigged."""
    if not any(m.type == 'COLLISION' for m in obj.modifiers):
        obj.modifiers.new(name="QC Collision", type='COLLISION')
    col = obj.collision
    if col is not None:
        col.thickness_outer = 0.02
        col.damping = 0.1


def ensure_wind_rig(context, props):
    """Create or reuse (found by name — idempotent) the QC_Wind rig:
    a Wind force-field empty aimed along the user direction, with a
    Turbulence field parented to it. Returns the wind object."""
    scene = context.scene

    wind = bpy.data.objects.get(WIND_EMPTY_NAME)
    if wind is None or wind.name not in scene.objects:
        if wind is None:
            wind = bpy.data.objects.new(WIND_EMPTY_NAME, None)
            wind.empty_display_type = 'SINGLE_ARROW'
            wind.empty_display_size = 1.5
        if wind.name not in scene.collection.all_objects:
            context.collection.objects.link(wind)

    wind.field.type = 'WIND'
    wind.field.strength = props.wind_strength
    wind.field.shape = 'PLANE'

    # Aim the empty's +Z along the requested direction (wind blows along
    # local Z).
    direction = Vector(props.wind_direction)
    if direction.length < 1e-6:
        direction = Vector((1.0, 0.0, 0.0))
    quat = direction.normalized().to_track_quat('Z', 'Y')
    wind.rotation_euler = quat.to_euler()

    turb = bpy.data.objects.get(TURBULENCE_EMPTY_NAME)
    if turb is None:
        turb = bpy.data.objects.new(TURBULENCE_EMPTY_NAME, None)
        turb.empty_display_type = 'SPHERE'
        turb.empty_display_size = 0.75
    if turb.name not in scene.collection.all_objects:
        context.collection.objects.link(turb)
    turb.parent = wind

    turb.field.type = 'TURBULENCE'
    turb.field.strength = props.wind_turbulence
    turb.field.seed = props.wind_seed
    return wind


def remove_wind_rig(context):
    """Delete the QC_Wind rig (wind + turbulence empties) if present."""
    removed = 0
    for name in (TURBULENCE_EMPTY_NAME, WIND_EMPTY_NAME):
        obj = bpy.data.objects.get(name)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
            removed += 1
    return removed


def cache_hygiene(context, scene, cache, sim_start, sim_end, report=None):
    """Point caches silently kill simulations when misconfigured.
    (Hard-won lesson from Quick Break.)

    * Clamp the cache start so it NEVER sits on a frame the timeline cannot
      reach — otherwise the sim never initializes and the cloth freezes.
    * Extend the cache end to cover the sim.
    * Free stale bakes so old cached data can't freeze the new setup.
    * Rewind the playhead to the sim start if it sits past it — cloth only
      computes forward.
    """
    if sim_start < scene.frame_start:
        if report is not None:
            report({'WARNING'},
                   f"Simulation start ({sim_start}) is before the scene "
                   f"start ({scene.frame_start}) — extending the scene start "
                   "down so the cache stays reachable")
        scene.frame_start = sim_start

    cache.frame_start = sim_start
    # Belt-and-braces clamp: the cache must never start before a reachable
    # frame.
    cache.frame_start = max(scene.frame_start,
                            min(cache.frame_start, sim_start))
    cache.frame_end = max(scene.frame_end, sim_end)

    # Free any stale bake (version-fragile op → guarded, per architecture
    # rules).
    try:
        with context.temp_override(scene=scene, point_cache=cache):
            bpy.ops.ptcache.free_bake()
    except Exception:
        pass

    # Cloth only computes forward: rewind the playhead if it's past the
    # start.
    if scene.frame_current > cache.frame_start:
        scene.frame_set(max(scene.frame_start, cache.frame_start))


def object_is_override_locked(obj):
    """True for linked or library-override data we must not edit."""
    return obj.library is not None or obj.override_library is not None


OVERRIDE_MESSAGE = ("This object is a linked override — make the cloth "
                    "modifier editable in the override hierarchy first")


def cage_name_for(obj):
    return CAGE_PREFIX + obj.name


def find_cage(obj):
    """Return the animation cage for a garment (or None)."""
    return bpy.data.objects.get(cage_name_for(obj))


def find_garment_for_cage(cage):
    """Inverse lookup: cage -> garment object (or None)."""
    if not cage.name.startswith(CAGE_PREFIX):
        return None
    return bpy.data.objects.get(cage.name[len(CAGE_PREFIX):])


def resolve_animator_pair(obj):
    """Given either the garment or its cage, return (garment, cage) —
    either may be None."""
    if obj is None:
        return None, None
    if obj.name.startswith(CAGE_PREFIX):
        garment = find_garment_for_cage(obj)
        return garment, obj
    return obj, find_cage(obj)


def animator_mode_active(obj):
    """True while the garment's cloth is muted and a cage exists — i.e.
    the user is animating with the stand-in."""
    garment, cage = resolve_animator_pair(obj)
    if garment is None or cage is None:
        return False
    mod = find_cloth_modifier(garment)
    return mod is not None and not mod.show_viewport


def build_or_update_cage(context, garment, ratio):
    """Create (or reuse — idempotent) the decimated animation cage.

    The cage is a copy of the garment object: it shares the same parent,
    constraints, object-level action, vertex groups, and — crucially — the
    same Armature modifier, so the SAME rig animation drives both. Cloth
    and Collision modifiers are stripped from the cage (that's the whole
    point), and a Decimate modifier at the end of the stack lightens the
    deform. Nothing on the garment itself is duplicated or destroyed.
    """
    cage = find_cage(garment)
    if cage is None:
        cage = garment.copy()          # shares action/parent/constraints
        cage.data = garment.data.copy()
        cage.name = cage_name_for(garment)
        cage.data.name = cage.name
        # Link into the same collections as the garment.
        linked = False
        for coll in garment.users_collection:
            coll.objects.link(cage)
            linked = True
        if not linked:
            context.collection.objects.link(cage)
        # Strip simulation modifiers — the cage must be deform-only.
        for mod in list(cage.modifiers):
            if mod.type in {'CLOTH', 'COLLISION'}:
                cage.modifiers.remove(mod)
        cage.show_wire = True          # reads visually as "the cage"

    # Decimate last in the stack (after Armature) so weights deform first.
    dec = None
    for mod in cage.modifiers:
        if mod.type == 'DECIMATE':
            dec = mod
    if dec is None:
        dec = cage.modifiers.new(name="QC Cage Decimate", type='DECIMATE')
    dec.ratio = ratio
    return cage


# ---------------------------------------------------------------------------
# OPERATORS
# ---------------------------------------------------------------------------

class QC_OT_simulate(Operator):
    """Set up (or refresh) the cloth simulation on the active mesh:
configure the Cloth modifier from the panel values, fix the Armature/Cloth
stack order, auto-convert rigid-body obstacles into colliders, build the
wind rig, and run cache hygiene so the sim can never silently freeze.
Idempotent — run it as often as you like"""
    bl_idname = "quick_cloth.simulate"
    bl_label = "Simulate Cloth!"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT')

    def execute(self, context):
        scene = context.scene
        props = scene.quick_cloth
        obj = context.active_object

        if object_is_override_locked(obj):
            self.report({'ERROR'}, OVERRIDE_MESSAGE)
            return {'CANCELLED'}

        if animator_mode_active(obj):
            self.report({'ERROR'},
                        "Animator Mode is on (the cloth is muted) — press "
                        "Exit Animator Mode first, then Simulate")
            return {'CANCELLED'}

        # Never simulate the cage itself — it's a deform-only stand-in.
        if obj.name.startswith(CAGE_PREFIX):
            self.report({'ERROR'},
                        "This is the animation cage — select the real "
                        "garment to simulate")
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
            mod.settings.vertex_group_mass = pin_group.name
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
                                               props.object_distance,
                                               report=self.report)
            if n:
                self.report({'INFO'},
                            f"Gave {n} rigid-body obstacle(s) a Collision "
                            "modifier")

        # 6. Wind rig (found by name — idempotent).
        if props.use_wind:
            ensure_wind_rig(context, props)

        # 7. Frame range: shot range from the panel (or the timeline's
        #    preview range), minus the settle pre-roll.
        if (props.use_preview_range and scene.use_preview_range):
            shot_start = scene.frame_preview_start
            shot_end = scene.frame_preview_end
        else:
            shot_start = props.frame_start
            shot_end = props.frame_end
        sim_start = shot_start - props.settle_frames
        sim_end = max(shot_end, sim_start + 1)

        # 8. Cache hygiene + disk cache.
        cache = mod.point_cache
        cache_hygiene(context, scene, cache, sim_start, sim_end,
                      report=self.report)
        cache.use_disk_cache = props.use_disk_cache
        if props.use_disk_cache:
            cache.use_library_path = True

        self.report({'INFO'},
                    f"Cloth configured on '{obj.name}' "
                    f"({props.preset.replace('_', ' ').title()}, "
                    f"frames {cache.frame_start}–{cache.frame_end}"
                    + (f", {props.settle_frames} settle frames" if props.settle_frames else "")
                    + "). Press Spacebar to play")
        return {'FINISHED'}


class QC_OT_set_pin_group(Operator):
    """Turn the current Edit-Mode vertex selection into the "pin" vertex
group (weight 1.0). Pinned vertices hold to the object's own animation —
weight the collar/waistband and let everything else simulate"""
    bl_idname = "quick_cloth.set_pin_group"
    bl_label = "Set Pin Group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'EDIT_MESH')

    def execute(self, context):
        obj = context.active_object

        if object_is_override_locked(obj):
            self.report({'ERROR'}, OVERRIDE_MESSAGE)
            return {'CANCELLED'}

        # Flush the edit-mode selection to the mesh data by toggling to
        # Object Mode (selection state is restored by returning to Edit
        # Mode below — we never leave the user somewhere else).
        bpy.ops.object.mode_set(mode='OBJECT')
        selected = [v.index for v in obj.data.vertices if v.select]

        if not selected:
            bpy.ops.object.mode_set(mode='EDIT')
            self.report({'ERROR'},
                        "Nothing selected — select the vertices to pin "
                        "(collar, waistband, corners) in Edit Mode first")
            return {'CANCELLED'}

        group = find_pin_group(obj)
        if group is None:
            group = obj.vertex_groups.new(name=PIN_GROUP_CANONICAL)
        else:
            # Refresh: clear old weights so the group exactly matches the
            # new selection.
            group.remove(list(range(len(obj.data.vertices))))
        group.add(selected, 1.0, 'REPLACE')

        bpy.ops.object.mode_set(mode='EDIT')
        self.report({'INFO'},
                    f"Pin group '{group.name}' set from {len(selected)} "
                    "selected vertice(s)")
        return {'FINISHED'}


class QC_OT_pin_from_rig_weights(Operator):
    """Build the "pin" group automatically from the armature's deform
weights: every vertex is pinned by its combined bone weight, so a freshly
auto-weighted garment follows the rig out of the box. Then paint DOWN the
pin weights (Weight Paint mode) wherever fabric should swing free. Keeps
Set Pin Group untouched for manual selections"""
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
        pin_group = find_pin_group(obj)
        if pin_group is None:
            pin_group = obj.vertex_groups.new(name=PIN_GROUP_CANONICAL)
        pin_index = pin_group.index

        weighted = 0
        for v in obj.data.vertices:
            total = 0.0
            for g in v.groups:
                if g.group in deform_group_indices:
                    total += g.weight
            total = min(total, 1.0)
            if total > 0.0:
                pin_group.add([v.index], total, 'REPLACE')
                weighted += 1
            elif any(g.group == pin_index for g in v.groups):
                pin_group.remove([v.index])

        if weighted == 0:
            self.report({'ERROR'},
                        "The rig's deform bones carry no weight on this "
                        "mesh — automatic weighting may have failed "
                        "(overlapping or non-manifold geometry)")
            return {'CANCELLED'}

        self.report({'INFO'},
                    f"Pin group '{pin_group.name}' built from rig weights "
                    f"({weighted}/{len(obj.data.vertices)} vertices). Paint "
                    "the pin weights DOWN where fabric should swing free")
        return {'FINISHED'}



class QC_OT_make_colliders(Operator):
    """Add a tuned Collision modifier to all selected objects so the cloth
can rest on them — chairs, bodies, tables. Works on rigged meshes untouched
(collision uses the deformed mesh, so animated characters collide
correctly). Idempotent"""
    bl_idname = "quick_cloth.make_colliders"
    bl_label = "Make Collider(s)"
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


class QC_OT_remove_wind(Operator):
    """Delete the QC_Wind rig (the wind and turbulence empties)"""
    bl_idname = "quick_cloth.remove_wind"
    bl_label = "Remove Wind"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (bpy.data.objects.get(WIND_EMPTY_NAME) is not None
                or bpy.data.objects.get(TURBULENCE_EMPTY_NAME) is not None)

    def execute(self, context):
        removed = remove_wind_rig(context)
        self.report({'INFO'}, f"Removed {removed} wind rig object(s)")
        return {'FINISHED'}


class QC_OT_bake(Operator):
    """Bake the cloth simulation to its point cache (respects the Disk
Cache setting). Flip Quality Mode to Final first"""
    bl_idname = "quick_cloth.bake"
    bl_label = "Bake"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and find_cloth_modifier(obj) is not None)

    def execute(self, context):
        obj = context.active_object
        mod = find_cloth_modifier(obj)
        cache = mod.point_cache
        cache.use_disk_cache = context.scene.quick_cloth.use_disk_cache
        if cache.use_disk_cache:
            cache.use_library_path = True
        # ptcache is version-fragile → guarded temp_override, per
        # architecture rules.
        try:
            with context.temp_override(scene=context.scene,
                                       active_object=obj,
                                       point_cache=cache):
                bpy.ops.ptcache.bake(bake=True)
        except Exception as exc:
            self.report({'ERROR'}, f"Bake failed: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'},
                    f"Baked frames {cache.frame_start}–{cache.frame_end}"
                    + (" to disk cache" if cache.use_disk_cache else ""))
        return {'FINISHED'}


class QC_OT_free_bake(Operator):
    """Free the baked cloth cache so the simulation recalculates live"""
    bl_idname = "quick_cloth.free_bake"
    bl_label = "Free Bake"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and find_cloth_modifier(obj) is not None)

    def execute(self, context):
        obj = context.active_object
        mod = find_cloth_modifier(obj)
        cache = mod.point_cache
        try:
            with context.temp_override(scene=context.scene,
                                       active_object=obj,
                                       point_cache=cache):
                bpy.ops.ptcache.free_bake()
        except Exception as exc:
            self.report({'ERROR'}, f"Free bake failed: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, "Freed the baked cache")
        return {'FINISHED'}


class QC_OT_apply_as_shape(Operator):
    """Snapshot the cloth at the current frame as a NEW object — extract a
nicely draped couch cushion or hung coat without destroying the sim setup"""
    bl_idname = "quick_cloth.apply_as_shape"
    bl_label = "Apply as Shape"
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
        context.collection.objects.link(new_obj)
        self.report({'INFO'},
                    f"Created '{new_obj.name}' from frame "
                    f"{context.scene.frame_current}")
        return {'FINISHED'}


class QC_OT_bind_render_mesh(Operator):
    """Proxy workflow: with the low-poly SIM mesh active and the high-res
RENDER mesh also selected, add a Surface Deform modifier to the render mesh
targeting the sim mesh and Bind it. Simulate a 5k-vert proxy, drive a
500k-vert garment. Run again on a bound mesh to Unbind"""
    bl_idname = "quick_cloth.bind_render_mesh"
    bl_label = "Bind Render Mesh"
    bl_options = {'REGISTER', 'UNDO'}

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

        mod = None
        for m in render_obj.modifiers:
            if m.type == 'SURFACE_DEFORM':
                mod = m
                break
        if mod is None:
            mod = render_obj.modifiers.new(name="QC Surface Deform",
                                           type='SURFACE_DEFORM')
        mod.target = sim_obj

        was_bound = mod.is_bound
        try:
            with context.temp_override(object=render_obj,
                                       active_object=render_obj,
                                       selected_objects=[render_obj]):
                bpy.ops.object.surfacedeform_bind(modifier=mod.name)
        except Exception as exc:
            self.report({'ERROR'}, f"Bind failed: {exc}")
            return {'CANCELLED'}

        if was_bound:
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
    """Swap the garment for a lightweight decimated cage while you animate:
the cage follows the SAME rig (same Armature modifier, same action — no
keyframes need transferring), while the real garment is hidden and its
cloth modifier is fully muted, so nothing is solved and no cache eats RAM.
Animate freely, then Exit Animator Mode when the performance is locked"""
    bl_idname = "quick_cloth.enter_animator_mode"
    bl_label = "Enter Animator Mode"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH' or context.mode != 'OBJECT':
            return False
        garment, _cage = resolve_animator_pair(obj)
        return garment is not None and not animator_mode_active(obj)

    def execute(self, context):
        props = context.scene.quick_cloth
        garment, _cage = resolve_animator_pair(context.active_object)

        if object_is_override_locked(garment):
            self.report({'ERROR'}, OVERRIDE_MESSAGE)
            return {'CANCELLED'}

        cage = build_or_update_cage(context, garment, props.cage_ratio)

        # Mute the cloth entirely: no solving during playback, no point
        # cache accumulating in RAM. (Muting beats hiding alone — a hidden
        # object with a live modifier can still be pulled into evaluation
        # by dependencies.)
        mod = find_cloth_modifier(garment)
        if mod is not None:
            mod.show_viewport = False

        # Hide the garment, present the cage.
        garment.hide_set(True)
        cage.hide_set(False)
        cage.hide_viewport = False
        for o in context.selected_objects:
            o.select_set(False)
        cage.select_set(True)
        context.view_layer.objects.active = cage

        self.report({'INFO'},
                    f"Animator Mode ON — animating with '{cage.name}' "
                    f"({props.cage_ratio:.0%} detail). The cage follows the "
                    "same rig; your keyframes live on the armature and "
                    "apply to the real garment automatically")
        return {'FINISHED'}


class QC_OT_exit_animator_mode(Operator):
    """Bring the real garment back: unhide it, un-mute its cloth modifier,
hide the cage, and free the (now stale) cache. Because the animation lives
on the rig — which garment and cage share — the cloth picks up the finished
performance immediately. Hit Simulate Cloth! to refresh ranges, then Bake"""
    bl_idname = "quick_cloth.exit_animator_mode"
    bl_label = "Exit Animator Mode"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return animator_mode_active(context.active_object)

    def execute(self, context):
        garment, cage = resolve_animator_pair(context.active_object)

        # Restore the garment.
        garment.hide_set(False)
        garment.hide_viewport = False
        mod = find_cloth_modifier(garment)
        if mod is not None:
            mod.show_viewport = True
            # The animation changed while the sim was muted — any cached
            # frames are stale and would freeze the new setup. Free them
            # (version-fragile op → guarded temp_override).
            try:
                with context.temp_override(scene=context.scene,
                                           point_cache=mod.point_cache):
                    bpy.ops.ptcache.free_bake()
            except Exception:
                pass

        # Park the cage (kept for next time — idempotent reuse).
        if cage is not None:
            cage.hide_set(True)
        for o in context.selected_objects:
            o.select_set(False)
        garment.select_set(True)
        context.view_layer.objects.active = garment

        self.report({'INFO'},
                    "Animator Mode OFF — garment restored, stale cache "
                    "freed. Run Simulate Cloth! to refresh the sim range, "
                    "then Bake")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# PANEL
# ---------------------------------------------------------------------------

class QC_PT_panel(Panel):
    bl_label = "Quick Cloth"
    bl_idname = "QC_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Quick Cloth"

    def draw(self, context):
        layout = self.layout
        props = context.scene.quick_cloth
        obj = context.active_object

        # 1. Preset dropdown — top, full width.
        layout.prop(props, "preset", text="")

        # 2. Fabric column.
        col = layout.column(align=True)
        col.prop(props, "mass")
        col.prop(props, "air_damping")
        col.prop(props, "show_fabric_detail",
                 icon='TRIA_DOWN' if props.show_fabric_detail else 'TRIA_RIGHT',
                 emboss=False)
        if props.show_fabric_detail:
            sub = col.box().column(align=True)
            sub.prop(props, "tension_stiffness")
            sub.prop(props, "compression_stiffness")
            sub.prop(props, "shear_stiffness")
            sub.prop(props, "bending_stiffness")
            sub.separator()
            sub.prop(props, "tension_damping")
            sub.prop(props, "compression_damping")
            sub.prop(props, "shear_damping")
            sub.prop(props, "bending_damping")
            sub.separator()
            sub.prop(props, "time_scale")
            sub.prop(props, "use_internal_springs")
            if props.use_internal_springs:
                sub.prop(props, "internal_stiffness")

        # 3. Garment box.
        box = layout.box()
        box.label(text="Garment", icon='MOD_CLOTH')
        pin_group = find_pin_group(obj) if obj else None
        if pin_group is not None:
            box.label(text=f"Pin group found \u2713 ({pin_group.name})",
                      icon='GROUP_VERTEX')
        else:
            box.label(text="No pin group", icon='GROUP_VERTEX')
        box.operator("quick_cloth.set_pin_group", icon='PINNED')
        box.operator("quick_cloth.pin_from_rig_weights",
                     icon='ARMATURE_DATA')
        box.prop(props, "pin_stiffness")
        box.prop(props, "fit_tightness")
        row = box.row(align=True)
        row.prop(props, "use_sewing")
        sub = row.row()
        sub.enabled = props.use_sewing
        sub.prop(props, "sewing_force", text="Force")
        pbox = box.box()
        pbox.prop(props, "use_pressure")
        if props.use_pressure:
            pbox.prop(props, "pressure_force")
            pbox.prop(props, "pressure_target_volume")

        # 4. Forces box.
        box = layout.box()
        box.label(text="Forces", icon='FORCE_WIND')
        box.prop(props, "use_wind")
        if props.use_wind:
            box.prop(props, "wind_direction")
            box.prop(props, "wind_strength")
            box.prop(props, "wind_turbulence")
            box.prop(props, "wind_seed")
            box.operator("quick_cloth.remove_wind", icon='X')
        box.prop(props, "gravity_influence")

        # 5. Collisions box.
        box = layout.box()
        box.label(text="Collisions", icon='PHYSICS')
        box.prop(props, "use_collision_objects")
        box.operator("quick_cloth.make_colliders", icon='MESH_ICOSPHERE')
        box.prop(props, "object_distance")
        row = box.row(align=True)
        row.prop(props, "use_self_collision")
        sub = row.row()
        sub.enabled = props.use_self_collision
        sub.prop(props, "self_distance", text="Distance")

        # 6. Simulation box.
        box = layout.box()
        box.label(text="Simulation", icon='SCENE_DATA')
        row = box.row(align=True)
        row.prop(props, "quality_mode", expand=True)
        box.prop(props, "frame_start")
        box.prop(props, "frame_end")
        box.prop(props, "settle_frames")
        box.prop(props, "use_preview_range")
        box.prop(props, "quality_steps")
        box.prop(props, "collision_quality")
        box.prop(props, "use_disk_cache")
        row = box.row(align=True)
        row.operator("quick_cloth.bake", icon='RENDER_ANIMATION')
        row.operator("quick_cloth.free_bake", icon='TRASH')
        box.operator("quick_cloth.apply_as_shape", icon='MESH_DATA')
        box.operator("quick_cloth.bind_render_mesh", icon='MOD_MESHDEFORM')

        # 6b. Animator Mode box.
        box = layout.box()
        box.label(text="Animator Mode", icon='ARMATURE_DATA')
        if animator_mode_active(obj):
            box.label(text="Animating with cage \u2014 cloth muted",
                      icon='CHECKMARK')
            box.operator("quick_cloth.exit_animator_mode",
                         icon='LOOP_BACK')
        else:
            box.prop(props, "cage_ratio")
            box.operator("quick_cloth.enter_animator_mode",
                         icon='MESH_GRID')

        # 7. Big final button.
        layout.separator()
        row = layout.row()
        row.scale_y = 1.6
        row.operator("quick_cloth.simulate", icon='MOD_CLOTH')


# ---------------------------------------------------------------------------
# REGISTRATION
# ---------------------------------------------------------------------------

classes = (
    QuickClothProps,
    QC_OT_simulate,
    QC_OT_set_pin_group,
    QC_OT_pin_from_rig_weights,
    QC_OT_make_colliders,
    QC_OT_remove_wind,
    QC_OT_bake,
    QC_OT_free_bake,
    QC_OT_apply_as_shape,
    QC_OT_bind_render_mesh,
    QC_OT_enter_animator_mode,
    QC_OT_exit_animator_mode,
    QC_PT_panel,
)


_registered = []


def register():
    try:
        for cls in classes:
            bpy.utils.register_class(cls)
            _registered.append(cls)
        bpy.types.Scene.quick_cloth = PointerProperty(type=QuickClothProps)
    except Exception:
        unregister()
        raise


def unregister():
    if hasattr(bpy.types.Scene, "quick_cloth"):
        del bpy.types.Scene.quick_cloth
    for cls in reversed(_registered):
        bpy.utils.unregister_class(cls)
    _registered.clear()


if __name__ == "__main__":
    register()
