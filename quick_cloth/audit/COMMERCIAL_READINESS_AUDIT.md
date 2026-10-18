# Quick Cloth commercial-readiness audit and specification

Date: 2026-10-18. Source: Quick Cloth 1.0.3, repository commit `f21d3b5`.

Scope: audit and specification only, as requested. Target: convincing, engine-neutral visual results inside Blender, with rigged and unrigged cloth. This is not an engine exporter or a runtime-cloth implementation. Production source has not been modified.

**Release verdict: not ready for commercial release.** The original module cannot import. Downstream defects also affect wind, settings synchronization, pre-roll, collisions, and Animator Mode. A finite audit cannot enumerate every possible Blender scene or certify arbitrary cloth geometry. This report enumerates concrete defects, foreseeable failure classes, and the test gates needed for a supportable release.

## Evidence and limits

- Read the entire add-on, manifest, and parent README. The README exists one directory above the add-on; the first review's documentation-gap statement was too broad. Documentation exists, but several claims need correction.
- Ran disposable, factory-startup Blender **4.1.1** and **5.1.2** processes. The interactive Blender session and user files were untouched.
- Stock import fails in both. To inspect later code, the probe inserts the missing collider class declaration **in memory only**. Downstream results describe behavior after this single isolation repair, not a working original build.
- Each version produced 12 observation records. These are diagnostic observations, not 12 passing acceptance tests. The probe, JSON observations, and logs are beside this report.
- No full visual bake suite, rendered collision assessment, performance benchmark, packaging install/uninstall matrix, or 4.2/4.5 runtime test was performed. Those remain release gates.
- Blender 5.1's extension validator accepted the existing manifest in the previous review. `schema_version = "1.0.3"` should be reviewed against the documented schema, but it is **not** an established installation blocker in this audit.

Evidence labels: **R** = reproduced on both tested Blender versions; **S** = directly established by source; **V** = validation gap or scenario needing a dedicated reproduction. Severity: **P0** = loading blocker; **P1** = core workflow, wrong result, or destructive ownership risk; **P2** = reliability, usability, or performance gap. Severity is release prioritization, not a security score. All code anchors below refer to the unmodified `__init__.py`.

## Findings table: startup, configuration, and ownership

| ID | Priority / evidence | Scenario and current issue | Required behavior / acceptance |
|---|---|---|---|
| F01 | P0 / R | Collider operator has no class declaration near line 1226. Its methods overwrite the rig-pin operator; `classes` references an undefined name at 1680. | Clean import, register, operator-ID uniqueness, and all panel operators resolve on every supported version. |
| F02 | P1 / S | Settings live only on `Scene` (334, 1695). Select cotton garment A, configure leather B, then refresh A: B's scene settings overwrite A. | Store authored simulation settings per garment/setup; scene defaults only initialize new setups. Switching selection displays that object's values. |
| F03 | P1 / R+S | Quality and ordinary sliders have no update callback. Preview→Final leaves the modifier at Preview quality; Bake only copies disk-cache preference (554, 1294). | A single settings resolver is used by setup and Bake. UI displays effective values and dirty state; Bake applies current intended values. |
| F04 | P1 / S | Preset callback writes directly to whichever object is active, without ownership, editability, baking, or Animator Mode checks (307). | Resolve the property owner's garment; defer or reject changes during bake; never modify an unrelated active object. |
| F05 | P2 / R+S | Presets do not reset all physics despite broad documentation. Cotton retains enabled pressure and pressure force 33, as tested. Pinning, gravity, sewing force, etc. also remain outside preset dictionaries. | Define preset scope explicitly: fabric-only versus full setup reset. Show retained advanced settings. Keep separate Reset Fabric and Reset Setup actions. |
| F06 | P1 / S + documentation | Negative fit values are copied directly into `shrink_min` (706); Latex/Stretch Denim descriptions say negative shrinks. Blender defines negative as growth. | Fix signs/mapping and tooltips together; migration must preserve old saved behavior unless the user chooses conversion. Verify with measured edge-length changes. |
| F07 | P1 / S | First Cloth/Surface Deform and fuzzy pin names are treated as managed resources (638, 650, 1404). Existing user-authored settings/groups may be overwritten or cleared. | Explicit adopt/create actions; ownership metadata and pointers; a specific selected pin group. Preserve unrelated resources. |
| F08 | P1 / S | Wind/cage identity relies on global names (816–865, 918–943). Name collisions can modify or delete unrelated objects. | Stable setup UUID and object pointer plus ownership validation. Display names must never grant deletion authority. |
| F09 | P1 / S | Wind lookup uses global `bpy.data.objects`; another scene's rig can be linked, modified, and globally removed (816–865). Shared garment objects likewise share modifier state. | Define scene-sharing policy. Isolate setup-owned rigs; warn before editing intentionally shared data; deletion must respect other owners/scenes. |
| F10 | P2 / S | Registration has no rollback and unregister assumes complete setup (1692–1702). A later class-registration failure can leave a partially enabled add-on. | Track successful registrations, roll them back on failure, handle partial teardown. Test enable/disable/re-enable and failed enable. |
| F11 | P2 / V | Legacy/extension ZIP installation, duplicate installs, old .blend migration, and 4.2/4.5 compatibility lack regression evidence. | Build with supported packaging paths and test clean profiles. Version data schema independently of package version; publish a tested version matrix. |

