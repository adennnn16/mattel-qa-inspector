import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer
import av

# 1. Configuration
st.set_page_config(
    page_title="Mattel Packaging Inspector", layout="centered", page_icon="💖"
)

# --- SECURITY CONFIGURATION: IP WHITELIST ---
ALLOWED_IP = "192.168.0.103"


def get_remote_ip():
    """Mendapatkan IP Address pengunjung dari HTTP Header Streamlit."""
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

    # 2. Custom Styling & Advanced Anti-Screenshot Protocol (Blank Screen)
    CSS_AND_JS_PROTECTION = """
        <style>
        /* Mencegah seleksi teks & klik kanan */
        body, .stApp {
            -webkit-user-select: none;
            -moz-user-select: none;
            -ms-user-select: none;
            user-select: none;
            background-color: #FFF0F5;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        /* Class untuk memutihkan seluruh tampilan saat terdeteksi SS atau Hilang Fokus */
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

        .ui-heading {
            text-align: center;
            color: #D81B60;
            font-weight: 700;
            margin-top: 12px;
            margin-bottom: 4px;
        }
        </style>

        <script>
        // Mencegah Menu Klik Kanan
        document.addEventListener('contextmenu', event => event.preventDefault());

        // Fungsi Memutihkan Layar
        function makeBlank() {
            document.body.classList.add('blank-screen');
            setTimeout(() => {
                document.body.classList.remove('blank-screen');
            }, 1500);
        }

        // Detect Tombol PrintScreen & Shortcut SS HP/PC
        document.addEventListener('keyup', (e) => {
            if (e.key === 'PrintScreen') makeBlank();
        });

        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey && e.key === 'p') || 
                (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'S')) ||
                (e.metaKey && e.shiftKey && (e.key === '3' || e.key === '4' || e.key === '5'))) {
                makeBlank();
            }
        });

        // Ketika HP/Browser memicu screenshot, sistem OS akan mengambil fokus layar.
        // Event blur ini akan mengubah tampilan menjadi putih total tepat sebelum foto SS ditangkap OS.
        window.addEventListener('blur', () => {
            document.body.classList.add('blank-screen');
        });

        window.addEventListener('focus', () => {
            document.body.classList.remove('blank-screen');
        });
        </script>
    """
    st.markdown(CSS_AND_JS_PROTECTION, unsafe_allow_html=True)

    # 3. Header
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

    # 4. Parameters Sidebar
    st.sidebar.header("Parameters")
    thresh_val = st.sidebar.slider("Sensitivity Threshold", 30, 200, 80, 5)
    min_area_val = st.sidebar.slider(
        "Min Defect Size (px)", 500, 10000, 4000, 500
    )

    # 5. Reference Image Setup
    st.markdown(
        "<p class='ui-heading'>1. Reference Master Sample</p>",
        unsafe_allow_html=True,
    )
    uploaded_file = st.file_uploader(
        "Upload Reference Image", type=["jpg", "png", "jpeg"]
    )

    ref_gray = None
    if uploaded_file is not None:
        file_bytes = np.frombuffer(uploaded_file.read(), np.uint8)
        ref_img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        ref_img = cv2.resize(ref_img, (640, 480))
        gray = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)
        ref_gray = cv2.GaussianBlur(gray, (11, 11), 0)
        st.image(
            ref_img,
            channels="BGR",
            caption="Master Reference Active",
            use_container_width=True,
        )

    # 6. Real-Time Processing Callback Function
    def video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        resized = cv2.resize(img, (640, 480))

        # Jika reference image sudah diunggah, lakukan analisis real-time
        if ref_gray is not None:
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            live_gray = cv2.GaussianBlur(gray, (11, 11), 0)

            # Hitung Structural Similarity (SSIM)
            score, diff = ssim(ref_gray, live_gray, full=True)
            diff_scaled = (diff * 255).astype("uint8")

            _, thresh = cv2.threshold(
                diff_scaled, thresh_val, 255, cv2.THRESH_BINARY_INV
            )
            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            has_defect = False
            for cnt in contours:
                if cv2.contourArea(cnt) > min_area_val:
                    has_defect = True
                    x, y, w, h = cv2.boundingRect(cnt)
                    # Bounding Box Merah untuk Defect
                    cv2.rectangle(resized, (x, y), (x + w, y + h), (0, 0, 255), 3)
                    cv2.putText(
                        resized,
                        "DEFECT",
                        (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 255),
                        2,
                    )

            # Overlay Status pada Frame Video
            status_text = (
                f"REJECT (Match: {round(score*100,1)}%)"
                if has_defect
                else f"PASS (Match: {round(score*100,1)}%)"
            )
            color = (0, 0, 255) if has_defect else (0, 255, 0)

            cv2.rectangle(resized, (10, 10), (320, 50), (0, 0, 0), -1)
            cv2.putText(
                resized,
                status_text,
                (20, 38),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
            )

        return av.VideoFrame.from_ndarray(resized, format="bgr24")

    # 7. Real-Time Camera Stream Section
    st.markdown(
        "<p class='ui-heading'>2. Real-Time Conveyor Scanner</p>",
        unsafe_allow_html=True,
    )

    if ref_gray is not None:
        webrtc_streamer(
            key="conveyor-inspector",
            mode=WebRtcMode.SENDRECV,
            video_frame_callback=video_frame_callback,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True,
        )
    else:
        st.info("Upload sampel referensi di atas untuk mengaktifkan pemindaian otomatis.")
