# Seventh review fixes — reload-stable signatures and cage Simulate

| Finding | Fix | Regression evidence |
|---|---|---|
| Cache signatures changed after every save/reopen when scene or object custom properties held groups or arrays, including other add-ons' registered settings such as Cycles. Their string form embeds a memory address, so Validate Cache Dependencies always reported a mismatch in real project files. | Serialize custom properties as plain values: groups as dictionaries, arrays as lists, ID references by full name. | A real bake with touched Cycles settings, a nested scene group, an object array and an ID reference validates as Baked after save/reopen. Editing the nested value or retargeting the reference still changes the signature; restoring them restores it. |
| Simulate on the Animator Mode cage registered a new setup identity on the cage before refusing. | Reject cages, override-locked objects and active Animator Mode before initializing the setup. | Simulate on the cage is refused with the cage message; the cage identity, scene registry and cage modifiers are unchanged. |

Tests are in `tests/test_seventh_review.py`. Both checks fail on the previous code. Full regression results on Blender 4.5.4 LTS and 5.2.2 LTS are recorded in `tests/results/summary.json`; 4.1.1 and 5.1.2 were not rerun for these fixes (their last results are in commit `4035978`).

Bakes recorded with the previous serializer may need one validation or rebuild if their signature included affected custom properties. These fixes do not close the interactive extension installation, collision, performance or storage-failure gates.
