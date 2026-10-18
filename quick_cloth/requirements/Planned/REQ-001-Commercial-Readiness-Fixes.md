# REQ-001 — Quick Cloth commercial-readiness fixes

| Field | Value |
|---|---|
| ID | REQ-001 |
| Status | Planned — implementation not started |
| Priority | Release-blocking |
| Baseline | Quick Cloth 1.0.3, source commit `f21d3b5` |
| Created / updated | 2026-10-18 |
| Scope | Setup, rigs, unrigged cloth, collisions, quality, baking, ownership, proxies, migration, tests and packaging |
| Target | Engine-neutral visual quality inside Blender |
| Source | [Commercial-readiness audit](../../audit/COMMERCIAL_READINESS_AUDIT.md) — findings F01–F56 |

## Objective

Apply the audited fixes and deliver reliable cloth setup and baking for rigged garments and unrigged meshes. Add Preview, Medium, High and Custom simulation-quality presets, honest bake validation/state controls, and regression coverage. Preserve user-authored scene data and existing saved results during migration.

Completion requires implementation and demonstrated acceptance, not only code changes or successful registration. The audit's runtime probes isolate downstream defects by patching a missing declaration in memory; release tests must execute the actual packaged source without such patches.

## Scope and constraints

- Support free drape, pinned unrigged cloth, transform-animated cloth, and ordinary skinned garments. Neither a rig nor pins nor colliders are mandatory for every cloth setup.
- Handle advanced rigs and unusual geometry through explicitly tested support or actionable validation errors. Do not silently pretend an unsupported setup is supported.
- Retain Blender's native cloth solver. Engine export, engine runtime cloth, and a replacement collision solver are outside this requirement.
- Preserve the advertised legacy Blender 4.1 and extension Blender 4.2+ installation paths unless a separately documented product decision changes them. Test representative supported versions; do not infer 4.2 compatibility from 4.1 or 5.1.
- Never auto-apply rig transforms, retime animation, overwrite unrelated modifiers/groups, or delete resources based on names alone.
- No guarantee of zero penetration for arbitrary scenes. Commercial claims must match the defined fixtures, limits, and evidence.
- Aqua Suite supplies UX/ownership patterns, not fluid solver settings or pause APIs. The audit records the inspected source locations.
- All findings F01–F56 require a recorded disposition: fixed and verified, supported limitation with validation, or explicitly deferred with release impact. P0/P1 findings may not be silently deferred.

## Required architecture and behavior

### R1 — Load, register, and migrate safely

1. Restore the missing collider operator class and the separate rig-weight pinning operator. Every panel operator must exist under a unique ID.
2. Make registration transactional and teardown safe after partial failure. Avoid scene access in restricted registration contexts.
3. Introduce a saved data-schema version separate from the add-on package version.
4. Migrate scene-level settings to per-garment setup data without overwriting existing live cloth settings. Existing modifiers are the primary evidence for already configured garments; scene values alone cannot reconstruct multiple previous fabrics.
5. Migrate old Final to Custom with its existing authored numerical values. Preserve old shrink behavior unless the user explicitly requests the corrected fit semantics. Identify uncertain legacy state rather than guessing.

### R2 — Own resources and isolate setups

1. Store authored settings and stable identity per garment/setup. Use pointers plus ownership metadata for cages, winds, modifiers and bindings; display names do not confer ownership.
2. Detect duplicated identities and missing targets. Rename, duplicate, save/reload and undo must not break or misassociate setups.
3. Require explicit adoption before changing a user's existing setup or replacing an unrelated pin group/binding. Never create a second Cloth modifier where Blender disallows it.
4. Make sharing between scenes and multi-user mesh data explicit. Preserve unrelated objects and resources when freeing caches or removing helpers.
5. Check actual object/mesh/override writability per operation; do not blanket-reject all editable overrides or inconsistently edit locked ones.

### R3 — Rigs, pins, and geometry

