# Quick Cloth

**Version 1.0.3 · Blender 4.1+ · Category: Physics**

The sister addon to **Quick Break**. Pick a fabric, click one button, get believable cloth — built for animators, not technical directors.

---

## What It Does

- **Nine fabric presets that change the cloth's BEHAVIOR, not just numbers** — cotton drapes, polyester floats, selvedge denim holds a boardy crease, latex hugs the body. Presets are starting points: selecting one rewrites every physics value (and updates a live modifier instantly), then every slider stays fully editable.
- **Per-object collisions with NO collision collection, ever.** The cloth interacts with every collision object in the scene, each one independently. Rigid-body obstacles are auto-converted into colliders one by one when you hit Simulate.
- **One-click pinning.** Select vertices in Edit Mode, press *Set Pin Group* — done. The pin group is fuzzy-matched ("pin", "pins", "pin group", "pinned", any capitalization), and pinned vertices follow the object's own animation, so a rigged shirt collar follows the walk cycle automatically.
- **Wind with a re-rollable seed.** A named, reusable QC_Wind rig (Wind + parented Turbulence field) with a *Wind Seed* you can re-roll for a different gust pattern — same idea as Quick Break's Break/Shrapnel seeds.
- **Cache hygiene built in.** The addon clamps the point cache so it can never start on an unreachable frame, frees stale bakes, and rewinds the playhead — the silent frozen-sim bug is designed out.
- **Animator workflow throughout**: automatic Armature→Cloth stack ordering, Settle Frames pre-roll, a non-destructive Preview/Final quality switch, a proxy-mesh *Bind Render Mesh* operator, and farm-friendly Disk Cache.
- Idempotent everywhere: hit *Simulate Cloth!* fifty times per shot — you'll always have exactly one Cloth modifier, one wind rig, and no duplicate colliders.

---

## Installation

**Blender 4.2 and newer (Extension):** drag `quick_cloth_addon.zip` into the Blender window (or *Edit → Preferences → Get Extensions → Install from Disk*). Done.

**Blender 4.1 (legacy addon):** *Edit → Preferences → Add-ons → Install…*, choose `quick_cloth_addon.zip`, enable **Quick Cloth**. The same zip works for both paths.

### Building the zip from this repo

The add-on source lives in `quick_cloth/` (`__init__.py` + `blender_manifest.toml`). To produce an installable `quick_cloth_addon.zip` that works for both install paths, zip the folder itself (so the archive contains `quick_cloth/__init__.py`):

```bash
git archive --format=zip -o quick_cloth_addon.zip HEAD quick_cloth README.md
```

The panel appears in the 3D Viewport sidebar (press **N**) under the **Quick Cloth** tab.

---

## Quick Start (30 seconds)

1. Select your garment mesh.
2. Open the **Quick Cloth** tab in the N-panel.
3. Pick a fabric preset (start with **Cotton** for clothing).
4. (Optional) In Edit Mode, select the collar/waistband vertices and press **Set Pin Group**.
5. (Optional) Select the body/table/chair and press **Make Collider(s)**.
6. Back in Object Mode, click **Simulate Cloth!**
7. Press **Spacebar**.

---

## The Panel, Option by Option

### Preset Dropdown

| # | Preset | Character |
|---|--------|-----------|
| 1 | **Simple Cloth (default)** | Blender's vanilla feel. Light, no self-collision, low quality steps — the fast-preview fabric. |
| 2 | **Cotton** | Shirts, t-shirts, pants, socks. Soft micro-wrinkles, drapes close to the body, self-collision on. |
| 3 | **Polyester** | Polos and slacks. Springier, holds its shape, slightly floaty (higher air damping), fewer fine wrinkles. |
| 4 | **Couch Leather** | Thick upholstery leather/pleather. Big heavy soft folds, almost no flutter; internal springs preserve cushion volume; time scale 0.9 for weight. |
| 5 | **Leather Coat** | Rain coats and biker jackets. Stiff panels that swing as a unit, soft only at the elbows. |
| 6 | **Latex** | Skin-tight latex garments. Very stretchy (low tension), near-zero bending so it follows every curve, NEGATIVE fit tightness so it shrinks onto the body, sewing on, self-collision mandatory. |
| 7 | **Stretch Denim** | Jeans with elastane. Gives at the knees, light hug fit (slightly negative fit tightness). |
| 8 | **Cotton Rigid Denim** | Classic Blender denim. Heavy, structured folds that hold a silhouette. |
| 9 | **Selvedge Denim** | Raw heavyweight denim — the stiffest fabric here. Boardy, tube-like folds, barely wrinkles, high damping so creases read as *held*. |

