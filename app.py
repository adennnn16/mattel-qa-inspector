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
    """Mendapatkan IP Address pengunjung dari HTTP Header Streamlit."""
    headers = st.context.headers
    if "X-Forwarded-For" in headers:
        return headers["X-Forwarded-For"].split(",")[0].strip()
    return headers.get("Remote-Addr", "")


def check_authentication():
    client_ip = get_remote_ip()

    if client_ip != ALLOWED_IP:
        # Tampilan pemblokiran jika IP tidak sesuai
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


# Jalankan proteksi IP
if check_authentication():

    # Custom Styling
    CSS_THEME = """
        <style>
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
        </style>
    """

    st.markdown(CSS_THEME, unsafe_allow_html=True)

    # Application Header
    HEADER_HTML = """
        <div class="mattel-header">
            <div>
                <p class="mattel-sub">MATTEL</p>
                <h1 class="mattel-title">Packaging Inspector</h1>
            </div>
            <div class="barbie-badge">Barbie</div>
        </div>
    """
    st.markdown(HEADER_HTML, unsafe_allow_html=True)

    # Inspection Parameters
    st.sidebar.header("Parameters")
    thresh_val = st.sidebar.slider("Sensitivity Threshold", 30, 200, 80, 5)
    min_area_val = st.sidebar.slider(
        "Min Defect Size (px)", 500, 10000, 4000, 500
    )

    def process_image(img_bytes, target_size=(640, 480)):
        """Convert uploaded bytes to grayscale blurred image matrix."""
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        resized = cv2.resize(img, target_size)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (11, 11), 0)
        return resized, blurred

    # Step 1: Reference Setup
    st.markdown(
        "<p class='ui-heading'>1. Reference Image</p>", unsafe_allow_html=True
    )
    uploaded_file = st.file_uploader(
        "Upload Golden Sample", type=["jpg", "png", "jpeg"]
    )

    if uploaded_file is not None:
        ref_img, ref_gray = process_image(uploaded_file.read())
        st.image(
            ref_img,
            channels="BGR",
            caption="Master Reference",
            use_container_width=True,
        )

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
            live_frame, live_gray = process_image(camera_image.read())

            # Structural Similarity Comparison
            score, diff = ssim(ref_gray, live_gray, full=True)
            diff_scaled = (diff * 255).astype("uint8")

            _, thresh = cv2.threshold(
                diff_scaled, thresh_val, 255, cv2.THRESH_BINARY_INV
            )
            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            annotated_frame = live_frame.copy()
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

            # Step 3: Analysis Display
            st.markdown(
                "<hr style='border: 0.5px solid #FFB6C1;'>",
                unsafe_allow_html=True,
            )

            match_score = round(score * 100, 2)
            col1, col2 = st.columns(2)
            col1.metric("Similarity", f"{match_score}%")

            if has_defect:
                col2.metric(
                    "Status",
                    "REJECT",
                    delta="- Defect Found",
                    delta_color="inverse",
                )
                st.error(
                    "Inspection Failed: Variance detected in packaging layout."
                )
            else:
                col2.metric("Status", "PASS", delta="Match")
                st.success(
                    "Inspection Passed: Packaging matches reference sample."
                )

            st.image(
                annotated_frame,
                channels="BGR",
                caption="Inspection Overlay",
                use_container_width=True,
            )

            with st.expander("Show Difference Mask"):
                st.image(
                    thresh,
                    caption="Binary Difference Map",
                    use_container_width=True,
                )

    else:
        st.info("Upload a reference sample to begin inspection workflow.")
