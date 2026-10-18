# Fourth review fixes and follow-up review — 2026-10-18

## Fixes

- NLA strip mute now participates in cache dependency signatures. The follow-up review expanded coverage to playback settings, track solo state, strip remapping, strip control curves, modifiers, and nested strip configuration. Animated influence/time are represented by their curves so timeline evaluation does not invalidate unchanged inputs.
- Disabled or muted NLA tracks/strips no longer hide edits to authored static transform channels.
- Existing cloth gravity influence is range-checked before adoption mutates any properties. Values outside the panel's 0–1 range produce an actionable rejection and retain the original modifier. Supported values survive adoption and reconfiguration.

## Validation and review scope

`tests/test_fourth_review.py` verifies a real bake becomes dirty after muting a collider's NLA strip; restoring mute restores the fingerprint. It also checks NLA enablement, solo state, action-range edits, timeline stability for animated strip influence, static edits with muted NLA, unchanged data after rejected adoption, and supported gravity round-tripping.

The follow-up source review examined the changed cache serialization and adoption paths. No additional confirmed unresolved defect was found in those changed paths after the expanded fixes. This is a scoped review, not proof of exhaustive dependency coverage. Arbitrary external driver dependencies remain outside the validation guarantee.

The complete suite contains 15 programs, run on Blender 4.1.1 and 5.1.2; see `tests/results/summary.json` for execution results. Interactive cancellation, Blender 4.2/4.5 installation, complex layered/fast-contact collision scenes, and performance acceptance remain release gates.
