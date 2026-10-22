# Quick Cloth 1.1.0 validation-build status

Updated: 2026-10-18. Eight implementation slices are delivered as separate commits. This is a development validation build, **not a commercial release approval**.

## Implemented and exercised

- Registration and failed-registration rollback.
- Per-garment settings, explicit live-settings adoption, stable canonical identity and duplicate isolation.
- Rig stack ordering, explicit attachment editing, geometry validation, and shared-data guards.
- Collider preservation, collision enablement, owned wind/turbulence and corrected new-preset shrink signs.
- Preview/Medium/High/Custom, authored Custom restoration and shared numerical resolver.
- Exact ranges, explicit rebuild, bake result/state checks, disk validation and save/reopen.
- Rename-safe cages, deletion recovery, refreshed cage geometry and non-rendering helpers.
- Owned proxy Bind/Rebind/Unbind, static snapshots, allowlisted packaging and versioned test runner.

Automated evidence is in `tests/results/summary.json` in the source repository. Tests use Blender 4.1.1 and 5.1.2 in disposable factory-startup processes, and actual source without audit patches. Small numerical fixtures include an unrigged cloth drop onto a collider and a rig-driven attachment. Full visual acceptance is a separate gate.

Slice run: **26/26 test executions passed** (13 programs on each version). Extension manifest validation also passed on 5.1.2. Later review fixes raised the suite to 18 programs; the latest run passed 36/36 on Blender 4.5.4 LTS and 5.2.2 LTS (see `docs/SEVENTH_REVIEW_FIXES.md`). Archive tests validate layout and extracted-code registration, not an interactive installation workflow.

## Finding dispositions

The original findings remain documented in `audit/COMMERCIAL_READINESS_AUDIT.md` in the source repository. “Implemented” means the code path changed; it does not claim every conceivable scene was certified.

| Findings | Disposition / evidence |
|---|---|
| F01 | Fixed; registration and operator-ID tests |
| F02–F04 | Per-object data and shared Bake resolver; ownership/quality tests. User UI locks while baking; external scripts remain responsible for not mutating native jobs |
| F05–F06 | Fabric scope documented, corrected new-preset shrink, existing values preserved or lossy adoption rejected |
| F07–F09 | Explicit adoption, pointer/registry ownership, owned wind cleanup; cross-scene shared garments rejected for independent simulation |
| F10 | Transactional registration with injected-failure regression |
| F11 | Legacy/extension archives supplied; 4.1/5.1 runtime tests. 4.2/4.5 and interactive install matrix still pending |
| F12 | Cloth moved after last Armature; automated multi-armature order check |
| F13–F15 | Coverage warnings, explicit groups, native 0–50 stiffness; one vertex-group rig required for automatic pins |
| F16–F17 | Basic rig/unrigged numerical fixtures and Dynamic Rest Shape control; advanced NLA/constraint/squash-stretch fixture acceptance pending |
| F18–F20 | Geometry, singular transform and unsupported upstream topology checks; unusual scale/topology validation remains shot-dependent |
| F21–F23 | Shared pin-data edits blocked, BMesh mode-preserving edits, editable-override checks; linked-library integration matrix pending |
| F24–F27 | Explicit collision enablement, body selection, preserved collider defaults, body stack diagnostic; real static-collider fixture passes |
| F28 | Authored clamp/thickness controls; no universal stability claim. Physical tuning and scale benchmark pending |
| F29 | Self-collision preserved across all quality tiers |
| F30–F31 | Current-pose cloth/body overlap diagnostic; full-shot crossing, teleport, self-intersection and layered-contact acceptance pending |
| F32 | Existing collision filters preserved, enabled scene collider count visible; comprehensive view-layer/filter diagnostics still limited |
| F33–F35 | Owned fields use native creation, disabling zeros strength, removal remains accessible; constrained owned winds rejected |
| F36–F38 | Exact ranges; negative pre-roll rejected with remedy; default settle is 0, no silent retiming |
| F39–F41 | Verified invalidation, completion checks, deep execute preflight; real bake/rebuild and injected invalidation failure tests |
| F42 | Conservative dependency snapshots and Needs Validation on evaluation/reload; scripted external inputs are not fully knowable |
| F43 | Native disk path/write/space checks and actual save/reopen regression; imported/external caches deliberately unsupported |
| F44–F45 | State UI, native job/Escape integration and guarded rebuild. Interactive cancellation, full-disk/process-interruption and concurrency fault matrix pending |
| F46–F49 | Explicit Animator state, hidden render helper, pointer pairing, rebuild on entry; rename/deletion/edit regression |
| F50 | Honest cloth-off stand-in scope; after-deformation decimation remains. Measured low-poly rig optimization is not claimed |
| F51 | Snapshot/restore changed visibility, recover hidden garment; complex view-layer and undo matrix pending |
| F52–F53 | Explicit owned binding and cycle checks; rig/cloth must live on proxy, not render mesh. Actual bind/rebind/unbind regression |
| F54 | Static evaluated snapshot naming and object-linked material copy; extensive appearance fixture review pending |
| F55–F56 | Tests, allowlisted packaging, documentation and honest support boundaries; peak memory, long-shot benchmarks and final reference videos pending |

## Remaining commercial release gates

- [ ] Interactive panel, progress, Escape cancellation, undo/redo and multi-window acceptance on a saved production-like scene.
- [ ] Actual supported extension installation and simulation tests on 4.2/4.5; current `blender_version_min` is a target, not evidence of testing those binaries.
- [ ] Approved reference shots for nine fabrics, rigged cape/skirt/shirt, fast/thin and deforming colliders, layered self-collision and pressure/sewing.
- [ ] Collision acceptance measurements over complete shots, beyond the small static floor/attachment fixtures. The proposed 2 mm human-scale tolerance is not universally certified.
- [ ] Benchmark wall time and peak memory for stated garment sizes, many colliders, long shots and repeated lifecycle use.
- [ ] Fault recovery under full/read-only/disconnected storage and interrupted native jobs; linked override and complex view-layer matrix.
- [ ] Final documented review of all P0/P1 acceptance items before sale/publication.

Do not mark REQ-001 complete or advertise guaranteed collision quality while these gates are open.