## Findings table: rigs, unrigged objects, and geometry

| ID | Priority / evidence | Scenario and current issue | Required behavior / acceptance |
|---|---|---|---|
| F12 | P1 / R | Two Armatures above the intended cloth path are not handled. Stack becomes `Arm1 → Cloth → Arm2`; only the first Armature is considered (666). | Inspect the complete deformation chain. Place cloth after intended rig deformation or flag ambiguous layering; do not reorder unrelated modifiers blindly. |
| F13 | P1 / S | Rig-weight pinning sums deform weights, usually producing weight 1 on normalized skinned vertices (1180–1215). This can pin the entire garment rigidly. | Show pinned/free coverage and warn on fully pinned cloth. Offer explicit attachment groups; retain full rig-weight pinning as an advanced intentional option. |
| F14 | P1 / S | Rig-weight pinning uses only the first Armature and assumes vertex groups correspond to deformation. Envelope-only rigs, multiple rigs, absent/invalid targets, and nondeforming bones lack clear handling. | Validate the actual rig strategy. Support or explain unsupported envelopes/multi-rig cases; never report meaningful automatic pinning without usable weights. |
| F15 | P2 / R+S | Pin stiffness UI caps at 1 and calls it welded; Blender RNA allows 0–50. Weight coverage and stiffness are distinct concepts (437). | Expose a documented stiffness control with the native range or a clearly defined mapping. Test attachment error under acceleration; do not promise exact welding. |
| F16 | P1 / V | Unrigged stationary cloth, object-animation cloth, bone-parented cloth, constraints, shape keys, NLA, drivers, and retargeted rigs have no representative tests. | Explicit support matrix: free drape needs no pins; attached moving cloth needs attachment targets. Test transform animation and rig deformation separately. |
| F17 | P2 / S+V | Dynamic rest shape and rest shape keys are not exposed or validated. Squash/stretch and changing character proportions can strain rest lengths. | Offer optional Dynamic Mesh/rest-state policy. Do not enable dynamic rest shape universally: ordinary pinned cloth does not require it. Validate mutually exclusive rest controls. |
| F18 | P1 / S | No geometry preflight before cloth setup: empty meshes, loose points, degenerate faces, zero-area triangles, duplicate shells, extreme aspect ratios, or invalid coordinates. | Block empty/nonfinite/unsimulatable geometry. Diagnose other geometry risks with selectable affected regions. Open cloth sheets and deliberate sewing edges must remain valid. |
| F19 | P1 / V | Animated topology, Geometry Nodes instances, remesh/boolean changes, changing subdivision levels, and changing vertex order can invalidate simulation/cache/binding. | Validate evaluated pre-cloth mesh and stable topology over the shot. Reject unsupported changing topology with a specific remedy; allow documented static generated meshes. |
| F20 | P1 / V | Negative/nonuniform/zero scale, scaled parents, very small/large assets, and scene-unit changes are not checked. | Use world-space dimensions and unit-aware diagnostics. Block singular transforms. Never automatically apply transforms on rigs, shared meshes, or animation. |
| F21 | P1 / S+V | Pin edits on multi-user meshes or linked mesh data are not audited; only object-level library state is checked (909, 1120). | Check object and mesh editability, shared vertex-group data, and shape-key implications. Offer explicit single-user copying when necessary. |
| F22 | P2 / S | Set Pin Group clears the old matched group and switches modes without `try/finally` (1125–1144). Failure can leave partial weights or the wrong mode. | Validate first; preserve old weights and mode on failure; handle multi-object Edit Mode explicitly. Repeated aliases must not select an arbitrary group silently. |
| F23 | P2 / S | All library overrides are rejected while automatic obstacle conversion checks only `library` (789, 909). Editable overrides are rejected in one path and treated differently in another. | Check actual writability per operation; consistent behavior across setup, pins, collider conversion, bake, and preset callbacks. |

