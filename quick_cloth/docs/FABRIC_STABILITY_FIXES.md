# Fabric stability fixes — jittery leather and exploding self-collision

Measured in Blender 5.2.2 LTS, Medium quality, on three test scenes:

- **Panel:** a 1 × 1.2 m pinned panel with 2 cm edges swung past a cylinder.
- **Drape:** a 1.6 m throw with 2 cm edges dropped on a seat.
- **Cushion:** a closed 60 × 60 × 15 cm cushion with 1 cm side edges resting on the floor.

"Late motion" is the mean vertex speed over the last 15 frames, when nothing drives the cloth. "Flips" is the share of moving vertex-frames that reverse direction, which is how jitter shows up.

| Finding | Fix | Evidence |
|---|---|---|
| **Couch Leather jittered and never came to rest.** The flip rate was 0.44–0.81 in all three scenes, with about 2 mm/frame of late motion on the cushion. Bend damping of 15 against 0.85 kg mass makes the solver overshoot every step. Turning internal springs off did not change it, and neither did High quality. | Bend damping 15 → 4. Bend damping 1, 2 and 4 all measured still. | Flips are now 0.00–0.08. The cushion's late motion is 0.003 mm/frame. |
| **Leather Coat blew up.** On the panel, edges stretched 2.5× and the cloth bunched upward (late 16 mm/frame). On the drape it fell through the floor (157 mm/frame). The cushion exploded at 6× stretch. The cause is self-collision: a 12 mm gap on meshes with 1–2 cm edges, and gaps of half the edge length or more do this to every fabric, including Simple. With self-collision off, the coat still jittered (flips 0.53–0.81) from bend damping 8. | Bend damping 8 → 2. Gap to Itself 12 → 5 mm. | Panel: 0.48 mm/frame, stretch 1.06. Drape: 1.06 mm/frame, resting on the seat. Cushion: 0.05 mm/frame. |
| **Cotton exploded the same way** (5× stretch on the cushion), and every other self-colliding preset used a 10–12 mm gap. | Cotton, Polyester and all three denims now use 5 mm, Latex uses 4 mm. Simple and the property default stay at 15 mm because self-collision is off for them. | No case exploded across the 27 runs. |
| **Nothing tied the gap to the mesh.** A gap that works on 2 cm edges is too large on 1 cm edges. | Set Up and Bake measure the mesh's short edges (5th percentile, world scale). Above 0.45× the short edge they refuse, and the message names the safe value. Above ⅓ they warn. Collisions shows the problem and a **Use Safe Gap** button, which sets ¼ of the short edge. | The cushion refuses 12 mm and warns at 4 mm. Use Safe Gap sets 2.5 mm, and both leather presets then settle (`tests/test_fabric_stability.py`). |

The ratios come from sweeps of the self-collision gap:

| Mesh | Gap / short edge | Result |
|---|---|---|
| Panel or drape, 2 cm edges | 0.25 | stable |
| Panel or drape, 2 cm edges | 0.5 | stretched and kept bunching |
| Cushion, 1 cm edges | 0.25 | stable |
| Cushion, 1 cm edges | 0.5 | stable |
| Cushion, 1 cm edges | 1.0 or more | exploded |

This is audit finding F31 for the self-distance part only. Overlapping layers, co-located seam vertices and doubled surfaces are still unchecked.

Files saved with the old presets keep their stored slider values. To get the new ones, re-pick the fabric or press Use Safe Gap. If an old file has a self-colliding gap that is too large for its mesh, its next Set Up or Bake is now refused with the fix in the message. Existing bakes are not touched.