1. Inspect the complete modifier/deformation chain. Position Cloth after the intended rig deformation and before intended finishing modifiers, or report ambiguous ordering without destructive reordering.
2. Offer explicit pin-group selection. Report weighted/free vertex coverage; warn when automatic rig-weight pinning makes the entire garment rigid.
3. Distinguish pin weights from pin stiffness. Expose native-valid stiffness or document an explicit mapping; remove unsupported promises of exact welding.
4. Support unrigged free drape and pinned objects without rig-only validation failures.
5. Check empty/nonfinite geometry, singular transforms, unstable evaluated topology, feature-specific mesh requirements, and shared data. Open cloth sheets and legitimate sewing edges remain valid.
6. Provide optional, documented dynamic-rest-shape/rest-shape-key handling. Do not require Dynamic Mesh for ordinary rig-following pins.
7. Pin editing must restore mode and preserve previous data on failure; define multi-object Edit Mode behavior.

### R4 — Collisions, fabric presets, and wind

1. Separate cloth collision enablement from automatic rigid-body collider conversion. Apply actual collision-enable state and show effective participation.
2. Allow explicit character body/obstacle selection without adding rigid-body physics. Validate collider enablement and deformation order.
3. Initialize collider defaults only on newly created managed colliders. Preserve existing thickness, damping, filters and exclusions unless explicitly reset/adopted.
4. Surface unit-aware cloth/collider clearance and relevant friction/clamping settings. Remove universal anti-jitter claims; calibrate defaults against fixtures.
5. Correct shrink/grow semantics and preset descriptions together, subject to R1 migration. Define which settings a fabric preset resets and which it retains.
6. Validate initial intersections, problematic spacing and extreme motion through actionable diagnostics. Do not claim higher quality repairs invalid geometry or impossible poses.
7. Create wind/turbulence using supported field initialization. Distinguish creation, enablement and removal; make cleanup accessible while disabled. Affect only owned rigs.
8. Retain scene-wide collision as a default for new setups if desired; never silently erase an adopted user's deliberate filtering. Show participating collider objects.

### R5 — Quality presets

Quality is separate from fabric and viewport display optimization. The following values are initial calibration targets. `Qfabric` is the fabric's recommended full-quality solver count; the audit lists the current nine values.

| Preset | Solver steps | Collision iterations | Policy |
|---|---:|---:|---|
| Preview | `max(6, ceil(Qfabric / 2))` | 3 | Diagnostic timing/motion bake; visibly labelled Preview |
| Medium, default | `max(12, Qfabric)` | 5 | Normal iteration; delivery only when acceptance passes |
| High | `max(20, ceil(1.5 * Qfabric))` | 8 | Tight contact, faster motion, closer shots |
| Custom | User values within running Blender's native bounds | User values within native bounds | Preserve exact authored intent |

- Persist quality per garment and display the effective values.
- Editing tier-controlled numerical values selects Custom. Preserve the last Custom values when switching between tiers.
- Do not change mass, stiffness, damping, fit, pressure, pins, time scale, physical margins or render subdivision when changing quality.
- Preserve authored object/self-collision settings across tiers. Any Preview self-collision bypass must be an explicit diagnostic control, not inherited by Medium/High.
- Changing quality marks a previous bake dirty; it must not silently destroy that cache.
- One resolver must supply the same effective settings to setup, UI validation and Bake. Detect native clamping rather than displaying values that were not applied.

### R6 — Exact ranges and reliable baking

1. Display shot range, simulation range, and effective settle count separately. Bake precisely the shown interval; do not extend to scene end implicitly.
2. Handle negative pre-roll explicitly. Either implement and verify a supported negative-cache/evaluation workflow or reject the impossible promise and offer an actionable range change. Never silently shorten pre-roll or retime animation.
3. Validate ordered native-valid bounds and preview-range interactions. Restore any temporary context/timeline changes.
4. Implement a shared preflight used by UI eligibility and again inside execute.
5. Resolve and verify the exact target/cache; invalidate an explicitly replaced old bake before applying new settings. Stop on invalidation failure.
6. Check native operator return status and cache completion state/range. No success report based solely on absence of exceptions.
7. Store bake metadata and dependency state. Relevant edits mark Dirty; unverified external changes mark Needs Validation. Include rig/collider animation, topology, FPS, gravity, forces and simulation settings.
8. Validate saved-file requirements, resolved cache paths, writable storage and missing/moved files. Memory and disk modes need separate honest persistence behavior.
9. Integrate progress and verified cancellation behavior for cloth point caches. Do not promise fluid-style pause/resume. Prevent conflicting operations during jobs.