## Findings table: collisions and forces

| ID | Priority / evidence | Scenario and current issue | Required behavior / acceptance |
|---|---|---|---|
| F24 | P1 / R | An existing Cloth modifier with `use_collision=False` stays disabled even when the panel says Use Collision Objects (686–770). | Separate Enable Cloth Collisions from Auto-convert Rigid Bodies. Apply the collision-enable state explicitly and display actual status. |
| F25 | P1 / S | Automatic conversion only visits rigid-body meshes (773). A normally rigged character body is often not a rigid body and receives no automatic collision. | Explicit body/obstacle selection and missing-collider diagnosis. Do not require rigid-body physics for character collision. |
| F26 | P1 / R | Make Collider overwrites an existing collider's thickness and damping on every call (804). Tested 0.004/0.7 becomes 0.02/0.1. | Initialize defaults only on new managed modifiers; preserve authored values unless Reset Collider is chosen. |
| F27 | P1 / S | Existing collider modifier ordering is not repaired or checked. A Collision modifier before Armature can evaluate the wrong surface. | Inspect evaluated collider deformation order; test moving/skinned bodies with final intended collider geometry. |
| F28 | P1 / S+V | Fixed 0.02 collider thickness, 0.015 object margin, and fixed impulse clamps are used across asset scales. `object_distance` passed to auto-conversion is unused. | Independent, unit-aware cloth/collider offsets; show combined clearance. Tune clamps/friction on benchmarks, not as universal anti-jitter constants. |
| F29 | P1 / S | Preview silently drops self-collision except for Latex, regardless of user-requested self-collision (734–754). Layered skirts/capes can visibly change behavior. | Preserve collision policy across quality tiers. Any optional fast self-collision bypass must be explicit, visible, and mark the result as diagnostic. |
| F30 | P1 / V | Initial cloth/body intersection, body self-intersection, crossed limbs, thin fast obstacles, teleports, and strongly accelerating pins lack diagnostics/tests. | Preflight initial clearance; warn on extreme motion and discontinuities. Benchmark high-speed and tight-contact scenarios. More iterations cannot repair every invalid pose. |
| F31 | P1 / V | Overlapping layers, self-distance greater than local edge spacing, co-located seam vertices, and thin doubled surfaces can repel explosively. | Compare physical clearances, topology, and nearest-neighbor spacing; identify problematic areas. Preserve intentionally loose sewing edges. |
| F32 | P2 / S | Collision exclusions, friction, existing disabled/muted collider modifiers, hidden collections/view layers, and unwanted scene colliders are not surfaced. `collection=None` broadens existing user filters. | Show the participating colliders and exclusions. Preserve user filters or require explicit adoption; default to scene-wide collision only for new setups if that remains product policy. |
| F33 | P1 / R | New wind and turbulence empties have no field settings; writing `.field.type` raises AttributeError (831, 852). | Create real force-field objects using supported initialization; validate type and ownership before reuse. |
| F34 | P2 / S | Turning Add Wind off does not disable/remove existing wind; it only skips creation. Remove Wind disappears from UI while the toggle is off (1066, 1612). | Distinguish Create Wind, Enable Wind, and Remove Wind. Always expose cleanup for an owned rig; show whether external wind also affects cloth. |
| F35 | P2 / V | Reused winds with constraints/transforms/parents, zero-length direction, extreme strength, external effectors, and scene-sharing can yield unexpected force behavior. | Define local/world direction, preserve or diagnose constraints, expose participating forces, and test wind off→on, duplicate, undo, and reload. Zero direction currently falls back to +X; disclose it. |

## Findings table: range, baking, and failure recovery

