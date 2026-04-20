# clawd

Clawd is the pixel-crab mascot of Claude Code — an 8-bit coral-orange
crustacean with eye-stalks, tiny claws, and a lot of opinions. He first
showed up in a Claude Artifacts demo video, then took on a life of his own
across the community (desktop pets, physical companions, terminal
status-lines, etc.).

This is a fresh sprite drawn for a 96×96 canvas, not a recycled asset pack.
It's included here as another example character — fourteen GIFs and a
manifest mapping them to the seven states.

## States

| State       | What he's doing                                          |
| ----------- | -------------------------------------------------------- |
| `sleep`     | eyes shut, breathing, Zs drifting up                     |
| `idle`      | six variants: blink, glance L, glance R, hum, wiggle, sparkle |
| `busy`      | focused brow, sweat drop trickling down                  |
| `attention` | wide eyes, alternating **!** and **?** above the head    |
| `celebrate` | dancing: hop-squish, claws up, confetti all around       |
| `dizzy`     | X eyes, three stars orbiting                             |
| `heart`     | squinty `> <` eyes, blush, floating hearts               |

The idle state has six variants so the home screen rotates through different
beats instead of looping one clip.

## Install

Drag this folder onto the Hardware Buddy window, or flash over USB:

```bash
python3 tools/flash_character.py characters/clawd
```

## Regenerating

The GIFs are generated from `src/make_clawd.py`. To tweak the design
(colors, frame counts, new idle variants), edit that script and re-run:

```bash
python3 characters/clawd/src/make_clawd.py
```