| Validation | Behavior |
|---|---|
| Missing/wrong target, cage target, disabled cloth, Animator Mode, incompatible edit mode | Block and explain remedy |
| Conflicting job or inaccessible target/cache | Block |
| Empty/nonfinite mesh, singular transform, unsupported changing topology | Block |
| Invalid range or unsupported promised pre-roll | Block |
| Entirely pinned attached garment, missing intended collider, severe initial intersection, extreme motion | Warn with affected objects/regions; define stricter delivery-mode policy where appropriate |
| Intentional free drape without rig/pins/colliders | Allow |
| Existing usable bake with changed settings | Require explicit Rebuild Bake; retain old cache until that action |
| Unresolved/unwritable disk-cache path | Block disk bake; identify actual path/error |
| Completed native job | Verify status/cache/range before marking Baked |
| Cancelled/partial/failed job | Report exact state and recovery action; never claim completion |

Required UI states: No Setup, Invalid, Ready, Baking, Baked/Current, Baked/Dirty, Cancelled/Partial, Failed/Missing Cache. Free Bake is available only for a freeable owned cache and never while conflicting work is running. Invalid controls must expose a reason, not merely appear grey.

### R7 — Animator Mode, proxies, and snapshots

1. Make entry/exit symmetrical, including missing/deleted cloth or cages. Store explicit mode state and provide recovery independent of modifier visibility.
2. Snapshot and restore only the visibility/settings the add-on changed. Cages must not appear in renders.
3. Refresh or safely rebuild outdated cages after geometry, weights, modifiers, constraints or action changes. Rename must not affect pairing.
4. Benchmark cage playback and memory. Decimation after full rig evaluation is not evidence of reduced deformation cost.
5. Separate owned Bind, Rebind and Unbind operations. Preserve unrelated Surface Deform modifiers and validate bind pose, topology, transforms and dependency cycles.
6. Define supported rigged render-mesh/proxy stacks to avoid double deformation.
7. Describe Apply as Shape as a static evaluated snapshot; preserve intended materials/render data and leave the source intact.

## Implementation slices and finding traceability

Each slice delivers code, meaningful regression tests, and documentation updates. Mark audit finding IDs in test descriptions and the completion record. Some findings span multiple slices.

| Order | Slice | Audit findings | Exit evidence |
|---|---|---|---|
| 1 | Startup and registration | F01, F10–F11 | Real source imports/registers/unregisters; install checks |
| 2 | Setup data, ownership and migration | F02, F04–F09, F21, F23 | Multi-garment/scene isolation; adoption and legacy-file tests |
| 3 | Rig/mesh/pin correctness | F12–F22 | Rigged and unrigged fixtures; useful geometry errors |
| 4 | Collision, presets and forces | F06, F24–F35 | Collider preservation, field creation and calibrated contact fixtures |
| 5 | Four quality presets | F03, F05, F29 | Resolver parity, Custom restoration and dirty-state tests |
| 6 | Ranges and bake lifecycle | F36–F45 | Exact ranges, failure injection, completion/storage tests |
| 7 | Animator/proxy/output lifecycle | F46–F54 | Rename/delete/reload/undo and render-helper checks |
| 8 | Performance, packaging and release | F11, F55–F56; all previous findings | Supported-version matrix, visual references, benchmark and release checklist |

## Acceptance checklist

