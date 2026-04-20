#!/usr/bin/env python3
"""
Generate GIFs for Clawd — the Claude Code pixel-crab mascot.

Style: 8-bit chunky pixel art, coral-orange body, black square eyes.
Reads/writes nothing from the BLE protocol; just draws the character
at 96px wide with plenty of frames per state.

Run from repo root:
    python3 characters/clawd/src/make_clawd.py

Outputs go in characters/clawd/ (the GIFs that ship to the device).
"""
from __future__ import annotations
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent  # characters/clawd/

# ---------- palette ----------
BG       = (0, 0, 0)            # device background (matches manifest)
BODY     = (217, 115, 76)       # coral-orange — Clawd's signature color
BODY_HI  = (240, 155, 110)      # top-highlight
BODY_LO  = (168, 78, 54)        # bottom shadow
INK      = (22, 14, 14)         # eye/outline ink
CHEEK    = (236, 120, 130)      # blush for heart state
WHITE    = (245, 240, 225)      # sparkles, Zs
STAR_Y   = (255, 210, 90)       # dizzy stars
HEART    = (232, 70, 90)        # hearts

# ---------- canvas ----------
CANVAS_W = 96
CANVAS_H = 96
PIX      = 4      # logical pixel -> real pixel scale
BODY_W   = 18     # logical width of crab body (in PIX units)
BODY_H   = 8      # logical height of crab body