| ID | Priority / evidence | Scenario and current issue | Required behavior / acceptance |
|---|---|---|---|
| F36 | P1 / R | Default shot start 1 minus 15 settle frames requests -14. Scene start clamps to 0, and cache hygiene then clamps cache start to 0: 15 promised settle frames become one (869–906). | Never claim unperformed pre-roll. Support a verified negative-cache/manual-evaluation workflow or offer a later shot start. Do not silently retime animation. |
| F37 | P1 / R | Requested end 20 becomes scene end 250 through `max(scene.frame_end, sim_end)` (893). | Bake exactly the displayed effective range; explicit separate scene-range extension if desired. |
| F38 | P1 / S | Invalid/reversed ranges are coerced; UI integer fields permit values beyond native cache bounds. Preview-range playback can skip pre-roll even if scene start is extended. | Validate legal ordered bounds and show shot versus simulation range. Bake independently of playback preview range; restore user timeline settings after temporary changes. |
| F39 | P1 / S | Settings/ranges are changed before freeing the bake. Cache-free exceptions are swallowed, including Animator Mode exit (896–901, 1517–1524). | Validate before mutation, free the exact cache with the correct object override, verify success, then apply settings. Stop with a useful error if cache invalidation fails. |
| F40 | P1 / S | Bake/Free Bake ignore the returned operator status and report success if no exception was raised (1307, 1337). | Check returned result and cache state; distinguish complete, cancelled, partial, failed, and not started. Never announce a successful bake from the absence of an exception. |
| F41 | P1 / R+S | Bake polling permits muted cloth; there are no mode, busy-job, disabled simulation, stale-cache, or active-view-layer checks (1289). | Shared preflight in UI and execute. Resolve exact target and cache, reject Animator Mode/muted sim/busy jobs and incompatible modes. |
| F42 | P1 / S | No persisted dirty-state contract: changes to rig action, collider animation, topology, FPS, units, gravity, or external forces are not tracked as bake dependencies. | Associate cache with its settings/dependency signature. Known edits invalidate; uncertain external edits mark Needs Validation. Do not silently reuse stale results. |
| F43 | P1 / S+V | Disk cache has no saved-file, directory, writable-storage, free-space, missing-cache, relink, or Save As checks. `use_library_path=True` alone cannot establish portability. | Validate Blender's resolved path; report it. Handle unsaved files and moved projects, distinguish memory/disk caches, and test reopen/Save As on another path. |
| F44 | P2 / S | No progress/state UI, explicit cancellation semantics, concurrent-operation guard, or per-garment queue. Bake uses immediate operator execution. | Native job/progress integration where supported; verified Escape cancellation. Serialize conflicting work and prevent edits during baking. Never reuse Mantaflow pause APIs for cloth. |
| F45 | P1 / V | Long bakes, low disk/memory, failed writes, process interruption, repeated bake/free, and undo during jobs have no tests. | Failure must leave a recoverable setup and honest cache status. Clear only owned cache files; preserve scene data; report partial results without declaring completion. |

## Findings table: Animator Mode, proxy binding, and output