- [ ] **AC01 — Unpatched loading:** actual source and packaged add-on load with every operator available; enable/disable/re-enable and partial registration recovery work.
- [ ] **AC02 — Settings isolation:** two garments with different fabrics retain their own settings through selection changes, refresh, bake, undo and reload.
- [ ] **AC03 — Ownership:** rename, duplicate, cross-scene sharing and removal cannot modify/delete unrelated resources; linked/override errors are consistent.
- [ ] **AC04 — Migration:** legacy files preserve their existing effective simulation and cache until explicit conversion/rebuild; ambiguous legacy state is explained.
- [ ] **AC05 — Rig support:** attachment targets follow evaluated ordinary rigs; complete deformation stacks are handled or diagnosed; normalized rig weights cannot silently masquerade as free cloth.
- [ ] **AC06 — Unrigged support:** free drop, drape, pinned curtain/flag, and transform-animated cloth pass without requiring an armature.
- [ ] **AC07 — Geometry validation:** invalid input fails without partial destructive changes; open sheets/sewing edges remain supported.
- [ ] **AC08 — Collisions:** enablement is synchronized, rigged bodies work without rigid bodies, existing collider values survive repeated setup, and evaluated collider ordering is correct.
- [ ] **AC09 — Forces/fabrics:** wind creates/enables/disables/removes correctly; fit semantics and feature-retention behavior match documentation and migration policy.
- [ ] **AC10 — Quality:** Preview/Medium/High/Custom resolve identically in UI/setup/Bake; Custom restores authored values; tier changes preserve physical behavior settings and mark stale bakes.
- [ ] **AC11 — Exact range:** shot start 1 with 15 settle frames has a truthful supported outcome; requested end 20 never silently becomes 250; preview range and native bounds are tested.
- [ ] **AC12 — Bake validations:** every validation row above has a passing execution-path test or documented UI verification. Bake is blocked for muted cloth and conflicting jobs.
- [ ] **AC13 — Bake truthfulness:** cancellation, operator CANCELLED result, exception, incomplete cache and invalidation failure never report success.
- [ ] **AC14 — Storage/dependencies:** changed rig/collider/settings mark dirty; unsaved/read-only/moved/missing disk-cache cases are recoverable; save/reopen verifies persistence.
- [ ] **AC15 — Animator recovery:** no-cloth entry policy, repeated entry/exit, rename, deletion, source edits, view layers, undo and reload work; helpers remain absent from renders.
- [ ] **AC16 — Proxy/snapshot safety:** owned binding operations preserve other modifiers; rigged proxy output avoids double deformation; static snapshots preserve intended appearance.
- [ ] **AC17 — Visual collision gate:** approved fixtures meet the criteria below at recorded quality settings; evidence includes rigged and unrigged bakes, not just API checks.
- [ ] **AC18 — Performance/repetition:** record bake time and peak memory for known workloads/hardware; repeated setup, cage, bake/free and cleanup show bounded resource counts.
- [ ] **AC19 — Package compatibility:** test legacy 4.1 and declared extension-version targets, including 4.2 and representative newer versions. Unavailable target runtimes remain explicitly unverified.
- [ ] **AC20 — Release completeness:** all F01–F56 have traceable dispositions; no unresolved release-blocking P0/P1; README, sample scenes, limitations and troubleshooting match delivered behavior.

## Visual and collision acceptance

The thresholds below are provisional product targets to calibrate against approved fixtures, not claims that current source passes.

- Zero complete cloth panels tunnelling through supported colliders during benchmark shots.
- Initial penetration tolerance of 2 mm on human-scale fixtures, with no sustained visible clipping at the delivery camera. Record scale and stricter close-up tolerances explicitly.
- No persistent layer swaps, visible attachment separation, unexplained clearance gaps or sustained at-rest contact chatter.
- Measure evaluated surfaces and attachment error. Vertex-only nearest distances are insufficient to detect all face/edge crossings; record sampling coverage and use appropriate triangle/contact checks.
- Repeat bakes and save/reopen must agree within fixture tolerances on the same tested version/hardware class; do not demand bit-identical cross-version simulations.
- Exercise static drape; pinned flag/curtain; rigged cape, skirt and shirt; walking/running/crouching/sitting/jumping; static and animated/skinned colliders; thin/fast props; layered cloth; and intentional invalid starting intersections.
- Use the full scenario matrix in the source audit for scale, topology, constraints/NLA/shape keys, storage failures, multiple scenes and performance cases.

## Test and delivery artifacts

1. Automated Blender regression suite with per-test results, version information, nonzero failure status and timeout handling. Avoid relying only on Blender process exit codes, which can be zero after script exceptions.
2. Separate fast lifecycle/API tests from actual simulation/bake tests and visual/manual checks. Preserve fixture files and expected tolerances.
3. Run representative rigged/unrigged simulation and storage recovery tests on each supported release target. Test native operator cancellation/progress in an interactive session where headless checks cannot establish UI behavior.
4. Maintain a finding disposition table with ID, fix location, regression test, tested versions, remaining limitations and evidence path.
5. Update README and release notes, document migration/backup behavior and support boundaries, and produce validated install archives. Creating this requirement does not authorize publishing a release.

Definition of done: all acceptance items checked with accessible evidence, all release-blocking findings resolved, calibrated visual fixtures accepted, and the exact distribution archive verified. Code implementation alone does not close this requirement.

## Current status

Requirement created. No production fixes have been applied under REQ-001. Audit observations and baseline probes are available in `audit/`; they are diagnostic evidence, not passing release tests.
