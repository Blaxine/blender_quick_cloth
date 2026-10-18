# Quick Cloth

The current add-on source and documentation are in [quick_cloth](quick_cloth/README.md).

Version 1.1.0 is a development validation build. Eight REQ-001 implementation slices address registration, per-garment settings, rigs, collisions, quality, baking and proxy lifecycle. Commercial release acceptance is still pending; see [release status](quick_cloth/docs/RELEASE_STATUS.md).

- [Implementation requirement](quick_cloth/requirements/InProgress/REQ-001-Commercial-Readiness-Fixes.md)
- [Original 56-finding audit](quick_cloth/audit/COMMERCIAL_READINESS_AUDIT.md)
- [Second code-review pass](quick_cloth/docs/SECOND_REVIEW.md)

From the quick_cloth directory, run `python tools/build.py` to create separate extension and legacy archives in `dist/`. Do not use the old single-archive git-archive recipe; the package now contains multiple Python modules.

Run `python tests/run_tests.py --blender "PATH/TO/blender.exe"` for isolated Blender regressions. The test runner supports repeated --blender arguments and writes a versioned results summary.

License: GPL-3.0-or-later.