# body origin (logical-pixel coordinates). Centered, slightly-above-center.
BODY_X = (CANVAS_W // PIX - BODY_W) // 2    # = (24-18)/2 = 3
BODY_Y = 5                                   # leaves room below for legs


def new_frame():
    im = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
    return im, ImageDraw.Draw(im)


def px(draw, x, y, color):
    """Paint one logical pixel (PIX x PIX real pixels)."""
    x0, y0 = x * PIX, y * PIX
    draw.rectangle([x0, y0, x0 + PIX - 1, y0 + PIX - 1], fill=color)


def rect(draw, x, y, w, h, color):
    for dy in range(h):
        for dx in range(w):
            px(draw, x + dx, y + dy, color)


def body_shape(draw, bob=0, squish=0, stalk_wiggle=0, claws_up=False):
    """
    Draw the crab body + shading + eye-stalks + claws + legs.
    `bob`          : -1..1   vertical offset (breathing / bouncing)
    `squish`       : 0..2    vertical squash (celebrate)
    `stalk_wiggle` : -1..1   horizontal nudge of the eye-stalks
    `claws_up`     : bool    raise the claws (celebrate pose)
    """
    by = BODY_Y + bob
    bh = BODY_H - squish

    # eye-stalks on top of the head: two vertical nubs with a tip
    stalk_left_x = BODY_X + 4 + stalk_wiggle
    stalk_right_x = BODY_X + BODY_W - 5 + stalk_wiggle
    for sx in (stalk_left_x, stalk_right_x):
        px(draw, sx, by - 2, BODY_HI)
        px(draw, sx, by - 1, BODY)

    # main chunky rounded rectangle, rounded by clipping corners
    for dy in range(bh):
        for dx in range(BODY_W):
            corner = (
                (dx == 0 and dy == 0) or
                (dx == BODY_W - 1 and dy == 0) or
                (dx == 0 and dy == bh - 1) or
                (dx == BODY_W - 1 and dy == bh - 1)
            )
            if corner:
                continue
            c = BODY
            if dy == 0:
                c = BODY_HI
            elif dy >= bh - 1:
                c = BODY_LO
            px(draw, BODY_X + dx, by + dy, c)

    # claws — little pincer arms on each side.
    if claws_up:
        # Arm points up+out; pincer at the top
        # left arm
        px(draw, BODY_X - 1, by + 1, BODY)
        px(draw, BODY_X - 2, by,     BODY)
        px(draw, BODY_X - 3, by - 1, BODY)   # pincer
        px(draw, BODY_X - 2, by - 1, BODY)
        # right arm
        px(draw, BODY_X + BODY_W,     by + 1, BODY)
        px(draw, BODY_X + BODY_W + 1, by,     BODY)
        px(draw, BODY_X + BODY_W + 2, by - 1, BODY)
        px(draw, BODY_X + BODY_W + 1, by - 1, BODY)
    else:
        # Claws resting at body midline
        for dy in range(2):
            px(draw, BODY_X - 1, by + 2 + dy, BODY)
            px(draw, BODY_X + BODY_W, by + 2 + dy, BODY)
        # pincer tips
        px(draw, BODY_X - 2, by + 2, BODY_LO)
        px(draw, BODY_X - 2, by + 3, BODY)
        px(draw, BODY_X + BODY_W + 1, by + 2, BODY_LO)
        px(draw, BODY_X + BODY_W + 1, by + 3, BODY)

    # legs: two pairs of two, with gap in the middle
    leg_y = by + bh
    leg_cols = [2, 4, 13, 15]   # columns within the body
    for lx in leg_cols:
        px(draw, BODY_X + lx, leg_y, BODY_LO)
        px(draw, BODY_X + lx, leg_y + 1, BODY_LO)


# ---------- eye renderers ----------
EYE_L_X = BODY_X + 5
EYE_R_X = BODY_X + 12
EYE_Y   = BODY_Y + 3


def eyes_normal(draw, bob=0, look=0, blink=False):
    """Classic pixel-square eyes. `look` shifts pupils horizontally."""
    y = EYE_Y + bob
    if blink:
        # closed slit
        for x in (EYE_L_X, EYE_R_X):
            px(draw, x, y + 1, INK)
            px(draw, x + 1, y + 1, INK)
        return
    # 2x2 square pupils, optional nudge
    for base in (EYE_L_X, EYE_R_X):
        rect(draw, base + look, y, 2, 2, INK)


def eyes_squint(draw, bob=0):
    """'> <' happy-squint eyes."""
    y = EYE_Y + bob
    # left '>'
    px(draw, EYE_L_X, y,     INK)
    px(draw, EYE_L_X + 1, y + 1, INK)
    px(draw, EYE_L_X, y + 2, INK)
    # right '<'
    px(draw, EYE_R_X + 1, y,     INK)
    px(draw, EYE_R_X, y + 1, INK)
    px(draw, EYE_R_X + 1, y + 2, INK)


def eyes_closed(draw, bob=0):
    """Sleeping: flat horizontal line for each eye."""
    y = EYE_Y + bob + 1
    rect(draw, EYE_L_X, y, 2, 1, INK)
    rect(draw, EYE_R_X, y, 2, 1, INK)


def eyes_x(draw, bob=0):
    """Dizzy X eyes. 3x3 with the four corners + center."""
    y = EYE_Y + bob
    for base in (EYE_L_X - 1, EYE_R_X):
        # X pattern
        px(draw, base,     y,     INK)   # top-left
        px(draw, base + 2, y,     INK)   # top-right
        px(draw, base + 1, y + 1, INK)   # center
        px(draw, base,     y + 2, INK)   # bottom-left
        px(draw, base + 2, y + 2, INK)   # bottom-right


def eyes_focused(draw, bob=0):
    """Busy / debug: smaller stern eyes + a furrow above."""
    y = EYE_Y + bob
    rect(draw, EYE_L_X, y + 1, 2, 1, INK)
    rect(draw, EYE_R_X, y + 1, 2, 1, INK)
    # eyebrow furrow
    px(draw, EYE_L_X, y - 1, INK)
    px(draw, EYE_L_X + 1, y, INK)
    px(draw, EYE_R_X + 1, y - 1, INK)
    px(draw, EYE_R_X, y, INK)


def eyes_alert(draw, bob=0):
    """Attention: wide 3x2 eyes, very open."""
    y = EYE_Y + bob
    rect(draw, EYE_L_X - 1, y, 3, 3, INK)
    rect(draw, EYE_R_X, y, 3, 3, INK)
    # tiny pupil gleam
    px(draw, EYE_L_X, y + 1, BODY_HI)
    px(draw, EYE_R_X + 1, y + 1, BODY_HI)


# ---------- flourish renderers (stuff floating around the crab) ----------
def draw_z(draw, x, y, size=1):
    """Draw a 'Z' glyph at logical-px (x,y). size=1 uses 3x3, size=2 uses 4x4-ish."""
    s = 3 if size == 1 else 4
    # top bar
    for i in range(s):
        px(draw, x + i, y, WHITE)
    # bottom bar
    for i in range(s):
        px(draw, x + i, y + s - 1, WHITE)
    # diagonal
    for i in range(s - 2):
        px(draw, x + s - 2 - i, y + 1 + i, WHITE)


def draw_heart(draw, x, y, color=HEART):
    """5x4 pixel heart."""
    pixels = [
        (0, 0), (1, 0), (3, 0), (4, 0),
        (0, 1), (1, 1), (2, 1), (3, 1), (4, 1),
        (1, 2), (2, 2), (3, 2),
        (2, 3),
    ]
    for dx, dy in pixels:
        px(draw, x + dx, y + dy, color)


def draw_star(draw, x, y, color=STAR_Y):
    pixels = [(1, 0), (0, 1), (1, 1), (2, 1), (1, 2)]
    for dx, dy in pixels:
        px(draw, x + dx, y + dy, color)


def draw_sparkle(draw, x, y, color=WHITE):
    px(draw, x + 1, y, color)
    px(draw, x, y + 1, color)
    px(draw, x + 1, y + 1, color)
    px(draw, x + 2, y + 1, color)
    px(draw, x + 1, y + 2, color)


def draw_sweat(draw, x, y):
    # teardrop at (x,y) logical
    px(draw, x + 1, y, (120, 200, 230))
    px(draw, x, y + 1, (160, 220, 240))
    px(draw, x + 1, y + 1, (200, 235, 250))
    px(draw, x + 2, y + 1, (120, 200, 230))
    px(draw, x + 1, y + 2, (120, 200, 230))


def draw_bang(draw, x, y):
    """Exclamation mark '!' — 1x4 bar + dot."""
    rect(draw, x, y, 1, 3, STAR_Y)
    px(draw, x, y + 4, STAR_Y)


def draw_question(draw, x, y):
    """5x6 '?' glyph."""
    pixels = [
        (1, 0), (2, 0), (3, 0),
        (0, 1), (4, 1),
        (3, 2), (4, 2),
        (2, 3),
        (2, 5),
    ]
    for dx, dy in pixels:
        px(draw, x + dx, y + dy, STAR_Y)


def draw_note(draw, x, y):
    """Music note '♪'."""
    rect(draw, x + 2, y, 1, 4, WHITE)
    px(draw, x + 3, y, WHITE)
    px(draw, x + 3, y + 1, WHITE)
    rect(draw, x, y + 3, 2, 2, WHITE)


# ---------- GIF writing ----------
def write_gif(path: Path, frames: list[Image.Image], durations):
    if isinstance(durations, int):
        durations = [durations] * len(frames)
    palettized = [f.convert("P", palette=Image.ADAPTIVE, colors=64) for f in frames]
    palettized[0].save(
        path,
        save_all=True,
        append_images=palettized[1:],
        duration=durations,
        loop=0,
        optimize=False,
        disposal=2,
    )
    return path.stat().st_size


# ---------- state builders ----------
def frame_sleep(t, total):
    im, d = new_frame()
    # slow breathing: bob down 1 px for half the cycle
    bob = 1 if t >= total // 2 else 0
    body_shape(d, bob=bob)
    eyes_closed(d, bob=bob)
    # two Zs drifting up
    progress = t / total
    zx = BODY_X + BODY_W + 1
    zy = BODY_Y - 1 - int(progress * 4)
    draw_z(d, zx, zy, size=1)
    zy2 = BODY_Y - 3 - int(((t + total // 2) % total) / total * 4)
    draw_z(d, zx + 2, zy2, size=1)
    return im


def frame_idle_blink(t, total):
    im, d = new_frame()
    bob = 0 if t < total - 2 else 0
    body_shape(d)
    blink = t >= total - 2
    eyes_normal(d, blink=blink)
    return im


def frame_idle_look_left(t, total):
    im, d = new_frame()
    # stalks lean with the gaze
    wig = 0 if t < total // 2 else -1
    body_shape(d, stalk_wiggle=wig)
    eyes_normal(d, look=wig)
    return im


def frame_idle_look_right(t, total):
    im, d = new_frame()
    wig = 0 if t < total // 2 else 1
    body_shape(d, stalk_wiggle=wig)
    eyes_normal(d, look=wig)
    return im


def frame_idle_hum(t, total):
    """Idle variant: humming a tune with floating music note."""
    im, d = new_frame()
    body_shape(d)
    eyes_squint(d)
    # bouncing note
    off = [0, -1, 0, 1][t % 4]
    draw_note(d, BODY_X + BODY_W + 2, BODY_Y - 1 + off)
    return im


def frame_idle_wiggle(t, total):
    """Body subtly bobs up and down."""
    im, d = new_frame()
    bob = [0, 0, -1, -1, 0, 0, 1, 1][t % 8]
    body_shape(d, bob=bob)
    eyes_normal(d, bob=bob)
    return im


def frame_idle_sparkle(t, total):
    im, d = new_frame()
    body_shape(d)
    eyes_normal(d)
    if t % 6 < 3:
        draw_sparkle(d, BODY_X - 3, BODY_Y + 1)
    if (t + 3) % 6 < 3:
        draw_sparkle(d, BODY_X + BODY_W + 2, BODY_Y + 5)
    return im


def frame_busy(t, total):
    """Working hard: focused eyes, sweat drop animates."""
    im, d = new_frame()
    # slight bounce to imply typing
    bob = [0, -1][t % 2]
    body_shape(d, bob=bob)
    eyes_focused(d, bob=bob)
    # sweat drop cycles top-to-bottom
    phase = t % 6
    sy = BODY_Y - 1 + phase
    draw_sweat(d, BODY_X - 3, sy)
    # tiny '*' spark on the other side
    if t % 4 < 2:
        px(d, BODY_X + BODY_W + 2, BODY_Y + 1, WHITE)
    return im


def frame_attention(t, total):
    """Alert: wide eyes + alternating ! and ?."""
    im, d = new_frame()
    body_shape(d)
    eyes_alert(d)
    # alternating glyphs above the crab
    glyph_above_y = BODY_Y - 5
    if t % 4 < 2:
        draw_bang(d, BODY_X + BODY_W // 2 - 1, glyph_above_y)
    else:
        draw_question(d, BODY_X + BODY_W // 2 - 2, glyph_above_y)
    return im


def frame_celebrate(t, total):
    """Dancing crab: bob, squish, wave claws, party around him."""
    im, d = new_frame()
    bob_seq    = [0, -2, -3, -2, 0, 1, 0, -2]
    squish_seq = [0, 1, 2, 1, 0, 0, 0, 1]
    bob = bob_seq[t % 8]
    squish = squish_seq[t % 8]
    # claws go up on the peak of each hop, stalks wiggle side-to-side
    claws_up = bob <= -2
    wig = [-1, 0, 1, 0][t % 4]
    body_shape(d, bob=bob, squish=squish, stalk_wiggle=wig, claws_up=claws_up)
    eyes_squint(d, bob=bob)

    # confetti — stable pseudo-random positions, color rotates per frame
    random.seed(42)
    pts = []
    for _ in range(8):
        cx = random.randint(0, CANVAS_W // PIX - 3)
        cy = random.randint(0, BODY_Y - 2)
        pts.append((cx, cy))
    for i, (cx, cy) in enumerate(pts):
        phase = (t + i) % 4
        if phase == 0:
            draw_star(d, cx, cy)
        elif phase == 1:
            draw_sparkle(d, cx, cy)
        elif phase == 2:
            draw_heart(d, cx, cy, color=STAR_Y)
        # phase 3: off (flash)
    return im


def frame_dizzy(t, total):
    """Spiral eyes + orbiting stars."""
    im, d = new_frame()
    # wobble
    tilt = [0, -1, 0, 1][t % 4]
    body_shape(d, bob=tilt)
    eyes_x(d, bob=tilt)

    # orbit
    cx, cy = BODY_X + BODY_W // 2, BODY_Y + 1
    for i in range(3):
        angle = (t * 45 + i * 120) * math.pi / 180
        ox = int(round(math.cos(angle) * 7))
        oy = int(round(math.sin(angle) * 3))
        draw_star(d, cx + ox, cy + oy)
    return im


def frame_heart(t, total):
    """Approved quickly: squint eyes + rising hearts."""
    im, d = new_frame()
    bob = [0, -1][t % 2]
    body_shape(d, bob=bob)
    eyes_squint(d, bob=bob)

    # cheek blush
    px(d, EYE_L_X - 1, EYE_Y + bob + 2, CHEEK)
    px(d, EYE_R_X + 2, EYE_Y + bob + 2, CHEEK)

    # two hearts drifting up on either side
    cycle = total
    rise = (t % cycle) / cycle
    h_y_left = BODY_Y - 1 - int(rise * 5)
    h_y_right = BODY_Y - 1 - int(((t + cycle // 2) % cycle) / cycle * 5)
    draw_heart(d, BODY_X - 4, h_y_left)
    draw_heart(d, BODY_X + BODY_W + 1, h_y_right)
    return im


# ---------- state table ----------
STATES = {
    "sleep":      (frame_sleep,      16, 120),
    "idle_0":     (frame_idle_blink, 14, 180),
    "idle_1":     (frame_idle_look_left,  12, 200),
    "idle_2":     (frame_idle_look_right, 12, 200),
    "idle_3":     (frame_idle_hum,   12, 180),
    "idle_4":     (frame_idle_wiggle, 16, 150),
    "idle_5":     (frame_idle_sparkle, 12, 180),
    "busy":       (frame_busy,       12, 120),
    "attention":  (frame_attention,  12, 140),
    "celebrate":  (frame_celebrate,  16, 100),
    "dizzy":      (frame_dizzy,      16, 110),
    "heart":      (frame_heart,      16, 130),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    for name, (builder, n, dur) in STATES.items():
        frames = [builder(t, n) for t in range(n)]
        path = OUT / f"{name}.gif"
        size = write_gif(path, frames, dur)
        total_bytes += size
        print(f"  {name:12s}  frames={n:<3} dur={dur:<4} -> {size:>7,}b  {path}")
    print(f"\nwrote {len(STATES)} gifs, {total_bytes:,} bytes total")


if __name__ == "__main__":
    main()