### Fabric

| Option | What it does |
|---|---|
| Vertex Mass | Mass per vertex (kg). Heavier hangs straighter, resists wind. **Nominal** — visual weight also depends on mesh density; treat it as a feel dial. |
| Air Damping | Air resistance. Higher = floatier, slower falling. |
| Fabric Detail (fold-out) | Tension / Compression / Shear / Bending stiffness, their four damping values, Time Scale, and Internal Springs. Bending is *the* fabric-character dial: near zero = silk, high = leather. |

### Garment (MOD_CLOTH box)

| Option | What it does |
|---|---|
| Pin status line | "Pin group found ✓" or "No pin group" — the addon fuzzy-matches pin/pins/pin group/pinned. |
| Set Pin Group | Turns the current Edit-Mode vertex selection into the pin group (weight 1.0). Errors clearly if nothing is selected. |
| Pin From Rig Weights | Builds the pin group automatically from the armature's combined deform-bone weights — a freshly auto-weighted garment follows the rig out of the box. Then paint the pin weights DOWN (Weight Paint mode) wherever fabric should swing free. Complements Set Pin Group; doesn't replace it. |
| Pin Stiffness | How rigidly pins hold (0–1). Pinned vertices follow the object's own animation — that's how you drag a cape around. |
| Fit Tightness | Shrink factor (-0.3…+0.3). **Negative shrinks the garment onto the body** — latex and stretch denim presets pre-set this. Needs a body collider to hug against. |
| Use Sewing + Force | Pulls sewing-spring edges together for flat-panel garments. |
| Pressure sub-box | Uniform internal pressure + optional target volume — puffer jackets, inflatables. |

### Forces (FORCE_WIND box)

| Option | What it does |
|---|---|
| Add Wind | On Simulate, creates or reuses (by name) the **QC_Wind** rig: a Wind empty aimed along Direction, plus a parented Turbulence field. |
| Direction / Strength / Turbulence | Where the wind blows, how hard, and how gusty. |
| Wind Seed | Re-rollable random seed for the gust pattern — new look, same average wind. |
| Remove Wind | Deletes the QC_Wind rig. |
| Gravity Influence | 0–1 scale on scene gravity for this cloth — float heavy fabrics for stylized shots. |

### Collisions (PHYSICS box)

| Option | What it does |
|---|---|
| Use Collision Objects | On Simulate, every rigid-body mesh in the scene without a Collision modifier gets one (thickness 0.02, damping 0.1) — each object individually. **No collision collection is ever created or assigned**; the cloth collides with everything. |
| Make Collider(s) | Explicitly adds a tuned Collision modifier to all *selected* objects — a chair, a body, a table. Safe on rigged meshes: nothing is applied or frozen. |
| Object Distance | Minimum cloth-to-obstacle distance. Raise it if the cloth pokes through. |
| Self Collision + Distance | Stops the cloth passing through itself. Required for tight fits and layered folds. |

### Simulation (SCENE_DATA box)

| Option | What it does |
|---|---|
| Preview / Final | **Preview** halves Quality Steps and Collision Quality (min 3/2) and disables self-collision unless the preset mandates it (Latex). **Final** uses your values verbatim. Non-destructive — it scales at configure time and never overwrites your sliders. |
| Start / End Frame | The SHOT's frame range. |
| Settle Frames | Pre-roll (default 15): the sim starts this many frames *before* the shot so the garment is already draped at frame 1. The scene start is extended down automatically if needed. |
| Use Preview Range | Takes the shot range from the timeline's preview range when it's active. |
| Quality Steps / Collision Quality | The solver dials. Scale Quality down for viewport speed, up for final bakes. |
| Disk Cache | Stores the bake on disk (library-path aware) so it survives relinking and render farms. |
| Bake / Free Bake | Bake the cache, or free it to simulate live again. |
| Apply as Shape | Snapshots the draped cloth at the current frame as a new object — extract a couch cushion or a hung coat. |
| Bind Render Mesh | With the low-poly sim mesh active and the high-res render mesh also selected: adds a Surface Deform to the render mesh, targets the sim mesh, and Binds. Run again to Unbind. |

