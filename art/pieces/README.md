# Pieces checklist: drop finished structures here

**Format:** transparent PNG, exported at **1x** from Figma, one structure per file, with the entrance facing
**down** (south) unless noted. Every piece is scaled to its real footprint automatically. Only the **shape**
(width : height) has to be right; any resolution works.

**Naming:** the file name decides where a piece goes. A type name fills **every** building of that type;
a building's own name fills just that one.

## Phase 1 (current map): Main Building, Rotunda, NAB/Snake Path, the bhawans around it
| File | Fills | Count | Shape (w : h) | Real size |
|---|---|---|---|---|
| `clock tower body.png` + `fd.png` | Main Building (FD3 + tower + FD2) | 1 | done ✅ | 314 × 100 m |
| `rotunda.png` | Rotunda (complete, round, with the steps) | 1 | ~3 : 2 | ~85 × 60 m |
| `bhawan.png` | Ram, Budh, Krishna, Gandhi, Shankar, Vishwakarma, Bhagirath (and later Vyas, Rana Pratap, Ashok) | 7 now, 10 total | **2 : 3** (tall) | ~65 × 98 m |
| `mess.png` | Ram-Budh, KG, VKB messes (later Shankar-Vyas, RP) | 3 now, 5 total | **1 : 1** | ~40 × 38 m |
| `nab.png` | both NAB blocks (mirrored for the second) | 2 | **1 : 6** (long, thin) | ~38 × 245 m |
| `fd1.png` *(optional)* | FD 1 | 1 | ~1 : 1 | ~115 × 105 m |
| `sac.png` *(optional)* | Student Activity Centre | 1 | ~5 : 9 | ~75 × 135 m |

Smaller buildings (wardens' residences, sheds) use a plain placeholder block for now. Add `small_house.png` later
if you want them drawn.

## Later phases
West side (Malviya, Birla Museum), east (Library + LTC, Workshop, Gymkhana, pool), south (Shiv Ganga, Saraswati
Temple, Meera Bhawan, Med-C, C'not), main gate. Same rules: name the file after the building, or after its type
if it repeats.

## If pieces combine into one building
Export each piece separately and add a screenshot of how they fit (like `_figma_layout.png`). Claude matches the
positions and saves them as a layout file, like `main_building_layout.json`.

## Optional: collision
`<file name>_collision.png`, the same size as the piece. Paint where the player must NOT walk; leave everything else
transparent. Without it, the whole building outline blocks except the entrance steps.
