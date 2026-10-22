# What's left

Updated: 2026-10-22

Quick Cloth is undergoing commercial-readiness validation. Passing automated tests is not a commercial certification.

## Current implementation verification

The latest fixes protect bone weights and existing attachment weights during automatic pinning, and expand cache signatures to include parenting and driver-target settings. A regression exposed a shared serializer bug that omitted string/enum properties; this is now corrected. All **34 regression executions passed** across Blender 4.1.1 and 5.1.2. The implementation fixes are in commit `a7f240c`.

The seventh review made cache signatures stable across save/reopen and stopped Simulate from initializing an Animator Mode cage before refusing it (`docs/SEVENTH_REVIEW_FIXES.md`). All **36 regression executions passed** across Blender 4.5.4 LTS and 5.2.2 LTS; results are recorded in `tests/results/summary.json`. 4.1.1 and 5.1.2 were not rerun for these fixes.

## Remaining release gates

| Priority | Work | Acceptance criteria |
|---|---|---|
| High | Interactive bake/cancel/recovery | Verify progress, Escape cancellation, retry, timer cleanup, frame restoration, and cache state in Blender's UI. |
| High | Rigged and unrigged collision scenes | Validate fast motion, thin colliders, layered garments, self-collision, starting intersections, pinned regions, and animated bodies. Record visible penetration, jitter, and stability against documented shot-specific tolerances. |
| High | Blender 4.2 and 4.5 compatibility | Install the supported package format on each version; exercise registration, presets, setup, baking, reopening cached scenes, rigs, and proxy workflows. Automated coverage now includes 4.5.4 LTS and 5.2.2 LTS (previously 4.1.1 and 5.1.2); 4.2 and interactive installation remain untested. |
| High | Storage-failure recovery | Inject disk-full and unwritable cache-directory failures. Require actionable errors, correct cache status, and successful recovery after storage is restored. |
| Medium | Performance and memory | Benchmark realistic garment meshes, frame ranges, collisions, and all quality tiers. Publish measured limits and recommended proxy sizes. |
| Medium | Quality and bake UI acceptance | Exercise Preview, Medium, High, and Custom; verify custom-value restoration, displayed ranges, bake validation, rebuild confirmation, and switching between multiple garments. |
| Medium | Final packaging and release sign-off | Rebuild archives from the verified commit, check clean installs/upgrades, confirm documentation and known limitations, and retain test evidence and package checksums. |

## Validation boundaries

- Collision acceptance targets engine-neutral visual quality in Blender, not a specific engine export/runtime workflow.
- Arbitrary external driver inputs cannot be guaranteed by local dependency signatures.
- Expanded dependency signatures may require rebuilding caches recorded by earlier builds.
- Recent scoped reviews do not prove that every possible edge case is covered.

## Suggested next task

Create a repeatable set of rigged and unrigged collision scenes with explicit visual acceptance criteria, then perform interactive bake/cancel testing on those scenes.