### Animator Mode (ARMATURE_DATA box)

| Option | What it does |
|---|---|
| Cage Detail | Polygon ratio of the animation cage (0.2 = 20% of the garment's faces). |
| Enter Animator Mode | Builds (or reuses) a decimated **cage** of the garment that follows the **same rig** — same Armature modifier, same action. The real garment is hidden and its cloth modifier is fully **muted**: nothing is solved during playback and no point cache accumulates in RAM. Animate at full speed watching the cage. |
| Exit Animator Mode | Restores the garment, un-mutes the cloth, hides the cage, and frees the now-stale cache. **No keyframes need transferring** — your animation lives on the armature, which the garment and cage share, so the cloth picks up the finished performance immediately. Then *Simulate Cloth!* → *Bake*. |


### Simulate Cloth!

The big button. Configures (or refreshes) everything above on the active mesh. Idempotent — running it twice updates the existing setup rather than stacking a second one.

---

## How It Works (Under the Hood)

1. **Presets** write a complete dictionary of physics values into the addon's properties *and* into a live cloth modifier if one exists. Physically: **mass** sets per-vertex weight (hang + inertia), **tension/compression** control stretch and squash (denim high, latex low), **shear** controls diagonal distortion, **bending** controls fold size (the single biggest character dial), the four **dampings** control how fast each motion settles (selvedge denim's high damping is why its creases hold), **air damping** controls float (polyester), **time scale** below 1.0 reads as heavy (couch leather), and **negative shrink** tightens a garment onto a body (latex, stretch denim). Couch Leather additionally enables **internal springs** so cushions keep their volume.
2. **Pinning**: the pin vertex group is wired to the cloth's pin group (mass vertex group), with Pin Stiffness controlling how rigidly weight-1.0 vertices hold. Pinned vertices follow the *object's own animation* — including an Armature modifier's deformation, which is why the stack order matters (see 5).
3. **The wind rig** is two empties found by name: `QC_Wind` (a plane-shaped Wind field aimed along your direction — wind blows along the empty's local Z) and `QC_Wind_Turbulence` parented to it (a Turbulence field whose strength is the Turbulence slider and whose noise **seed** is the Wind Seed). Re-running Simulate reuses and retunes them; nothing duplicates.
4. **Collision auto-conversion** mirrors Quick Break's, in reverse: Quick Break turned Collision-modifier objects into passive rigid bodies; Quick Cloth turns rigid-body obstacles into cloth colliders. Every rigid-body mesh without a Collision modifier gets one, individually, with tuned defaults. The cloth's collision collection is left **None** on purpose, so it collides with every collider in the scene.
5. **Rigged garments**: if the cloth object also has an Armature modifier, the addon reorders the stack so **Armature comes first, Cloth after** (via `modifiers.move()`, no operators) and reports "Moved Cloth below Armature so pins follow the rig". Pinned collar/waistband vertices then follow the rig's animation while the loose fabric simulates on top.
6. **The cache-hygiene story**: Blender point caches silently kill simulations when misconfigured — if the cache starts on a frame the timeline can't reach, the sim never initializes and the cloth just freezes. On every Simulate, the addon clamps the cache start to a reachable frame (extending the scene start down when Settle Frames requires it), extends the cache end to cover the sim, frees any stale bake so old data can't freeze the new setup, rewinds the playhead to the sim start, and warns you when frame math looks wrong.

---

## Tips

- **Auto-weighted garment that should mostly follow the rig**: press **Pin From Rig Weights** right after parenting with automatic weights — the whole garment tracks the rig immediately, and you only paint the pin weights *down* on hems, capes, and sleeves you want to fly free. Pin Stiffness becomes your global rigid-vs-loose dial.
- **Shirt on a rigged walking character** (the #1 use case): weight the collar and waistband into the **pin** group (*Set Pin Group*), select the body mesh and press **Make Collider(s)**, then *Simulate Cloth!* on the shirt. The addon puts Cloth below Armature automatically — pins follow the rig, fabric simulates on top.
- **Hang a coat on a rack**: pin the vertices touching the hook, pick **Leather Coat**, simulate, then **Apply as Shape** to keep the drape as a static prop.
- **Skin-tight latex fit**: pick **Latex**, make the body a collider, and keep Fit Tightness negative — the garment shrinks onto the body. Don't turn off self-collision; the preset needs it (Preview mode keeps it on for Latex).
- **Couch cushion drape**: pick **Couch Leather** (internal springs keep the volume), drop it onto a collider couch frame, let it settle, **Apply as Shape**.
- **Flag in the wind with re-rollable gusts**: pin the flag's pole edge, enable **Add Wind**, set direction and strength, then re-roll **Wind Seed** until the gust pattern reads right — the average wind never changes.
- **Proxy sim driving a high-res garment**: simulate a ~5k-vert proxy, then select the high-res render mesh, ctrl-select the proxy (active), press **Bind Render Mesh**. The single biggest speed win in cloth work.
- **Animate heavy shots without the sim eating your RAM**: select the garment, press **Enter Animator Mode**, and animate against the lightweight cage — the cloth is muted, so the solver never runs and the cache never grows. When the performance is locked, **Exit Animator Mode**, hit *Simulate Cloth!*, and *Bake*. Keyframes never move: they live on the rig, which both meshes share.
- **Settle the drape before frame 1**: leave **Settle Frames** at 15 (or more for heavy fabric) and animate the character holding its first pose during the settle window — or use the rig's rest pose. The garment is already draped when the shot starts.
- Block in **Preview**, flip to **Final**, then **Bake** (with **Disk Cache** on for farm renders). Bakes are FPS-dependent — re-bake after changing the scene frame rate; the addon never touches your FPS and maps fabric feel through Time Scale only.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Cloth falls through objects | The obstacle needs a Collision modifier — select it and press **Make Collider(s)** (or leave *Use Collision Objects* on for rigid bodies). Then raise **Collision Quality** and/or **Object Distance**. |
| Cloth explodes / jitters | Raise **Quality Steps**; if self-collision is on, raise **Self Distance** slightly — too-small distances miss collisions and blow up. |
| Jitter the moment playback starts | Stiff fabrics need more solver substeps: raise **Quality Steps** (v1.0.1 presets already ship stiffness-matched steps and clamp collision impulses) and make sure you're in **Final**, not Preview. If the jitter only lasts the first frames, that's the snap-to-equilibrium transient — raise **Settle Frames** so it happens before the shot. Latex/Stretch Denim also contract at frame 1 (negative Fit Tightness) — they need the body collider present to catch them. |
| Sim freezes after a few frames | Classic stale/unreachable cache. Play from *before* the sim start, press **Free Bake**, and re-run **Simulate Cloth!** — the addon clamps the cache and rewinds the playhead for exactly this reason. |
| Latex doesn't hug the body | Fit Tightness must be **negative** (the preset sets -0.12) *and* the body must be a collider — the garment can only shrink onto something it collides with. |
| Pins don't hold | Check the pin group actually has weight-1.0 vertices (re-run **Set Pin Group**) and raise **Pin Stiffness** toward 1.0. |
| Garment doesn't follow the rig | Cloth must sit **below** Armature in the modifier stack — the addon fixes this automatically on Simulate (watch for the "Moved Cloth below Armature" message). If you rebuilt the stack by hand, just hit **Simulate Cloth!** again. |
| Playback is slow / RAM fills up while animating | Use **Animator Mode** — it mutes the cloth (no solve, no cache) and swaps in a decimated cage that follows the same rig. Also enable **Disk Cache** so bakes live on disk instead of memory. |
| Bake lost after re-opening the file | Enable **Disk Cache** before baking — memory caches don't survive a reload; disk caches do (and they survive relinking and render farms). |

---

*Quick Cloth is GPL-3.0-or-later. Simulate responsibly.*
