import streamlit as st
import os
from google import genai
from google.genai import types
import requests
import io
import base64
from PIL import Image
import pdfplumber

# --- 1. 기능 함수 (최신 구글 API 규칙 적용) ---

def get_available_imagen_model(api_key):
    """내 계정에서 사용 가능한 최신 Imagen 3 모델을 자동으로 찾습니다."""
    if not api_key: return None, "API 키 없음"
    try:
        temp_client = genai.Client(api_key=api_key)
        available_models = [m.name for m in temp_client.models.list() if "imagen" in m.name.lower()]
        priority_models = ["imagen-3.0-generate-002", "imagen-3.0-generate-001", "imagen-3"]
        for p in priority_models:
            for a in available_models:
                if p == a or p in a: return a, None
        return available_models[0] if available_models else "imagen-3.0-generate-002", None
    except: return "imagen-3.0-generate-002", None

def get_available_gemini_model(api_key):
    """사용 가능한 가장 똑똑한 Gemini 모델을 찾습니다."""
    if not api_key: return None, "API 키 없음"
    try:
        temp_client = genai.Client(api_key=api_key)
        available_models = [m.name for m in temp_client.models.list() if "gemini" in m.name.lower()]
        priority_models = ["gemini-2.0-pro", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-1.5-flash"]
        for p in priority_models:
            for a in available_models:
                if p in a: return a, None
        return available_models[0] if available_models else "gemini-1.5-flash", None
    except: return "gemini-1.5-flash", None

# --- 2. 디자인 가이드 ---

DESIGN_A_GUIDE = """
[BASE GUIDE - TYPE 1 (Layout & System Only)]
SYSTEM
* Information-first composition / Diagram-style visual language / Presentation board style
PRIORITY
1. High readability / 2. Balanced spacing / 3. Clean structured layout
COLOR
* Primary: Muted deep green (#249473) / Secondary: Desaturated brown (#3E3523) / Minimal: Burnt orange (#CC5200)
PANEL
* Surface: Glass-like panels, near-white, light transparency, rounded edges
"""

ICON_A_GUIDE = """
[ICON SYSTEM - TYPE 1]
* Style: 3D isometric, clay-texture, soft semi-gloss, studio lighting
"""

# --- 3. 페이지 설정 및 디자인 ---

st.set_page_config(page_title="나노바나나 인포그래픽 엔진", layout="wide", page_icon="🍌")

st.markdown("""
    <style>
    .stApp { background-color: #FAFAF8; }
    .main-title { font-size: 24px; font-weight: 700; color: #1a1a1a; margin-bottom: 5px; }
    .nanobana-badge { display: inline-block; padding: 2px 12px; border-radius: 99px; background: #edf7f3; border: 1px solid #a8dcc8; color: #266651; font-size: 12px; font-weight: 600; margin-bottom: 10px; }
    .flow-notice { background: #edf7f3; border: 1px solid #a8dcc8; border-radius: 10px; padding: 15px; color: #266651; font-size: 14px; margin-bottom: 20px; }
    div.stButton > button[kind="primary"] { background-color: #249473 !important; color: white !important; border: none !important; box-shadow: 0 2px 4px rgba(36,148,115,0.3); }
    div.stButton > button[kind="primary"]:hover { background-color: #266651 !important; }
    div.stButton > button[kind="secondary"] { background-color: #edf7f3 !important; color: #266651 !important; border: 1px solid #a8dcc8 !important; }
    .summary-box { background: #ffffff; border-left: 5px solid #D0A98C; padding: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin: 10px 0; }
    </style>
    """, unsafe_allow_html=True)

# 세션 상태 관리
for key, val in {'design_style': 'Style A', 'icon_style': 'Icon A', 'gen_mode': 'Strict', 
                'api_key': os.getenv("GEMINI_API_KEY"), 'selected_gemini_model': None, 'selected_imagen_model': None}.items():
    if key not in st.session_state: st.session_state[key] = val

# --- 4. 사이드바 (설정) ---

with st.sidebar:
    st.markdown("### 🔑 API 설정")
    u_key = st.text_input("Gemini API Key", type="password", value=st.session_state.api_key if st.session_state.api_key else "")
    if u_key != st.session_state.api_key:
        st.session_state.api_key = u_key
        st.session_state.selected_gemini_model = None
        st.session_state.selected_imagen_model = None
        st.rerun()

    if st.session_state.api_key:
        st.success("✅ API 키 확인")
        if not st.session_state.selected_gemini_model:
            st.session_state.selected_gemini_model, _ = get_available_gemini_model(st.session_state.api_key)
        if not st.session_state.selected_imagen_model:
            st.session_state.selected_imagen_model, _ = get_available_imagen_model(st.session_state.api_key)
        st.info(f"🤖 {st.session_state.selected_gemini_model}")
        st.info(f"🎨 {st.session_state.selected_imagen_model}")
    
    st.markdown("### 📂 원고 업로드")
    uploaded_file = st.file_uploader("PDF/TXT 파일", type=['pdf', 'txt'])
    manual_text = st.text_area("직접 입력", placeholder="내용을 입력하세요...")
    
    st.markdown("### 📏 출력 크기")
    dpi = st.selectbox("DPI 선택", [72, 96, 150, 300], index=2)
    px_w, px_h = int(210 * (dpi/25.4)), int(297 * (dpi/25.4))
    st.caption(f"최종 크기: {px_w}x{px_h}px")

# --- 5. 메인 화면 (복구된 구성) ---

st.markdown('<p class="main-title">🍌 나노바나나 디자인 엔진 (Imagen 3)</p>', unsafe_allow_html=True)
st.markdown('<span class="nanobana-badge">● BASE GUIDE 1 내장</span>', unsafe_allow_html=True)
st.markdown('<div class="flow-notice">원고 업로드 → 모드/디자인 선택 → 생성 클릭</div>', unsafe_allow_html=True)

with st.container(border=True):
    # 생성 모드
    st.markdown("#### 🎯 생성 모드")
    m1, m2 = st.columns(2)
    if m1.button("Strict (구조 보존)", use_container_width=True, type="primary" if st.session_state.gen_mode == "Strict" else "secondary"):
        st.session_state.gen_mode = "Strict"; st.rerun()
    if m2.button("Generative (재구성)", use_container_width=True, type="primary" if st.session_state.gen_mode == "Generative" else "secondary"):
        st.session_state.gen_mode = "Generative"; st.rerun()
    
    st.divider()
    # 디자인 컨셉
    st.markdown("#### 🎨 디자인 컨셉")
    d1, d2, d3 = st.columns(3)
    if d1.button("디자인 A (한맥)", use_container_width=True, type="primary" if st.session_state.design_style == "Style A" else "secondary"):
        st.session_state.design_style = "Style A"; st.rerun()
    if d2.button("디자인 B", use_container_width=True, type="primary" if st.session_state.design_style == "Style B" else "secondary"):
        st.session_state.design_style = "Style B"; st.rerun()
    if d3.button("디자인 C", use_container_width=True, type="primary" if st.session_state.design_style == "Style C" else "secondary"):
        st.session_state.design_style = "Style C"; st.rerun()
    
    st.divider()
    # 아이콘 스타일
    st.markdown("#### 💎 아이콘 스타일")
    i1, i2, i3 = st.columns(3)
    if i1.button("아이콘 A (3D)", use_container_width=True, type="primary" if st.session_state.icon_style == "Icon A" else "secondary"):
        st.session_state.icon_style = "Icon A"; st.rerun()
    if i2.button("아이콘 B", use_container_width=True, type="primary" if st.session_state.icon_style == "Icon B" else "secondary"):
        st.session_state.icon_style = "Icon B"; st.rerun()
    if i3.button("아이콘 C", use_container_width=True, type="primary" if st.session_state.icon_style == "Icon C" else "secondary"):
        st.session_state.icon_style = "Icon C"; st.rerun()

st.divider()

# 텍스트 처리
doc_content = ""
if uploaded_file:
    if uploaded_file.type == "application/pdf":
        with pdfplumber.open(uploaded_file) as pdf: doc_content = "".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    else: doc_content = uploaded_file.read().decode("utf-8")
elif manual_text: doc_content = manual_text

client = genai.Client(api_key=st.session_state.api_key) if st.session_state.api_key else None

if doc_content and client:
    st.markdown("### 📋 원고 핵심 요약")
    with st.spinner("요약 중..."):
        try:
            res = client.models.generate_content(model=st.session_state.selected_gemini_model, contents=f"3줄 요약: {doc_content[:1500]}")
            st.markdown(f'<div class="summary-box">{res.text}</div>', unsafe_allow_html=True)
        except: st.info("요약 생략")

# --- 6. 실행 버튼 및 생성 로직 ---

if st.button("🚀 조감도 및 아이콘 생성", type="primary", use_container_width=True):
    if not doc_content: st.error("원고를 입력하세요!")
    elif not client: st.error("API 키를 확인하세요!")
    else:
        try:
            with st.spinner("프롬프트 구성 중..."):
                prompt_query = f"{DESIGN_A_GUIDE}\n{ICON_A_GUIDE}\nMODE: {st.session_state.gen_mode}\nCONTENT: {doc_content[:1500]}\nImagen 3용 영문 프롬프트로 변환해줘."
                final_prompt = client.models.generate_content(model=st.session_state.selected_gemini_model, contents=prompt_query).text

            with st.spinner("Imagen 3 조감도 생성 중..."):
                ratio = "16:9" if px_w/px_h > 1.2 else "3:4" if px_w/px_h < 0.8 else "1:1"
                # 🌟 최종 수정: client.models.generate_image (소문자/단수형 확인)
                img_res = client.models.generate_image(
                    model=st.session_state.selected_imagen_model,
                    prompt=final_prompt,
                    config=types.GenerateImageConfig(aspect_ratio=ratio, number_of_images=1)
                )
                img_bytes = img_res.generated_images[0].image_bytes
                
                col_res1, col_res2 = st.columns([0.7, 0.3])
                col_res1.image(Image.open(io.BytesIO(img_bytes)), use_container_width=True)
                col_res2.markdown(f"**생성 완료!**\n\n모델: {st.session_state.selected_imagen_model}\n비율: {ratio}")
                with col_res2.expander("프롬프트 확인"): st.write(final_prompt)
                st.balloons()
        except Exception as e:
            st.error(f"생성 실패: {e}")