| ID | Priority / evidence | Scenario and current issue | Required behavior / acceptance |
|---|---|---|---|
| F46 | P1 / R | Enter works without Cloth; exit poll requires a muted Cloth modifier. Garment becomes hidden with Exit disabled (1441–1537). | Explicit mode state independent of modifier existence; either require configured cloth on entry or support non-cloth entry/exit symmetrically. Always provide recovery. |
| F47 | P1 / R | Cage inherits `hide_render=False`; exit only hides it per view layer (955, 1528). | Cages are non-rendering helpers by default; validate render/dependency behavior while still allowing necessary evaluation. Test active and inactive Animator Mode renders. |
| F48 | P1 / R | Renaming garment/cage breaks pair lookup. Long names, duplicates, auto suffixes, and user objects starting `QC_Cage_` create similar ambiguity. | Pointer/UUID pair association, duplicate-ID repair, and orphan recovery on load. Renaming must be harmless. |
| F49 | P1 / R | Re-entering reuses the old cage without updating geometry, weights, modifiers, constraints, or replaced actions (955). | Detect source changes and rebuild safely or update the cage. Retain intended shared rig animation while synchronizing replaced actions/constraints. |
| F50 | P2 / S | Decimate is appended after deformation and other copied expensive modifiers. The original full vertex count is still processed upstream; original copied data remains in memory. | Benchmark actual playback and memory. Build a reduced rest-mesh proxy with validated weights, or describe the current feature only as a cloth-off stand-in. |
| F51 | P1 / S | State detection relies on Cloth visibility, not mode ownership. Exit forcibly unhides/enables garment regardless of its previous state. Other view layers/collections may still hide either object. | Snapshot and restore only changed state; durable mode flag plus recovery path. Handle manual deletion of cage/cloth, undo, save/reload, and excluded collections. |
| F52 | P1 / S | Surface Deform reuses the first such modifier and assigns target before checking bound state (1403–1429). Unrelated bindings can be changed/unbound. | Owned binding selection; explicit Bind, Rebind, Unbind; preserve target until safe unbind. Reject self/dependency cycles and unsupported targets. |
| F53 | P1 / V | Render mesh may already have Armature/Cloth; surface deformation can compound existing motion. Different rest poses, modifiers, scales, or evaluated topology can spoil binding. | Specify supported render stack and bind pose. Test rig+proxy together with animated poses and post-bind topology edits. |
| F54 | P2 / S | Apply as Shape captures the entire evaluated stack, not just Cloth. Object-linked material overrides, object-level rendering properties, vertex-group names, and animation semantics need explicit handling (1345). | Label as Create Static Snapshot; document scope and preserve selected intended material/render data. Verify original remains unchanged. |
| F55 | P1 / V | Dense meshes, many garments/colliders, repeated snapshots/cages, high self-collision, and long caches lack measured cost or cleanup policy. | Show evaluated simulation vertex count and frame count; warn based on measured budgets. Provide owned-helper cleanup and demonstrate repeated use does not grow resources unexpectedly. |
| F56 | P1 / V | Commercial claims such as never freezes, idempotent everywhere, and farm-friendly caching exceed current evidence. | Replace absolutes with tested support boundaries; ship sample scenes, troubleshooting, migration instructions, and a reproducible release checklist. |

## Aqua Suite patterns that apply

Local source inspected at `C:/Users/User/Downloads/blender_aqua`, corroborated by the chat **Verify the repository**.

| Existing Aqua Suite pattern | Verified location | Quick Cloth adaptation |
|---|---|---|
| Simulation-resolution buttons Preview/Medium/High/Ultra plus Custom; selected values highlighted | `ui/panel.py:99–210` | Use the requested Preview/Medium/High/Custom. Map to cloth solver settings, not fluid voxel resolution. No Ultra is required. |
| Viewport Preview/Final preserves authored values | `core/quality.py` | Separate display optimization from bake fidelity. A viewport toggle must not silently lower the bake settings. |
| Bake/Bake Again, Free enabled when cache exists, progress while busy | `ui/panel.py:213–240`, `core/bakes.py` | Adopt state-driven controls; add dirty, partial, failed, and target-specific validity states. |
| Controls disabled during bake, error reporting, ownership tags | `ui/panel.py`, `core/bakes.py`, `core/registry.py` | Per-garment ownership plus guarded operations and useful errors. Carry the design across, not fluid APIs. |
| Effective settings and explicitly approximate cost readout | `ui/panel.py:183–210` | Show evaluated vertices, solver steps, collision iterations, self-collision, frame range, and cache location. Do not copy fluid cubic-cost or memory formulas. |

## Proposed quality specification

These are **initial engineering defaults for calibration**, not proven quality guarantees. Fabric and quality are separate dimensions. Keep mass, stiffness, damping, physical clearance, fit, pressure, time scale, and pinning unchanged when changing quality.

Let `Qfabric` be the fabric's current recommended full-quality steps: Simple 5, Cotton 8, Polyester 10, Couch Leather 15, Leather Coat 12, Latex 14, Stretch Denim 11, Rigid Denim 12, Selvedge Denim 14. These recommendations themselves still need visual calibration.

| Control | Solver steps | Collision iterations | Collision policy | Intended use |
|---|---:|---:|---|---|
| Preview | `max(6, ceil(Qfabric / 2))` | 3 | Preserve user-authored object/self-collision settings | Timing and broad-motion checks; visibly label resulting cache Preview. |
| Medium (default) | `max(12, Qfabric)` | 5 | Preserve authored policy | Normal iteration and candidate delivery for scenes that pass visual checks. |
| High | `max(20, ceil(1.5 × Qfabric))` | 8 | Preserve authored policy | Fast motion, tight contact, layered cloth, closer shots; still requires validation. |
| Custom | Explicit native-valid user values | Explicit native-valid user values | Explicit user choices | Specialized shots; enforce hard API bounds, show soft stability warnings. |

