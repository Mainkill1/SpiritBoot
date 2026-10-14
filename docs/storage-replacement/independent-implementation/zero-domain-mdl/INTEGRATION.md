# Integration tree guard

The first 0133 CI build reproduced release64 ROM `c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853`, then stopped before host checks because the workflow still required the previous 146-patch source tree. Root independently applied only 0133 to that exact tree using an isolated Git index; resulting tree `8231cceb5e3ecd578499fa0d2fbf421f0143642c` matches the actual CI build receipt. The workflow pin is updated to that exact 147-patch tree. The historical baseline receipt and native frozen inputs retain their original identity.
