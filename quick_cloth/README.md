# Quick Cloth 1.1.0 — validation build

Per-garment cloth setup and native Blender baking for rigged garments and unrigged meshes.

This build implements the eight REQ-001 development slices. **Commercial release approval is still pending** the visual, interactive and compatibility gates in [release status](docs/RELEASE_STATUS.md). It is not an engine exporter or a replacement cloth solver.

## Install

- Blender 4.2+: install the extension ZIP from `dist/quick_cloth-1.1.0.zip` through Install from Disk.
- Blender 4.1: use `dist/quick_cloth-1.1.0-legacy.zip` through legacy add-on installation.
- Restart Blender when replacing an earlier development build. Back up production .blend files before adopting/migrating existing setups.

Run `python tools/build.py` to make both archives. Packaging uses an explicit allowlist; tests, audit files and local caches are not distributed. Registration and actual simulation tests run on 4.1.1 and 5.1.2; 4.2/4.5 and interactive extension installation still require verification.

## Workflow

1. Select a mesh. Existing Cloth requires **Adopt Existing Cloth**, which reads live settings without changing the modifier/cache.
2. Choose a fabric starting point. Settings belong to that garment. Presets reset their listed fabric values, not pressure, gravity, attachments or every advanced feature.
3. For attachments, choose a vertex group or select vertices in Edit Mode and use **Set Pin Group**. New groups are named QC Attachment; an unrelated group named pin is preserved. Automatic rig-weight pinning is an advanced starting point and can pin every vertex: paint weights down where cloth must move freely.
4. Choose a body/obstacle and **Make Body Collider**, or select obstacles and use **Make Collider(s)**. Rigged bodies do not need rigid-body physics. Existing collider parameters and collision filters are preserved.
5. Choose **Preview / Medium / High / Custom** and an exact range, then **Simulate Cloth!** to configure. Play sequentially from simulation start for live evaluation.
6. Inspect the setup/contact diagnostics. **Bake** resolves current settings again. **Rebuild Bake** explicitly replaces an existing cache. **Free Bake** frees only the selected garment's cache.

## Quality and fabric

Medium is the default. Preview reduces solver work without silently disabling self-collision. High raises solver steps and collision iterations. Custom stores edited values and restores them after visiting other tiers. Effective numerical settings are visible.

Quality does not alter physical mass, stiffness, damping, distances, pressure, time scale or attachments. Fabric selection can change its own prescribed values. Positive Fit Tightness shrinks and negative grows. Adopted legacy shrink values retain their actual behavior; selecting a new fabric applies corrected preset signs.

## Baking and storage

- Settle Frames defaults to **0**. Negative pre-roll is rejected explicitly: increase the shot start or reduce settling; animation is never automatically retimed.
- The requested end frame is respected, independent of the scene's end. Baking restores the playhead.
- Disk cache requires a saved .blend and writable storage. Native caches are stored in the displayed `blendcache_<filename>` directory beside that file. Keep the cache folder with the project and revalidate after Save As/moving files.
- Preview bakes are diagnostic, not certified final quality.
- Existing bakes are retained when settings change and shown as Dirty/Needs Validation. Validate Cache Dependencies compares recorded inputs; scene evaluation and reload conservatively request validation. External driver inputs and visual correctness still require review.
- Interactive native bake progress/Escape integration is implemented but awaits interactive acceptance. No dedicated pause/resume promise is made.

## Animator Mode and render proxies

Animator Mode requires configured cloth. It mutes the cloth in the viewport and creates a non-rendering stand-in. Re-entry rebuilds the stand-in to pick up geometry/rig changes. Exit restores recorded visibility and retains old caches for explicit validation/rebuild. Recover Hidden Garment can restore a single hidden setup even if its cage was deleted.

Cage decimation occurs after copied deformation: this mode avoids cloth solving but is **not a measured low-poly rig optimization**. Render meshes driven by Surface Deform must not also carry Armature/Cloth; put those on the simulation proxy. Bind at simulation start. Bind, Rebind and Unbind are explicit operations and preserve unrelated Surface Deform modifiers.

Create Static Snapshot captures the full evaluated mesh stack into a new object. It does not produce a shape key or an animated export.

## Supported boundaries

- Free-draping open sheets are valid; rigs, pins and colliders are optional for such setups.
- Empty/zero-area/nonfinite meshes, singular transforms and known unsupported upstream changing-topology modifiers are blocked.
- Automatic rig-weight pinning requires one vertex-group armature. Other rig strategies need explicit attachment groups and validation.
- Cross-scene shared garment objects must be copied for independent simulation. Pin editing on shared mesh data requires making the mesh single-user first.
- Physics margins must be tuned to asset scale. The current contact diagnostic examines the evaluated current pose and reports surface overlaps; it is not a continuous/full-shot penetration test.
- Advanced rigs, fast thin colliders, complex layered clothing and extreme pressure/scale need shot-specific validation. See the release status for unclosed acceptance work.

## Tests

`python tests/run_tests.py --blender "PATH/TO/blender.exe"` runs isolated factory-startup processes, includes real bake/rebuild, disk reopen, rig attachment and collision smoke tests, and writes `tests/results/summary.json`. Pass multiple `--blender` arguments for a version matrix. Failures/timeouts produce a failing runner exit status even when Blender itself exits zero after a script error.

License: GPL-3.0-or-later.
