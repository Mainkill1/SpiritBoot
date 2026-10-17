# Integration tree guard

The first 0133 CI build reproduced release64 ROM `c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853`, then stopped before host checks because the workflow still required the previous 146-patch source tree. Root independently applied only 0133 to that exact tree using an isolated Git index; resulting tree `8231cceb5e3ecd578499fa0d2fbf421f0143642c` matches the actual CI build receipt. The workflow pin is updated to that exact 147-patch tree. The historical baseline receipt and native frozen inputs retain their original identity.

The upper-reservation profile had a second source-tree assertion, corrected to the same independently verified tree. Its actual CI receipt still reproduces reserved128 ROM `2632d513d84bf165d3a916b135cc387af6ee414b9f4bfbef334163752f022836`. Both identity checks remain strict.
