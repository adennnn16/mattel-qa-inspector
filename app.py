import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
import streamlit as st

# Configuration
st.set_page_config(
    page_title="Mattel Packaging Inspector", layout="centered", page_icon="💖"
)

# --- SECURITY CONFIGURATION: IP WHITELIST ---
ALLOWED_IP = "10.12.141.25"


def get_remote_ip():
    headers = st.context.headers
    if "X-Forwarded-For" in headers:
        return headers["X-Forwarded-For"].split(",")[0].strip()
    return headers.get("Remote-Addr", "")


def check_authentication():
    client_ip = get_remote_ip()
    if client_ip != ALLOWED_IP:
        st.markdown(
            f"""
            <div style="
                background-color: #FFFFFF;
                padding: 30px;
                border-radius: 20px;
                box-shadow: 0 8px 16px rgba(255, 20, 147, 0.2);
                border: 2px solid #FF1493;
                max-width: 400px;
                margin: 50px auto;
                text-align: center;
                font-family: sans-serif;
            ">
                <h2 style="color: #D81B60; margin-bottom: 10px;">⛔ Access Denied</h2>
                <p style="color: #FF1493; font-weight: bold; font-size: 14px;">IP Address Tidak Diizinkan ({client_ip})</p>
                <p style="color: #666; font-size: 12px; margin-top: 15px;">
                    Aplikasi ini dikunci dan hanya dapat diakses melalui IP <b>{ALLOWED_IP}</b>.
                </p>
            </div>
        """,
            unsafe_allow_html=True,
        )
        return False
    return True


if check_authentication():

    # Custom Styling & Anti-Screenshot Protocol (Blank Screen)
    CSS_AND_JS = """
        <style>
        body, .stApp {
            -webkit-user-select: none;
            user-select: none;
            background-color: #FFF0F5;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        .blank-screen {
            background-color: #FFFFFF !important;
            opacity: 0 !important;
            filter: brightness(10) contrast(0) !important;
            transition: none !important;
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

        .mattel-sub { font-size: 10px; font-weight: 700; color: #FFB6C1; margin: 0; }
        .mattel-title { font-size: 20px; font-weight: 800; margin: 0; }
        .barbie-badge { background-color: rgba(255, 255, 255, 0.2); padding: 4px 12px; border-radius: 8px; font-style: italic; font-weight: 700; }
        .ui-heading { text-align: center; color: #D81B60; font-weight: 700; margin-top: 12px; }
        </style>

        <script>
        document.addEventListener('contextmenu', event => event.preventDefault());

        function makeBlank() {
            document.body.classList.add('blank-screen');
            setTimeout(() => { document.body.classList.remove('blank-screen'); }, 1500);
        }

        document.addEventListener('keyup', (e) => { if (e.key === 'PrintScreen') makeBlank(); });
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey && e.key === 'p') || 
                (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'S')) ||
                (e.metaKey && e.shiftKey && (e.key === '3' || e.key === '4'))) {
                makeBlank();
            }
        });

        window.addEventListener('blur', () => { document.body.classList.add('blank-screen'); });
        window.addEventListener('focus', () => { document.body.classList.remove('blank-screen'); });
        </script>
    """
    st.markdown(CSS_AND_JS, unsafe_allow_html=True)

    # Header
    st.markdown(
        """
        <div class="mattel-header">
            <div>
                <p class="mattel-sub">MATTEL</p>
                <h1 class="mattel-title">Packaging Inspector</h1>
            </div>
            <div class="barbie-badge">Barbie</div>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # Parameters
    st.sidebar.header("Parameters")
    thresh_val = st.sidebar.slider("Sensitivity Threshold", 30, 200, 80, 5)
    min_area_val = st.sidebar.slider(
        "Min Defect Size (px)", 500, 10000, 4000, 500
    )
    auto_mode = st.sidebar.checkbox(
        "Continuous Auto-Scan (Conveyor Mode)", value=True
    )

    # Reference Image
    st.markdown(
        "<p class='ui-heading'>1. Reference Master Sample</p>",
        unsafe_allow_html=True,
    )
    uploaded_file = st.file_uploader(
        "Upload Reference Image", type=["jpg", "png", "jpeg"]
    )

    if uploaded_file is not None:
        file_bytes = np.frombuffer(uploaded_file.read(), np.uint8)
        ref_img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        ref_img = cv2.resize(ref_img, (640, 480))
        ref_gray = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)
        ref_gray = cv2.GaussianBlur(ref_gray, (11, 11), 0)

        st.image(
            ref_img,
            channels="BGR",
            caption="Master Reference",
            use_container_width=True,
        )

        st.markdown(
            "<p class='ui-heading'>2. Conveyor Scanner</p>",
            unsafe_allow_html=True,
        )
        camera_image = st.camera_input("Scanner Active")

        if camera_image is not None:
            live_bytes = np.frombuffer(camera_image.read(), np.uint8)
            live_img = cv2.imdecode(live_bytes, cv2.IMREAD_COLOR)
            live_img = cv2.resize(live_img, (640, 480))
            live_gray = cv2.cvtColor(live_img, cv2.COLOR_BGR2GRAY)
            live_gray = cv2.GaussianBlur(live_gray, (11, 11), 0)

            score, diff = ssim(ref_gray, live_gray, full=True)
            diff_scaled = (diff * 255).astype("uint8")

            _, thresh = cv2.threshold(
                diff_scaled, thresh_val, 255, cv2.THRESH_BINARY_INV
            )
            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            annotated_frame = live_img.copy()
            has_defect = False

            for cnt in contours:
                if cv2.contourArea(cnt) > min_area_val:
                    has_defect = True
                    x, y, w, h = cv2.boundingRect(cnt)
                    cv2.rectangle(
                        annotated_frame, (x, y), (x + w, y + h), (0, 0, 255), 2
                    )
                    cv2.putText(
                        annotated_frame,
                        "DEFECT",
                        (x, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 0, 255),
                        2,
                    )

            match_score = round(score * 100, 2)
            col1, col2 = st.columns(2)
            col1.metric("Similarity", f"{match_score}%")

            if has_defect:
                col2.metric("Status", "REJECT", delta="- Defect Found")
                st.error("INSPECTION FAILED: Defect Detected!")
            else:
                col2.metric("Status", "PASS", delta="Match")
                st.success("INSPECTION PASSED")

            st.image(
                annotated_frame,
                channels="BGR",
                caption="Inspection Analysis",
                use_container_width=True,
            )

            # Jika mode conveyor aktif, lakukan refresh otomatis untuk menangkap frame berikutnya
            if auto_mode:
                st.rerun()
