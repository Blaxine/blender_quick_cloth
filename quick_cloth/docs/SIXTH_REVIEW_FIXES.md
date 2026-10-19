# Sixth review fixes — pin weights and cache dependencies

| Finding | Fix | Regression evidence |
|---|---|---|
| Automatic pin generation overwrote deform-bone weights when the attachment destination was a bone group. | Reject rig bone groups as destinations with an actionable message before any mutation. Users can clear the attachment field to create a separate group. | Bone weights 0.2 and 0.5 remain intact after rejection; creating a separate attachment produces 0.7 without changing either source. |
| Automatic pin generation removed existing pins before reporting that no source bone weights existed. | Compute and validate the complete weight set before creating groups or writing weights. | Failed generation retains existing pins, group count, and attachment selection. Successful regeneration removes obsolete pins and applies valid new weights. |
| Parent-inverse changes could move a collider while dependency validation still matched. | Fingerprint the parent-inverse matrix, parent type, bone target, and vertex-parent indices. | A real bake becomes dirty after changing a collider parent-inverse translation by 10 units; restoring the matrix restores the signature. |
| Driver target axis/space/bone settings were omitted from cache signatures. | Serialize target RNA configuration; also include driver mute and self-reference settings. Exclude evaluated fallback status. | A real bake becomes dirty when switching a collider driver from LOC_X to LOC_Y (position 2 to 7). Transform-space and bone-target edits also change the signature. |

Tests are in `tests/test_sixth_review.py`. Full regression results on Blender 4.1.1 and 5.1.2 are recorded in `tests/results/summary.json`.

Expanded signatures require validation/rebaking of caches recorded with older signatures. These fixes do not close the remaining interactive cancellation, complex collision, performance, or Blender 4.2/4.5 acceptance gates.
