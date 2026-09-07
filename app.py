import streamlit as st
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Mattel QA Inspector (Internal)", 
    layout="centered", 
    page_icon="🔒"
)

# --- SESSION STATE FOR AUTHENTICATION ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "user_email" not in st.session_state:
    st.session_state["user_email"] = ""

# --- LOGIN SYSTEM (RESTRICTED TO MATTEL STAFF) ---
def login_screen():
    st.markdown("""
        <style>
        .stApp { background-color: #FFF0F5; }
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
        .login-title {
            color: #D81B60;
            font-weight: 800;
            font-size: 20px;
            margin-bottom: 5px;
        }
        .login-sub {
            color: #888;
            font-size: 12px;
            margin-bottom: 20px;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='login-card'>", unsafe_allow_html=True)
    st.markdown("<p class='login-title'>🔒 Mattel QA Portal</p>", unsafe_allow_html=True)
    st.markdown("<p class='login-sub'>Internal Authorized Personnel Only</p>", unsafe_allow_html=True)

    email = st.text_input("Corporate Email", placeholder="employee@mattel.com")
    password = st.text_input("Access Password", type="password")

    if st.button("Authenticate"):
        if email.lower().endswith("@mattel.com") and password == "MattelQC2026!":
            st.session_state["authenticated"] = True
            st.session_state["user_email"] = email.lower()
            st.rerun()
        else:
            st.error("Akses Ditolak! Wajib menggunakan email @mattel.com dan password yang benar.")

    st.markdown("</div>", unsafe_allow_html=True)


# --- MAIN APPLICATION WORKFLOW ---
def main_app():
    # CSS & Security Scripts
    CSS_AND_SECURITY = f"""
        <style>
        /* Block Text Selection & Mouse Context Menu */
        body {{
            -webkit-user-select: none;
            -moz-user-select: none;
            -ms-user-select: none;
            user-select: none;
        }}
        .stApp {{
            background-color: #FFF0F5;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        .mattel-header {{
            background: linear-gradient(135deg, #FF1493 0%, #FF007F 100%);
            padding: 18px 24px;
            border-radius: 16px;
            color: #FFFFFF;
            margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(255, 20, 147, 0.25);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .mattel-sub {{
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            color: #FFB6C1;
            margin: 0;
        }}
        .mattel-title {{
            font-size: 20px;
            font-weight: 800;
            margin: 0;
        }}
        .barbie-badge {{
            background-color: rgba(255, 255, 255, 0.2);
            padding: 4px 12px;
            border-radius: 8px;
            font-style: italic;
            font-weight: 700;
            font-size: 16px;
            border: 1px solid rgba(255, 255, 255, 0.3);
        }}
        .block-container {{
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 480px;
        }}
        div.stButton > button:first-child {{
            background: linear-gradient(90deg, #FF1493 0%, #E60067 100%);
            color: #FFFFFF;
            font-weight: 700;
            font-size: 15px;
            border-radius: 12px;
            border: none;
            padding: 12px 24px;
            box-shadow: 0 4px 10px rgba(255, 20, 147, 0.3);
            width: 100%;
        }}
        [data-testid="stCameraInput"] {{
            border: 3px solid #FF1493;
            border-radius: 16px;
            overflow: hidden;
        }}
        .ui-heading {{
            text-align: center;
            color: #D81B60;
            font-weight: 700;
            margin-top: 12px;
            margin-bottom: 4px;
        }}
        .ui-subtext {{
            text-align: center;
            color: #FF69B4;
            font-size: 12px;
            margin-bottom: 16px;
        }}
        /* Dynamic Watermark Overlay */
        .watermark {{
            position: fixed;
            bottom: 12px;
            right: 12px;
            opacity: 0.35;
            font-size: 11px;
            color: #D81B60;
            font-weight: bold;
            pointer-events: none;
            z-index: 9999;
            text-align: right;
        }}
        </style>

        <!-- Dynamic Security Script: Blur on Tab Switch -->
        <script>
        window.addEventListener('blur', function() {{
            document.body.style.filter = 'blur(12px)';
        }});
        window.addEventListener('focus', function() {{
            document.body.style.filter = 'none';
        }});
        </script>

        <!-- Watermark Display -->
        <div class="watermark">
            CONFIDENTIAL - MATTEL INTERNAL USE ONLY<br>
            User: {st.session_state['user_email']}
        </div>
    """
    st.markdown(CSS_AND_SECURITY, unsafe_allow_html=True)

    # Header
    st.markdown("""
        <div class="mattel-header">
            <div>
                <p class="mattel-sub">MATTEL INTERNAL</p>
                <h1 class="mattel-title">Packaging Inspector</h1>
            </div>
            <div class="barbie-badge">Barbie</div>
        </div>
    """, unsafe_allow_html=True)

    # Sidebar Logout & Parameters
    st.sidebar.write(f"Logged in: **{st.session_state['user_email']}**")
    if st.sidebar.button("Logout"):
        st.session_state["authenticated"] = False
        st.session_state["user_email"] = ""
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("Inspection Parameters")
    thresh_val = st.sidebar.slider("Sensitivity Threshold", 30, 200, 80, 5)
    min_area_val = st.sidebar.slider("Min Defect Size (px)", 500, 10000, 4000, 500)

    # Helper function for image processing
    def process_image(img_bytes, target_size=(640, 480)):
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        resized = cv2.resize(img, target_size)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (11, 11), 0)
        return resized, blurred

    # Step 1: Reference Upload
    st.markdown("<p class='ui-heading'>1. Master Reference Setup</p>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload Golden Sample", type=["jpg", "png", "jpeg"])

    if uploaded_file is not None:
        ref_img, ref_gray = process_image(uploaded_file.read())
        st.image(ref_img, channels="BGR", caption="Master Reference", use_container_width=True)

        # Step 2: Live Scanning
        st.markdown("<p class='ui-heading'>Position packaging in frame</p>", unsafe_allow_html=True)
        st.markdown("<p class='ui-subtext'>Tap button below to capture</p>", unsafe_allow_html=True)

        camera_image = st.camera_input("Scan Packaging")

        if camera_image is not None:
            live_frame, live_gray = process_image(camera_image.read())

            # Structural Similarity Algorithm
            score, diff = ssim(ref_gray, live_gray, full=True)
            diff_scaled = (diff * 255).astype("uint8")

            _, thresh = cv2.threshold(diff_scaled, thresh_val, 255, cv2.THRESH_BINARY_INV)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            annotated_frame = live_frame.copy()
            has_defect = False

            for cnt in contours:
                if cv2.contourArea(cnt) > min_area_val:
                    has_defect = True
                    x, y, w, h = cv2.boundingRect(cnt)
                    cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                    cv2.putText(
                        annotated_frame, 
                        "DEFECT", 
                        (x, y - 8), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.5, 
                        (0, 0, 255), 
                        2
                    )

            # Step 3: Result Analysis
            st.markdown("<hr style='border: 0.5px solid #FFB6C1;'>", unsafe_allow_html=True)
            
            match_score = round(score * 100, 2)
            col1, col2 = st.columns(2)
            col1.metric("Similarity", f"{match_score}%")

            if has_defect:
                col2.metric("Status", "REJECT", delta="- Defect Found", delta_color="inverse")
                st.error("Inspection Failed: Variance detected in packaging layout.")
            else:
                col2.metric("Status", "PASS", delta="Match")
                st.success("Inspection Passed: Packaging matches reference sample.")

            st.image(annotated_frame, channels="BGR", caption="Inspection Overlay", use_container_width=True)

            with st.expander("Show Difference Mask"):
                st.image(thresh, caption="Binary Difference Map", use_container_width=True)
    else:
        st.info("Upload a reference sample to begin inspection workflow.")


# --- ENTRY POINT ---
if not st.session_state["authenticated"]:
    login_screen()
else:
    main_app()
