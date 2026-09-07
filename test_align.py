"""Self-check for align_to_reference. Run: python3 test_align.py"""
import cv2
import numpy as np

from app import align_to_reference, combined_difference, letterbox

SHIFT = cv2.getRotationMatrix2D((320, 240), 3.0, 1.0)
SHIFT[:, 2] += (18, -11)


def varied_scene(seed=7):
    """Distinctive detail everywhere, the case alignment is meant to handle."""
    rng = np.random.default_rng(seed)
    frame = np.full((480, 640, 3), 30, np.uint8)
    for _ in range(60):
        x, y = int(rng.integers(20, 600)), int(rng.integers(20, 440))
        colour = tuple(int(v) for v in rng.integers(40, 255, 3))
        if rng.random() < 0.5:
            w, h = int(rng.integers(15, 70)), int(rng.integers(15, 70))
            cv2.rectangle(frame, (x, y), (x + w, y + h), colour, -1)
        else:
            cv2.circle(frame, (x, y), int(rng.integers(8, 35)), colour, -1)
        cv2.putText(frame, chr(65 + int(rng.integers(0, 26))), (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    return frame


def repeating_scene():
    """A grid of near-identical cells, as a tray of identical parts would be."""
    frame = np.full((480, 640, 3), 40, np.uint8)
    for row in range(4):
        for col in range(5):
            x, y = 60 + col * 110, 50 + row * 100
            shade = 60 + 40 * ((row + col) % 5)
            cv2.rectangle(frame, (x, y), (x + 70, y + 60), (shade, 255 - shade, shade), -1)
            cv2.circle(frame, (x + 35, y + 30), 14, (255, 255, 255), -1)
    return frame


def test_recovers_a_known_shift():
    ref = varied_scene()
    ref_gray = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    live = cv2.warpAffine(ref, SHIFT, (640, 480))
    live_gray = cv2.cvtColor(live, cv2.COLOR_BGR2GRAY)

    warped, covered = align_to_reference(live, live_gray, ref_gray)
    assert warped is not None, "alignment declined a frame it should have matched"

    mask = covered > 0
    warped_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    aligned = np.abs(warped_gray[mask].astype(int) - ref_gray[mask].astype(int)).mean()
    raw = np.abs(live_gray[mask].astype(int) - ref_gray[mask].astype(int)).mean()
    assert aligned < raw / 10, f"alignment did not help: {aligned:.1f} vs {raw:.1f} unaligned"


def test_declines_a_repeating_pattern():
    """A confident fit one repeat out of place is worse than no fit at all."""
    ref = repeating_scene()
    ref_gray = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    live = cv2.warpAffine(ref, SHIFT, (640, 480))
    live_gray = cv2.cvtColor(live, cv2.COLOR_BGR2GRAY)

    warped, covered = align_to_reference(live, live_gray, ref_gray)
    assert warped is None and covered is None, "ambiguous repeats should not produce a warp"


def test_letterbox_keeps_proportions():
    """A portrait frame must not come out stretched across a landscape canvas."""
    tall = np.zeros((900, 300, 3), np.uint8)
    tall[:, :] = (10, 20, 30)
    cv2.circle(tall, (150, 450), 120, (255, 255, 255), -1)

    out = letterbox(tall, (640, 480))
    assert out.shape == (480, 640, 3)

    # the circle stays a circle: its bounding box is square to within a pixel
    mask = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY) > 200
    rows, cols = np.where(mask)
    height, width = np.ptp(rows) + 1, np.ptp(cols) + 1
    assert abs(height - width) <= 1, f"circle came out {width}x{height}, so it was stretched"

    # and the padding is on the sides, the tall image having been fitted by height
    assert not mask[:, 0].any() and not mask[:, -1].any()


def test_extra_samples_forgive_variation_the_anchor_would_flag():
    """The point of holding several golden samples: a unit that matches any of them passes."""
    anchor = varied_scene()
    variant = varied_scene()
    cv2.circle(variant, (500, 380), 40, (0, 0, 0), -1)   # a part that sits differently

    anchor_gray = cv2.cvtColor(anchor, cv2.COLOR_BGR2GRAY)
    variant_gray = cv2.cvtColor(variant, cv2.COLOR_BGR2GRAY)

    alone, alone_map = combined_difference([anchor_gray], variant_gray)
    together, together_map = combined_difference([anchor_gray, variant_gray], variant_gray)

    assert together > alone, f"a second sample should raise the score: {together} vs {alone}"
    assert together > 0.99, f"a capture matching a held sample should score near 1, got {together}"
    assert (together_map >= alone_map - 1e-9).all(), "an extra sample must never lower a pixel"


def test_one_sample_matches_plain_ssim():
    scene = varied_scene()
    gray = cv2.cvtColor(scene, cv2.COLOR_BGR2GRAY)
    score, diff = combined_difference([gray], gray)
    assert score > 0.999, f"a frame against itself should score 1, got {score}"
    assert diff.shape == gray.shape


def test_gives_up_on_a_blank_frame():
    blank = np.zeros((480, 640, 3), np.uint8)
    warped, covered = align_to_reference(blank, blank[:, :, 0], blank[:, :, 0])
    assert warped is None and covered is None, "a textureless frame should not produce a warp"


if __name__ == "__main__":
    test_recovers_a_known_shift()
    test_declines_a_repeating_pattern()
    test_extra_samples_forgive_variation_the_anchor_would_flag()
    test_one_sample_matches_plain_ssim()
    test_letterbox_keeps_proportions()
    test_gives_up_on_a_blank_frame()
    print("ok")