Quality behavior requirements:

1. Persist quality per garment. A scene default may initialize newly created garments only.
2. Highlight the selected preset, and show resolved values. Direct edits to preset-controlled fields switch to Custom, preserving the values the user just entered.
3. Preserve previous Custom values when visiting other tiers; restoring Custom restores the saved custom pair. Fabric edits do not erase custom quality.
4. Fabric choice may update the tier's recommended solver count, but must not quietly change a previously baked result. Mark it dirty and show the new effective settings.
5. Preview does not silently disable necessary collisions. An optional **Skip Self Collision for Preview** is a separate explicit diagnostic override, clearly marked on the cache and never inherited by Medium/High.
6. Viewport optimization/Animator Mode is distinct from Simulation Quality. Display-only reduction must not change exported/rendered garment topology or final physics behind the user's back.
7. No quality tier silently reduces collision margins, changes time scale, retimes animation, applies transforms, or modifies render subdivision. Such changes alter the scene/result, not just numerical fidelity.
8. Native API bounds must be checked for the running supported version. Preset values are targets subject to explicit validation, not values silently clamped and misreported.
9. Offer Bake Preview for intentional diagnostic bakes, with a visible quality label. Do not prohibit all Preview bakes, and do not call a Preview cache final-quality output.
10. Migrate legacy Final to Custom with its authored numerical values, or provide a transparent migration policy. Reinterpreting old Final as new High would silently change existing projects.

## Bake button validations and state contract

Run lightweight checks for UI enablement and the full preflight again inside execute. `poll()` alone is not a validation boundary. Every check must explain the affected object and a concrete remedy.

| Gate | Block or warn | Required behavior |
|---|---|---|
| Correct mesh/setup/cache | Block if missing, stale pointer, cage target, excluded target, or ambiguous setup | Resolve by owned identity, not current name or first modifier. Display target garment. |
| Compatible mode and visibility | Block Edit Mode and disabled/muted Cloth/Animator Mode | Offer Exit Animator Mode or select the garment. Do not toggle modes silently inside Bake. |
| Scene/editability | Block operations that cannot legally change settings/cache | Check object, mesh, and actual override permissions. Support valid editable overrides. |
| Existing job | Block overlapping/conflicting job | Disable Bake, Free, setup, quality and ownership mutations; show progress and cancellation instructions. |
| Mesh data | Block empty/nonfinite/singular input or unsupported topology changes | Warn/select degenerate areas and other diagnosable risks; open sheets are valid. |
| Range/pre-roll | Block invalid bounds or unsupported promised pre-roll | Show exact shot range, cache range, and effective settle count. A shortened settle window requires a visible correction, not silent success. |
| Current settings | Block failed application or native value mismatch | Resolve tier and fabric; compare requested versus effective values; verify target cache invalidation before applying changes. |
| Existing bake | Require explicit Rebuild Bake when replacing a usable cache | Free the exact target cache and verify state. A normal parameter edit only marks dirty; it must not silently destroy the old bake. |
| Pins/rig | Warn on zero attachment weights for attached workflows, all-pinned cloth, missing rig target, or ambiguous stack | Free draping without a rig or pins remains fully supported. |
| Colliders | Warn when intended body/obstacles lack enabled collision or deformation order is wrong | Zero colliders is legitimate for freely falling or hanging cloth. Do not universally require colliders. |
| Initial clearance | Warn or block severe known intersections in delivery mode | Identify cloth-body and self-intersecting regions. Permit explicit diagnostic bake of intentional sewing/assembly setups. |
| Scale/motion | Warn on nonuniform/negative scales, extreme size, severe acceleration/teleport | Block singular transforms. Offer safe remedies without applying transforms/retiming rigs automatically. |
| Pressure/sewing | Warn on volume pressure with unsuitable topology or sewing with no eligible loose edges | Do not reject ordinary open cloth. Diagnose the enabled feature's requirements. |
| Storage | Block disk mode with unresolved/unwritable path or insufficient verified space | Require Save As when Blender's relative disk-cache location needs it. Memory-cache workflows remain separately supported. |
| Cost | Warn using clearly labeled approximate memory/duration information | Show frame and vertex counts. Do not present an uncalibrated time estimate as a guarantee. |
| Completion | Verify operator return and cache state/range | Cancelled/failed/partial must not display Baked. Re-evaluate state after job completion, not immediately after scheduling. |
| Save/reopen | Check persistent cache and dependency metadata | Missing, changed-version, or mismatching cache becomes Needs Validation/Dirty, never assumed current. |

