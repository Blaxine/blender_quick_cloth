# Continued review — stack ordering and cache adoption

## Confirmed findings fixed

| Priority | Finding | Fix and regression |
|---|---|---|
| P1 | A Cloth → Build → Armature stack passed preflight because validation stopped at Cloth. Setup/bake then moved Cloth below Armature, putting unsupported changing topology before simulation. Rebuild could discard the good cache before discovering the unsafe configuration. | Validate a temporary list representing the final modifier order without mutating the actual stack. The regression attempts rebuilding a real bake and verifies rejection preserves both modifier order and the baked cache. |
| P2 | Adoption copied native frame bounds but inherited scene preview-range mode and omitted the native disk-cache preference. Subsequent setup could use different bounds or disable disk caching. | Copy native disk-cache mode and explicitly select the adopted native frame range. The regression saves a temporary blend, adopts disk-cached cloth with frames 5–8 while preview frames are 1–2, and checks setup retains disk caching and 5–8. |

A suspected multiple-Cloth ambiguity was disproved: Blender rejects creation of a second Cloth modifier. No redundant restriction was retained.

The follow-up review inspected the final simulated modifier order, mutation timing, and cache adoption behavior. No additional confirmed issue was found in these changed paths. This does not establish exhaustive add-on correctness. Interactive cancellation, complex collision shots, Blender 4.2/4.5 installation, and performance acceptance remain open release gates.

Verification is recorded in `tests/results/summary.json`; `tests/test_fifth_review.py` contains the targeted regressions.
