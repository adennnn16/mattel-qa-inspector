import hashlib
import sqlite3
from pathlib import Path

import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
import streamlit as st

# --- SECURITY CONFIGURATION: IP WHITELIST ONLY ---
ALLOWED_IPS = [
    "10.12.142.25",  # Satu-satunya IP yang diizinkan
]


def get_remote_ip():
    """Mendapatkan IP Address pengunjung dari HTTP Header Streamlit."""
    headers = st.context.headers
    # Memeriksa header jika aplikasi berjalan di balik proxy/firewall
    if "X-Forwarded-For" in headers:
        return headers["X-Forwarded-For"].split(",")[0].strip()
    return headers.get("Remote-Addr", "111.94.235.200")


# --- SESSION STATE FOR SECURITY & AUTHENTICATION ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False


# Custom Styling & Security Protocol Injection
CSS_THEME = """
    <style>
    /* Security: Block text selection & right click context menu */
    body {
        -webkit-user-select: none;
        -moz-user-select: none;
        -ms-user-select: none;
        user-select: none;
    }

    .stApp {
        background-color: #FFF0F5;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    .mattel-header {
        background: linear-gradient(135deg, #FF1493 0%, #FF007F 100%);
        padding: 18px 24px;
        border-radius: 16px;
        color: #FFFFFF;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(255, 20, 147, 0.25);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .mattel-sub {
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: #FFB6C1;
        margin: 0;
    }
    
    .mattel-title {
        font-size: 20px;
        font-weight: 800;
        margin: 0;
    }
    
    .barbie-badge {
        background-color: rgba(255, 255, 255, 0.2);
        padding: 4px 12px;
        border-radius: 8px;
        font-style: italic;
        font-weight: 700;
        font-size: 16px;
        border: 1px solid rgba(255, 255, 255, 0.3);
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 480px;
    }

    div.stButton > button:first-child {
        background: linear-gradient(90deg, #FF1493 0%, #E60067 100%);
        color: #FFFFFF;
        font-weight: 700;
        font-size: 15px;
        border-radius: 12px;
        border: none;
        padding: 12px 24px;
        box-shadow: 0 4px 10px rgba(255, 20, 147, 0.3);
        width: 100%;
    }

    [data-testid="stCameraInput"] {
        border: 3px solid #FF1493;
        border-radius: 16px;
        overflow: hidden;
    }

    .ui-heading {
        text-align: center;
        color: #D81B60;
        font-weight: 700;
        margin-top: 12px;
        margin-bottom: 4px;
    }
    
    .ui-subtext {
        text-align: center;
        color: #FF69B4;
        font-size: 12px;
        margin-bottom: 16px;
    }

    /* Dynamic Watermark Styling */
    .watermark {
        position: fixed;
        bottom: 10px;
        right: 10px;
        opacity: 0.35;
        font-size: 11px;
        color: #D81B60;
        font-weight: bold;
        pointer-events: none;
        z-index: 9999;
        text-align: right;
    }

    /* Access Card UI */
    .login-card {
        background-color: #FFFFFF;
        padding: 30px;
        border-radius: 20px;
        box-shadow: 0 8px 16px rgba(255, 20, 147, 0.2);
        border: 2px solid #FF1493;
        max-width: 400px;
        margin: auto;
        text-align: center;
    }
    </style>

    <!-- Security Script: Auto-blur on Tab Switch / Screen Snapping -->
    <script>
    window.addEventListener('blur', function() {
        document.body.style.filter = 'blur(15px)';
    });
    window.addEventListener('focus', function() {
        document.body.style.filter = 'none';
    });
    </script>
"""

HEADER_HTML = """
    <div class="mattel-header">
        <div>
            <p class="mattel-sub">MATTEL INTERNAL</p>
            <h1 class="mattel-title">Packaging Inspector</h1>
        </div>
        <div class="barbie-badge">Barbie</div>
    </div>
"""

BLUR_KERNEL = (5, 5)

DB_PATH = Path("inspections.db")
CAPTURE_DIR = Path("captures")
REFERENCE_DIR = Path("references")

SCHEMA = """
CREATE TABLE IF NOT EXISTS inspection (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    inspected_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    verdict       TEXT    NOT NULL DEFAULT 'UNKNOWN',
    similarity    REAL    NOT NULL DEFAULT 0,
    defects       INTEGER NOT NULL DEFAULT 0,
    aligned       INTEGER NOT NULL DEFAULT 0,
    threshold     INTEGER NOT NULL DEFAULT 0,
    min_area      INTEGER NOT NULL DEFAULT 0,
    capture       TEXT    NOT NULL DEFAULT ''
)
"""

REFERENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS reference (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    sku       TEXT NOT NULL DEFAULT '',
    digest    TEXT NOT NULL DEFAULT '',
    path      TEXT NOT NULL DEFAULT '',
    added_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (sku, digest)
)
"""

ZONE_SCHEMA = """
CREATE TABLE IF NOT EXISTS zone (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    reference  TEXT    NOT NULL DEFAULT '',
    name       TEXT    NOT NULL DEFAULT '',
    x          INTEGER NOT NULL DEFAULT 0,
    y          INTEGER NOT NULL DEFAULT 0,
    w          INTEGER NOT NULL DEFAULT 0,
    h          INTEGER NOT NULL DEFAULT 0,
    UNIQUE (reference, name)
)
"""


def check_authentication():
    """Restricted screen: Only IP Whitelist validation."""
    client_ip = get_remote_ip()

    # Pengecekan IP Whitelist
    if client_ip not in ALLOWED_IPS:
        st.session_state["authenticated"] = False
        st.markdown(CSS_THEME, unsafe_allow_html=True)
        st.markdown("<div class='login-card'>", unsafe_allow_html=True)
        st.markdown(
            "<h2 style='color: #D81B60; margin-bottom: 0;'>⛔ Access Denied</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<p style='color: #FF1493; font-weight: bold; font-size: 13px; margin-top: 10px;'>IP Address Unrecognized ({client_ip})</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='color: #666; font-size: 12px;'>Aplikasi ini hanya dapat diakses melalui jaringan resmi Mattel (IP Whitelist).</p>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return False

    # Jika IP valid, izinkan akses langsung
    st.session_state["authenticated"] = True
    return True


def connect():
    """Open the database, creating and migrating it as needed."""
    db = sqlite3.connect(DB_PATH)
    with db:
        db.execute(SCHEMA)
        db.execute(ZONE_SCHEMA)
        db.execute(REFERENCE_SCHEMA)
        widen_reference_table(db)
        existing = {
            row[1] for row in db.execute("PRAGMA table_info(inspection)")
        }
        for column, spec in (
            ("regions", "TEXT NOT NULL DEFAULT ''"),
            ("sku", "TEXT NOT NULL DEFAULT ''"),
        ):
            if column not in existing:
                db.execute(f"ALTER TABLE inspection ADD COLUMN {column} {spec}")
    return db


def widen_reference_table(db):
    columns = {row[1] for row in db.execute("PRAGMA table_info(reference)")}
    if "id" in columns:
        return
    db.execute("ALTER TABLE reference RENAME TO reference_single")
    db.execute(REFERENCE_SCHEMA)
    db.execute(
        "INSERT INTO reference (sku, digest, path, added_at)"
        " SELECT sku, digest, path, added_at FROM reference_single"
    )
    db.execute("DROP TABLE reference_single")


def save_reference(sku, data, suffix):
    REFERENCE_DIR.mkdir(exist_ok=True)
    digest = hashlib.sha256(data).hexdigest()
    path = REFERENCE_DIR / f"{sku}-{digest[:12]}{suffix}"
    path.write_bytes(data)

    db = connect()
    with db:
        db.execute(
            "INSERT INTO reference (sku, digest, path) VALUES (?, ?, ?)"
            " ON CONFLICT (sku, digest) DO UPDATE SET path=excluded.path",
            (sku, digest, str(path)),
        )
    db.close()


def references_for(sku):
    db = connect()
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT id, sku, digest, path FROM reference WHERE sku = ? ORDER BY id",
        (sku,),
    ).fetchall()
    db.close()
    return [dict(row) for row in rows]


def delete_reference(reference_id):
    db = connect()
    with db:
        db.execute("DELETE FROM reference WHERE id = ?", (reference_id,))
    db.close()


def known_skus():
    db = connect()
    rows = db.execute(
        "SELECT DISTINCT sku FROM reference ORDER BY sku"
    ).fetchall()
    db.close()
    return [row[0] for row in rows]


def save_zone(reference, name, x, y, w, h):
    db = connect()
    with db:
        db.execute(
            "INSERT INTO zone (reference, name, x, y, w, h) VALUES (?, ?, ?, ?, ?, ?)"
            " ON CONFLICT (reference, name) DO UPDATE SET x=excluded.x, y=excluded.y,"
            " w=excluded.w, h=excluded.h",
            (reference, name, x, y, w, h),
        )
    db.close()


def zones_for(reference):
    db = connect()
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT id, name, x, y, w, h FROM zone WHERE reference = ? ORDER BY name",
        (reference,),
    ).fetchall()
    db.close()
    return [dict(row) for row in rows]


def delete_zone(zone_id):
    db = connect()
    with db:
        db.execute("DELETE FROM zone WHERE id = ?", (zone_id,))
    db.close()


def zone_for_box(zones, box):
    x, y, w, h = box
    best, best_area = None, 0
    for zone in zones:
        overlap_w = min(x + w, zone["x"] + zone["w"]) - max(x, zone["x"])
        overlap_h = min(y + h, zone["y"] + zone["h"]) - max(y, zone["y"])
        area = max(0, overlap_w) * max(0, overlap_h)
        if area > best_area:
            best, best_area = zone["name"], area
    return best


def draw_zones(img, zones):
    out = img.copy()
    for zone in zones:
        cv2.rectangle(
            out,
            (zone["x"], zone["y"]),
            (zone["x"] + zone["w"], zone["y"] + zone["h"]),
            (255, 200, 0),
            1,
        )
        cv2.putText(
            out,
            zone["name"],
            (zone["x"] + 2, zone["y"] + 14),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (255, 200, 0),
            1,
        )
    return out


def log_inspection(
    digest,
    capture_bytes,
    suffix,
    verdict,
    similarity,
    defects,
    aligned,
    threshold,
    min_area,
    regions="",
    sku="",
):
    CAPTURES_DIR = CAPTURE_DIR
    CAPTURES_DIR.mkdir(exist_ok=True)
    capture = CAPTURES_DIR / f"{digest[:16]}{suffix}"
    capture.write_bytes(capture_bytes)

    db = connect()
    with db:
        db.execute(
            "INSERT INTO inspection"
            " (sku, verdict, similarity, defects, aligned, threshold, min_area, capture, regions)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sku,
                verdict,
                similarity,
                defects,
                int(aligned),
                threshold,
                min_area,
                str(capture),
                regions,
            ),
        )
    db.close()


def recent_inspections(limit=10):
    db = connect()
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT inspected_at, sku, verdict, similarity, defects, regions, aligned, capture"
        " FROM inspection ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    db.close()
    return [dict(row) for row in rows]


def combined_difference(reference_grays, live_gray):
    best = None
    for reference_gray in reference_grays:
        _, diff = ssim(reference_gray, live_gray, full=True)
        best = diff if best is None else np.maximum(best, diff)
    return float(best.mean()), best


def letterbox(img, target_size):
    target_w, target_h = target_size
    h, w = img.shape[:2]
    scale = min(target_w / w, target_h / h)
    new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))

    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    canvas = np.zeros((target_h, target_w, 3), np.uint8)
    top, left = (target_h - new_h) // 2, (target_w - new_w) // 2
    canvas[top : top + new_h, left : left + new_w] = cv2.resize(
        img, (new_w, new_h), interpolation=interpolation
    )
    return canvas


def process_image(img_bytes, target_size=(640, 480)):
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        st.error(
            "That file could not be decoded as an image. Re-save it as JPEG or PNG."
        )
        st.stop()
    resized = letterbox(img, target_size)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, BLUR_KERNEL, 0)
    return resized, gray, blurred


def align_to_reference(
    live_bgr,
    live_gray,
    ref_gray,
    min_inliers=15,
    ratio=0.75,
    min_inlier_frac=0.4,
):
    orb = cv2.ORB_create(2000)
    live_kp, live_desc = orb.detectAndCompute(live_gray, None)
    ref_kp, ref_desc = orb.detectAndCompute(ref_gray, None)
    if live_desc is None or ref_desc is None:
        return None, None

    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(live_desc, ref_desc, k=2)
    good = [
        p[0]
        for p in pairs
        if len(p) == 2 and p[0].distance < ratio * p[1].distance
    ]
    if len(good) < min_inliers:
        return None, None

    src = np.float32([live_kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([ref_kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    matrix, inliers = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC)
    if matrix is None or inliers is None:
        return None, None

    agreeing = int(inliers.sum())
    if agreeing < min_inliers or agreeing < min_inlier_frac * len(good):
        return None, None

    h, w = ref_gray.shape
    warped = cv2.warpAffine(live_bgr, matrix, (w, h))
    covered = cv2.warpAffine(np.full((h, w), 255, np.uint8), matrix, (w, h))
    return warped, cv2.erode(covered, np.ones((9, 9), np.uint8))


def main():
    st.set_page_config(
        page_title="Mattel Packaging Inspector",
        layout="centered",
        page_icon="💖",
    )

    # Execute IP Check Authentication Gatekeeper First
    if not check_authentication():
        return

    # Security & UI Layout Injection
    st.markdown(CSS_THEME, unsafe_allow_html=True)
    st.markdown(HEADER_HTML, unsafe_allow_html=True)

    # Dynamic Watermark Injection
    st.markdown(
        f"""
        <div class="watermark">
            CONFIDENTIAL - MATTEL INTERNAL<br>
            Network Verified<br>
            IP: {get_remote_ip()}
        </div>
    """,
        unsafe_allow_html=True,
    )

    # Sidebar Parameters & IP Status
    st.sidebar.markdown("### Access Status")
    st.sidebar.success("Network Authorized")
    st.sidebar.write(f"IP: `{get_remote_ip()}`")

    st.sidebar.markdown("---")
    st.sidebar.header("Parameters")
    thresh_val = st.sidebar.slider("Sensitivity Threshold", 30, 200, 80, 5)
    min_area_val = st.sidebar.slider(
        "Min Defect Size (px)", 100, 5000, 800, 100
    )

    # Step 1: Product and its golden sample
    st.markdown("<p class='ui-heading'>1. Product</p>", unsafe_allow_html=True)

    NEW_SKU = "\u2014 new SKU \u2014"
    catalogue = known_skus()
    choice = st.selectbox("SKU", catalogue + [NEW_SKU])
    sku = (
        st.text_input("New SKU code", placeholder="GTX99-beach").strip()
        if choice == NEW_SKU
        else choice
    )

    samples = references_for(sku) if sku else []
    uploaded_file = st.file_uploader(
        "Golden sample" if not samples else "Add another golden sample",
        type=["jpg", "png", "jpeg"],
    )

    if uploaded_file is not None and not sku:
        st.warning("Give the SKU a code before uploading its golden sample.")
    elif uploaded_file is not None:
        data = uploaded_file.getvalue()
        if hashlib.sha256(data).hexdigest() not in {
            s["digest"] for s in samples
        }:
            save_reference(sku, data, Path(uploaded_file.name).suffix or ".jpg")
            samples = references_for(sku)

    missing = [s for s in samples if not Path(s["path"]).exists()]
    if missing:
        st.error(
            f"{len(missing)} golden sample(s) recorded for {sku} are missing from disk. "
            "Upload them again, or remove them below."
        )
    samples = [s for s in samples if Path(s["path"]).exists()]

    if samples:
        ref_img, ref_sharp, ref_gray = process_image(
            Path(samples[0]["path"]).read_bytes()
        )
        sample_grays = [ref_gray]
        unregistered = []

        for extra in samples[1:]:
            extra_img, extra_sharp, extra_gray = process_image(
                Path(extra["path"]).read_bytes()
            )
            onto_anchor, _ = align_to_reference(
                extra_img, extra_sharp, ref_sharp
            )
            if onto_anchor is None:
                unregistered.append(Path(extra["path"]).name)
                continue
            sample_grays.append(
                cv2.GaussianBlur(
                    cv2.cvtColor(onto_anchor, cv2.COLOR_BGR2GRAY),
                    BLUR_KERNEL,
                    0,
                )
            )

        if unregistered:
            st.warning(
                "Left out of the comparison, being too unlike the first sample to register: "
                + ", ".join(unregistered)
            )

        zones = zones_for(sku)

        st.image(
            draw_zones(ref_img, zones),
            channels="BGR",
            caption=f"Master Reference \u2014 {sku} ({len(sample_grays)} of "
            f"{len(samples)} samples in the comparison)",
            width="stretch",
        )

        with st.expander(f"Golden samples ({len(samples)} held)"):
            st.caption(
                "The first is the anchor every capture is registered onto. Each extra sample "
                "widens the tolerance: a pixel only counts as differing when it differs from "
                "all of them."
            )
            for position, sample in enumerate(samples):
                row, remove = st.columns([4, 1])
                row.text(
                    ("anchor  " if position == 0 else "        ")
                    + Path(sample["path"]).name
                )
                if remove.button("Remove", key=f"remove-sample-{sample['id']}"):
                    delete_reference(sample["id"])
                    st.rerun()

        with st.expander(f"Inspection regions ({len(zones)} named)"):
            st.caption(
                "Name the area each component occupies on the golden sample. A capture is "
                "registered onto this frame first, so a region keeps its meaning across units."
            )
            name = st.text_input("Region name", placeholder="shoe_left")
            left, top, width, height = st.columns(4)
            zone_x = left.number_input("x", 0, 639, 0, 5)
            zone_y = top.number_input("y", 0, 479, 0, 5)
            zone_w = width.number_input("width", 1, 640, 120, 5)
            zone_h = height.number_input("height", 1, 480, 120, 5)

            if st.button("Save region"):
                if name.strip():
                    save_zone(sku, name.strip(), zone_x, zone_y, zone_w, zone_h)
                    st.rerun()
                else:
                    st.warning("A region needs a name.")

            for zone in zones:
                row, remove = st.columns([4, 1])
                row.text(
                    f"{zone['name']}  ({zone['x']}, {zone['y']})  {zone['w']}x{zone['h']}"
                )
                if remove.button("Remove", key=f"remove-{zone['id']}"):
                    delete_zone(zone["id"])
                    st.rerun()

        # Step 2: Live Scanning
        st.markdown(
            "<p class='ui-heading'>Position packaging in frame</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p class='ui-subtext'>Tap button below to capture</p>",
            unsafe_allow_html=True,
        )

        camera_image = st.camera_input("Scan Packaging")

        if camera_image is not None:
            capture_bytes = camera_image.getvalue()
            live_frame, live_sharp, live_gray = process_image(capture_bytes)

            warped, covered = align_to_reference(
                live_frame, live_sharp, ref_sharp
            )
            if warped is None:
                covered = None
                st.warning(
                    "Could not align this capture to the reference, so it is being compared as shot. "
                    "Re-take it with the product framed as the golden sample was."
                )
            else:
                live_frame = warped
                live_gray = cv2.GaussianBlur(
                    cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY), BLUR_KERNEL, 0
                )

            score, diff = combined_difference(sample_grays, live_gray)
            diff_scaled = (np.clip(diff, 0, 1) * 255).astype("uint8")

            _, thresh = cv2.threshold(
                diff_scaled, thresh_val, 255, cv2.THRESH_BINARY_INV
            )
            if covered is not None:
                thresh = cv2.bitwise_and(thresh, covered)
            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            annotated_frame = draw_zones(live_frame, zones)
            defects = 0
            flagged = []

            for cnt in contours:
                if cv2.contourArea(cnt) > min_area_val:
                    defects += 1
                    x, y, w, h = cv2.boundingRect(cnt)
                    hit = zone_for_box(zones, (x, y, w, h))
                    if hit and hit not in flagged:
                        flagged.append(hit)
                    cv2.rectangle(
                        annotated_frame, (x, y), (x + w, y + h), (0, 0, 255), 2
                    )
                    cv2.putText(
                        annotated_frame,
                        hit or "DEFECT",
                        (x, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 0, 255),
                        2,
                    )

            # Step 3: Analysis Display
            st.markdown(
                "<hr style='border: 0.5px solid #FFB6C1;'>",
                unsafe_allow_html=True,
            )

            match_score = round(score * 100, 2)
            col1, col2 = st.columns(2)
            col1.metric("Similarity", f"{match_score}%")

            verdict = "REJECT" if defects else "PASS"

            if defects:
                col2.metric(
                    "Status",
                    "REJECT",
                    delta="- Defect Found",
                    delta_color="inverse",
                )
                if flagged:
                    st.error(
                        "Inspection Failed. Check these regions: "
                        + ", ".join(flagged)
                    )
                else:
                    st.error(
                        "Inspection Failed: Variance detected in packaging layout."
                    )
            else:
                col2.metric("Status", "PASS", delta="Match")
                st.success("Inspection Passed: Packaging matches reference sample.")

            st.image(
                annotated_frame,
                channels="BGR",
                caption="Inspection Overlay",
                width="stretch",
            )

            digest = hashlib.sha256(capture_bytes).hexdigest()
            if st.session_state.get("logged_capture") != digest:
                log_inspection(
                    digest,
                    capture_bytes,
                    "." + (camera_image.type or "image/jpeg").split("/")[-1],
                    verdict,
                    match_score,
                    defects,
                    warped is not None,
                    thresh_val,
                    min_area_val,
                    ", ".join(flagged),
                    sku,
                )
                st.session_state["logged_capture"] = digest

            with st.expander("Show Difference Mask"):
                st.image(
                    thresh, caption="Binary Difference Map", width="stretch"
                )

            with st.expander("Recent Inspections"):
                rows = recent_inspections()
                if rows:
                    st.dataframe(rows, width="stretch", hide_index=True)
                else:
                    st.caption("Nothing recorded yet.")

    else:
        st.info(
            "Pick a SKU and give it a golden sample to begin the inspection workflow."
        )


if __name__ == "__main__":
    main()