| State | Main button | Other behavior |
|---|---|---|
| No setup | Set Up Cloth | Explain missing configuration. |
| Invalid | Bake disabled with reason | Offer relevant repair actions; diagnostics remain available. |
| Ready, no bake | Bake — Preview/Medium/High/Custom | Show exact target, range, and effective settings. |
| Baking | Baking… | Progress; verified Escape cancellation for point cache; controls locked. |
| Baked/current | Rebuild Bake | Show baked tier, range, version, and timestamp. Free Bake enabled. |
| Baked/dirty | Rebuild Bake — settings changed | Old bake is identified as stale and retained until explicit rebuild/free. |
| Cancelled/partial | Bake Again / Free Partial Cache as supported | Do not promise resume unless that exact cloth-cache workflow is implemented and tested. |
| Failed/missing cache | Retry Bake + diagnostic | Keep original garment and setup recoverable. |

Suggested bake transaction: resolve target → validate → snapshot user context → explicitly invalidate owned old cache → apply settings/range → verify native values → start native bake → monitor → verify completion → record result/signature → restore temporary context. Use targeted rollback for pre-bake failure; cache destruction cannot be pretended reversible. Do not promise pause/resume or a dedicated Cancel operator merely because Aqua Suite's fluid bake supports it.

## Collision acceptance standard for this product

The target is acceptable gameplay-style visuals **in Blender**. This does not certify any engine's runtime solver. Blender's cloth is a numerical simulation; no tier can guarantee arbitrary meshes never penetrate. The commercial promise should name tested scene classes, limits, and remedies.

Proposed release thresholds below are a product specification to calibrate, not measured results:

| Criterion | Proposed acceptance |
|---|---|
| Whole-surface tunnelling | Zero cloth panels passing completely through a supported collider during the benchmark shot. Test both frame samples and appropriate motion/subframe diagnostics. |
| Small penetration tolerance | For human-scale fixtures, use 2 mm as an initial measured tolerance; scale the fixture/spec explicitly for miniature/giant assets. No sustained visible penetration at the delivery camera. Tight hero shots may need a stricter tolerance. |
| Measurement method | Use evaluated cloth and collider surfaces, triangle/edge tests and signed distance where a valid closed oriented collider permits it. Vertex-only nearest-distance tests miss face/edge crossings; open colliders require a different contact test. Report sampling coverage rather than claiming continuous proof. |
| Clearance/puffiness | Contact gap is consistent with declared cloth/collider margins; no unexplained floating shell. Review silhouettes and close contacts as well as distance numbers. |
| At-rest stability | After settling, no visible persistent contact chatter; log residual displacement relative to the moving collider, excluding intentional wind/rig motion. Establish fixture-specific numeric limits from approved reference output. |
| Pin attachments | No visible collar/waist/corner detachment in the supported acceleration range; measure pinned-target error separately from cloth penetration. Fully pinned cloth is intentional only when explicitly chosen. |
| Layered cloth | No persistent layer swaps or visible self-intersections in the defined cape/skirt/coat benchmarks with self-collision enabled. |
| Repeatability | Repeat bake and save/reopen match within chosen positional tolerances on the same version/hardware class. Do not promise bit-identical results across Blender versions. |
| Performance | Publish measured wall time, peak memory, vertices, colliders, frames, hardware and tier. A universal FPS or bake-time claim is unacceptable without workload limits. |

