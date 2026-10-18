# Third review fixes — 2026-10-18

The five reproduced findings are addressed:

- Validate owned wind and turbulence types and wind parenting before freeing a bake, including disabled owned wind.
- Fingerprint the effective requested range and compare it with native cache bounds in state display. Invalid ranges fail dependency validation without raising an operator exception.
- Fingerprint individual unanimated transform channels on objects and pose bones alongside animation curves; timeline evaluation of animated channels is excluded.
- Reject adoption of unequal internal tension/compression stiffness before mutation, because the current panel exposes one combined control. Authored values remain intact.
- Use the collider thickness setting for rigid-body conversion in setup as well as bake.

Regression coverage: `tests/test_third_review.py` exercises each case, including animated rig pose channels and timeline stability. Full runner results are recorded in `tests/results/summary.json`.

These fixes do not certify commercial readiness. Interactive cancellation, Blender 4.2/4.5 installation, and complex collision/performance acceptance remain release gates.
