import streamlit as st
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Mattel Packaging Inspector", layout="centered", page_icon="💖")

# --- CUSTOM MATTEL / BARBIE PINK CSS THEME ---
st.markdown("""
    <style>
    /* Global Background & Font */
    .stApp {
        background-color: #FFF0F5;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Header Styling */
    .mattel-header {
        background: linear-gradient(135deg, #FF1493 0%, #FF007F 100%);
        padding: 20px 25px;
        border-radius: 20px;
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 8px 16px rgba(255, 20, 147, 0.3);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .mattel-sub {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: #FFB6C1;
        margin: 0;
    }
    .mattel-title {
        font-size: 22px;
        font-weight: 900;
        margin: 0;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }
    .barbie-badge {
        background-color: rgba(255,255,255,0.2);
        padding: 6px 14px;
        border-radius: 12px;
        font-style: italic;
        font-weight: bold;
        font-size: 18px;
        border: 1px solid rgba(255,255,255,0.4);
    }

    /* Container Box Styling */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 500px;
    }

    /* Streamlit Buttons to Mattel Pink */
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #FF1493 0%, #E60067 100%);
        color: white;
        font-weight: 800;
        font-size: 16px;
        border-radius: 15px;
        border: none;
        padding: 14px 28px;
        box-shadow: 0 6px 12px rgba(255, 20, 147, 0.4);
        width: 100%;
        transition: all 0.3s ease;
    }
    div.stButton > button:first-child:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 18px rgba(255, 20, 147, 0.6);
        background: linear-gradient(90deg, #E60067 0%, #C70055 100%);
    }

    /* Camera & File Uploader Borders */
    [data-testid="stCameraInput"] {
        border: 4px solid #FF1493;
        border-radius: 20px;
        overflow: hidden;
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
    }

    /* Instructions Section */
    .instruction-text {
        text-align: center;
        color: #D81B60;
        font-weight: 700;
        margin-top: 15px;
        margin-bottom: 5px;
    }
    .sub-instruction {
        text-align: center;
        color: #FF69B4;
        font-size: 13px;
        margin-bottom: 20px;
    }
    .stars {
        text-align: center;
        font-size: 20px;
        color: #FF1493;
        margin-top: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- MATTEL HEADER UI ---
st.markdown("""
    <div class="mattel-header">
        <div>
            <p class="mattel-sub">MATTEL</p>
            <h1 class="mattel-title">Packaging Inspector</h1>
        </div>
        <div class="barbie-badge">Barbie</div>
    </div>
""", unsafe_allow_html=True)

# --- SIDEBAR CONTROL ---
st.sidebar.header("🎛️ Inspection Settings")
thresh_val = st.sidebar.slider("Sensitivity Threshold", min_value=30, max_value=200, value=80, step=5)
min_area_val = st.sidebar.slider("Minimum Defect Area (px)", min_value=500, max_value=10000, value=4000, step=500)

# --- STEP 1: REFERENCE UPLOAD ---
st.markdown("<p class='instruction-text'>1. Set Reference Sample</p>", unsafe_allow_html=True)
uploaded_file = st.file_uploader("Upload Master Golden Sample", type=["jpg", "png", "jpeg"])

if uploaded_file is not None:
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    ref_img = cv2.imdecode(file_bytes, 1)
    
    ref_img = cv2.resize(ref_img, (640, 480))
    ref_gray = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)
    ref_gray_blur = cv2.GaussianBlur(ref_gray, (11, 11), 0)

    st.image(ref_img, channels="BGR", caption="Active Reference Sample", use_container_width=True)

    # --- STEP 2: CAMERA SCANNER ---
    st.markdown("<div class='stars'>⭐ ⭐ ⭐</div>", unsafe_allow_html=True)
    st.markdown("<p class='instruction-text'>Position packaging in frame</p>", unsafe_allow_html=True)
    st.markdown("<p class='sub-instruction'>then tap Scan Packaging below</p>", unsafe_allow_html=True)

    camera_image = st.camera_input("SCAN PACKAGING")

    if camera_image is not None:
        cam_bytes = np.asarray(bytearray(camera_image.read()), dtype=np.uint8)
        live_frame = cv2.imdecode(cam_bytes, 1)

        live_resized = cv2.resize(live_frame, (640, 480))
        live_gray = cv2.cvtColor(live_resized, cv2.COLOR_BGR2GRAY)
        live_gray_blur = cv2.GaussianBlur(live_gray, (11, 11), 0)

        # Compute SSIM
        score, diff = ssim(ref_gray_blur, live_gray_blur, full=True)
        diff = (diff * 255).astype("uint8")

        thresh = cv2.threshold(diff, thresh_val, 255, cv2.THRESH_BINARY_INV)[1]
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        annotated_frame = live_resized.copy()
        defects_found = False

        for contour in contours:
            if cv2.contourArea(contour) > min_area_val:
                defects_found = True
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), (0, 0, 255), 3)
                cv2.putText(annotated_frame, "MISSING ITEM", (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # --- STEP 3: INSPECTION RESULT ---
        st.markdown("<hr style='border:1px solid #FFB6C1;'>", unsafe_allow_html=True)
        st.markdown("<p class='instruction-text'>Inspection Analysis</p>", unsafe_allow_html=True)
        
        similarity_percentage = round(score * 100, 2)

        col1, col2 = st.columns(2)
        col1.metric(label="Match Score", value=f"{similarity_percentage}%")
        
        if defects_found:
            col2.metric(label="Quality Status", value="REJECT", delta="- DEFECT DETECTED", delta_color="inverse")
            st.error("🚨 RESULT: REJECT - Missing Items Detected!")
        else:
            col2.metric(label="Quality Status", value="PASS", delta="+ COMPLETE")
            st.success("✅ RESULT: PASS - 100% Complete Set!")

        st.image(annotated_frame, channels="BGR", caption="Annotated Result", use_container_width=True)

        with st.expander("🔍 View Pixel Difference Mask"):
            st.image(thresh, caption="White Areas = Pixel Differences", use_container_width=True)

else:
    st.info("💡 Please upload a reference Golden Sample image to initiate inspection.")