Blender documents collision quality and distance as tradeoffs and recommends solver-quality increases for fast motion; those controls improve robustness but do not replace valid geometry, clearances, and animation. See [Blender cloth collision settings](https://docs.blender.org/manual/id/3.5/physics/cloth/settings/collisions.html). Negative shrinking grows cloth, and Dynamic Mesh changes rest shape rather than simply turning on rig support: [Blender cloth shape settings](https://docs.blender.org/manual/en/5.4/physics/cloth/settings/shape.html). The second page is reference documentation; implementation must be verified against each supported installed version.

## Required regression and visual scenario matrix

Run relevant combinations rather than assuming one happy-path example represents a category. Every case specifies both expected supported behavior and an intentional rejection path where appropriate.

| Group | Scenarios to exercise | Release evidence |
|---|---|---|
| Unrigged cloth | Free drop; table/sphere drape; pinned flag; hanging curtain; moving/rotating/scaling object; zero gravity + wind | Approved bake/video and attachment/contact measurements. |
| Ordinary rigs | Cape collar, skirt waistband, shirt shoulders; walking, running, crouching, sitting, jumping, turning | Pins follow evaluated rig, free areas drape, correct moving-body collision. |
| Complex rigs | Multiple Armatures, bone parenting, constraints, NLA blends, drivers, shape keys, replaced action, squash/stretch | Supported paths pass; ambiguous/unsupported paths rejected without damage. |
| Collision types | Static plane/sphere/box, concave chair, thin pole, fast moving prop, skinned body, shape-key body, rigid body | Correct evaluated geometry and documented speed/thickness limits. |
| Collision stress | Initial penetration, crossed arms/legs, body self-intersection, teleport, fast spin, narrow gaps, overlapping garments | Predictable diagnosis; no unsupported universal success claim. |
| Self collision/seams | Folding flag, layered cape/skirt, sleeves against torso, sewn panels, duplicate vertices, tight self margins | Contacts stable; deliberate sewing edges preserved. |
| Fabric features | All nine presets at all four tiers; sewing on/off, pressure on/off, internal springs, shrink/grow | Behavior distinguishable and documented; no accidental retained feature masquerading as a fabric preset. |
| Geometry | Tri/quads/ngons; low/high density; long thin faces; disconnected islands; open edges; nonmanifold intersections; empty mesh | Valid open cloth works; invalid cases have useful errors. |
| Units/transforms | Meter/cm/mm scenes; tiny/giant fixtures; applied/unapplied uniform scale; nonuniform/negative/zero scale; scaled parents | Physically interpretable margins; destructive automatic fixes prohibited. |
| Modifier stacks | Armature, shape deformation, subdivision, solidify, mirror, GN geometry, remesh, render proxy | Stable topology and correct pre/post-simulation ordering. |
| Ranges | Start 1 with default settle; start 100; start 0; reversed/single-frame ranges; huge bounds; preview range enabled; seek/backward playback | UI matches exact baked interval and settle behavior. |
| Cache dependencies | Change stiffness, tier, pins, rig animation, collider, gravity, FPS, units, topology, force fields | Dirty state and explicit rebuild; no stale-success UI. |
| Storage/recovery | Unsaved file, disk vs memory, read-only/full/missing storage, Save As, moved cache, reopen, interrupted bake | Correct errors, no false completion, recoverable setup. |
| Animator lifecycle | Enter/exit repeatedly; no cloth; delete/rename cage or garment; duplicate; undo/redo; edit source; different view layers | Reliable recovery, restored visibility, no helper in render. |
| Proxy binding | Bind/unbind/rebind, mismatched pose/scale, pre-existing binding, missing target, topology edits, rigged render mesh | Original modifiers preserved; correct deformation without dependency cycles. |
| Multi-object/scenes | Two different fabrics, shared mesh, linked/override data, duplicated scene, shared objects, same display names | Ownership isolation and honest sharing behavior. |
| Installation | Clean 4.1 legacy; clean supported extension versions; disable/re-enable; failed enable retry; old saved projects | Verified packaged archive and migration tests. |
| Repetition/performance | Many garments/colliders; 100 setup/toggle cycles; repeated bake/free/snapshot/delete; long shot | Bounded owned-resource growth and published benchmark measurements. |

## Delivery plan and release gate

1. **Restore correctness:** F01, wind initialization, shrink semantics, pre-roll/range, collision enablement, and settings-before-bake contract. Add regression tests reproducing the failures above.
2. **Protect user scenes:** object-owned settings, resource identity/adoption, collider preservation, editable overrides, reliable Animator Mode and proxy lifecycle.
3. **Implement quality and bake UX:** requested four tiers, effective values, shared preflight, dirty/cache state, progress/cancellation semantics, disk validation.
4. **Calibrate visual behavior:** representative rigged/unrigged fixtures, collision tolerances, preset tuning, hardware measurements. Passing API smoke tests does not satisfy this stage.
5. **Ship only with evidence:** all P0/P1 release issues resolved or explicitly removed from supported scope; every supported-version install/bake/reopen path passes; reference videos/scenes and known limitations accompany the build.

No production fixes or quality controls were implemented in this audit pass.
