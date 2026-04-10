import streamlit as st
import os
from google import genai
from google.genai import types
import requests
import io
import base64
from PIL import Image
import pdfplumber
import importlib.metadata

# --- [기능 함수] 모델 자동 탐색 로직 ---

def get_available_gemini_model(api_key):
    """사용 가능한 최신 Gemini(텍스트) 모델을 탐색합니다."""
    if not api_key: return None, "API 키가 없습니다."
    try:
        temp_client = genai.Client(api_key=api_key)
        available_models = [m.name for m in temp_client.models.list() if "gemini" in m.name]
        
        if not available_models: return None, "Gemini 모델을 찾을 수 없습니다."

        priority_models = [
            "gemini-2.0-pro", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-1.5-flash"
        ]
        for p in priority_models:
            for a in available_models:
                if p in a: return a, None
        return available_models[0], None
    except Exception as e:
        return None, f"Gemini 모델 목록 오류: {e}"

def get_available_imagen_model(api_key):
    """유료 플랜에서 사용 가능한 최신 Imagen 3 모델을 탐색합니다."""
    if not api_key: return None, "API 키가 없습니다."
    try:
        temp_client = genai.Client(api_key=api_key)
        available_models = [m.name for m in temp_client.models.list() if "imagen" in m.name.lower()]
        
        priority_models = ["imagen-3.0-generate-002", "imagen-3.0-generate-001", "imagen-3"]
        for p in priority_models:
            for a in available_models:
                if p == a or p in a: return a, None
        return available_models[0] if available_models else "imagen-3.0-generate-002", None
    except:
        return "imagen-3.0-generate-002", None

# --- [디자인 가이드] 혜봉님 커스텀 상세 가이드 ---

DESIGN_A_GUIDE = """
[BASE GUIDE - TYPE 1 (Layout & System Only)]
SYSTEM
* Information-first composition / Diagram-style visual language / Presentation board style
PRIORITY
1. High readability / 2. Balanced spacing and alignment / 3. Clean structured layout
DESIGN
* White-dominant corporate infographic / High whitespace ratio (70–80%)
* Clean geometric sans-serif placeholders / No background color flooding
COLOR
* Primary Accent (10–20%): Muted deep green (#249473)
* Secondary Accent (5–12%): Desaturated brown (#3E3523 to #604F32 range)
* Minimal Highlight (2–6%): Burnt orange (#CC5200) / Base (65–80%): White
PANEL
* Surface: Glass-like panels, near-white tint, light transparency, defined rounded edges
"""

ICON_A_GUIDE = """
[ICON SYSTEM - TYPE 1]
* Style: 3D isometric product render, high-detail modeling
* Material: Matte clay-texture + soft semi-gloss (not metallic)
* Lighting: Soft studio lighting, top-front key light, no harsh highlights
"""

# --- [UI/UX] 페이지 설정 및 테마 ---

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

# 세션 상태 초기화
for key, val in {
    'design_style': 'Style A', 'icon_style': 'Icon A', 'gen_mode': 'Strict', 
    'api_key': os.getenv("GEMINI_API_KEY"), 'selected_gemini_model': None, 'selected_imagen_model': None
}.items():
    if key not in st.session_state: st.session_state[key] = val

# --- [사이드바] 설정 및 계산기 ---

with st.sidebar:
    st.markdown("### 🔑 API 설정")
    try:
        sdk_v = importlib.metadata.version('google-genai')
        st.caption(f"SDK 버전: `{sdk_v}`")
    except: pass

    user_api_key = st.text_input("Gemini API Key", type="password", value=st.session_state.api_key if st.session_state.api_key else "")
    if user_api_key != st.session_state.api_key:
        st.session_state.api_key = user_api_key
        st.session_state.selected_gemini_model = None
        st.session_state.selected_imagen_model = None
        st.rerun()

    if st.session_state.api_key:
        st.success("✅ 키 연결됨")
        if not st.session_state.selected_gemini_model:
            st.session_state.selected_gemini_model, _ = get_available_gemini_model(st.session_state.api_key)
        if not st.session_state.selected_imagen_model:
            st.session_state.selected_imagen_model, _ = get_available_imagen_model(st.session_state.api_key)
        st.caption(f"🤖 분석: {st.session_state.selected_gemini_model}")
        st.caption(f"🎨 생성: {st.session_state.selected_imagen_model}")

    st.divider()
    st.markdown("### 📏 [복구] 출력 크기 계산기")
    dpi = st.selectbox("DPI 선택", [72, 96, 150, 300], index=2)
    col_w, col_h = st.columns(2)
    mm_w = col_w.number_input("가로(mm)", value=210)
    mm_h = col_h.number_input("세로(mm)", value=297)
    px_w, px_h = int(mm_w * (dpi / 25.4)), int(mm_h * (dpi / 25.4))
    st.info(f"결과: {px_w} × {px_h} px")

    st.divider()
    st.markdown("### 📂 원고 업로드")
    uploaded_file = st.file_uploader("PDF/TXT 파일", type=['pdf', 'txt'])
    manual_text = st.text_area("직접 입력", placeholder="내용을 입력하세요...")

# --- [메인] 화면 구성 및 생성 로직 ---

st.markdown('<p class="main-title">🍌 나노바나나 디자인 엔진 (Imagen 3)</p>', unsafe_allow_html=True)
st.markdown('<span class="nanobana-badge">● BASE GUIDE 1 내장</span>', unsafe_allow_html=True)
st.markdown('<div class="flow-notice">원고 업로드 → 디자인 선택 → 생성 버튼 클릭</div>', unsafe_allow_html=True)

# 디자인 선택 컨테이너 (복구 완료)
with st.container(border=True):
    st.markdown("#### 🎯 생성 모드")
    m1, m2 = st.columns(2)
    if m1.button("Strict (구조 보존)", use_container_width=True, type="primary" if st.session_state.gen_mode == "Strict" else "secondary"):
        st.session_state.gen_mode = "Strict"; st.rerun()
    if m2.button("Generative (재구성)", use_container_width=True, type="primary" if st.session_state.gen_mode == "Generative" else "secondary"):
        st.session_state.gen_mode = "Generative"; st.rerun()
    
    st.divider()
    st.markdown("#### 🎨 디자인 컨셉")
    d1, d2, d3 = st.columns(3)
    for i, (btn, label) in enumerate(zip([d1, d2, d3], ["디자인 A (한맥)", "디자인 B", "디자인 C"])):
        style_key = f"Style {chr(65+i)}"
        if btn.button(label, use_container_width=True, type="primary" if st.session_state.design_style == style_key else "secondary"):
            st.session_state.design_style = style_key; st.rerun()

    st.divider()
    st.markdown("#### 💎 아이콘 스타일")
    i1, i2, i3 = st.columns(3)
    for i, (btn, label) in enumerate(zip([i1, i2, i3], ["아이콘 A (3D)", "아이콘 B", "아이콘 C"])):
        icon_key = f"Icon {chr(65+i)}"
        if btn.button(label, use_container_width=True, type="primary" if st.session_state.icon_style == icon_key else "secondary"):
            st.session_state.icon_style = icon_key; st.rerun()

st.divider()

# 텍스트 추출
doc_content = ""
if uploaded_file:
    if uploaded_file.type == "application/pdf":
        with pdfplumber.open(uploaded_file) as pdf: doc_content = "".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    else: doc_content = uploaded_file.read().decode("utf-8")
elif manual_text: doc_content = manual_text

client = genai.Client(api_key=st.session_state.api_key) if st.session_state.api_key else None

if doc_content and client:
    st.markdown("### 📋 원고 핵심 요약")
    with st.spinner("분석 중..."):
        try:
            res = client.models.generate_content(model=st.session_state.selected_gemini_model, contents=f"3줄 요약: {doc_content[:1500]}")
            st.markdown(f'<div class="summary-box">{res.text}</div>', unsafe_allow_html=True)
        except: st.info("요약 로드 실패")

# --- 최종 이미지 생성 실행 ---

if st.button("🚀 조감도 및 아이콘 생성", type="primary", use_container_width=True):
    if not doc_content: st.error("원고를 먼저 입력해주세요!")
    elif not client: st.error("사이드바에서 API 키를 입력해주세요!")
    else:
        try:
            with st.spinner("프롬프트 구성 중..."):
                design_guide = DESIGN_A_GUIDE if st.session_state.design_style == "Style A" else f"STYLE: {st.session_state.design_style}"
                icon_guide = ICON_A_GUIDE if st.session_state.icon_style == "Icon A" else f"ICON: {st.session_state.icon_style}"
                
                prompt_query = f"{design_guide}\n{icon_guide}\nMODE: {st.session_state.gen_mode}\nCONTENT: {doc_content[:1500]}\nGoogle Imagen 3용 상세 영문 프롬프트로 변환해줘."
                final_prompt = client.models.generate_content(model=st.session_state.selected_gemini_model, contents=prompt_query).text

            with st.spinner("Imagen 3 엔진 가동 중..."):
                ratio_val = px_w / px_h
                target_ratio = "16:9" if ratio_val > 1.3 else "3:4" if ratio_val < 0.8 else "1:1"
                
                # [최종 수정] client.models.generate_image (소문자/단수형)
                img_res = client.models.generate_image(
                    model=st.session_state.selected_imagen_model,
                    prompt=final_prompt,
                    config=types.GenerateImageConfig(aspect_ratio=target_ratio, number_of_images=1)
                )
                img_bytes = img_res.generated_images[0].image_bytes
                
                with st.container(border=True):
                    c1, c2 = st.columns([0.7, 0.3])
                    c1.image(Image.open(io.BytesIO(img_bytes)), use_container_width=True)
                    c2.markdown(f"**생성 정보**\n\n- 모델: {st.session_state.selected_imagen_model}\n- 비율: {target_ratio}")
                    with c2.expander("프롬프트 보기"): st.write(final_prompt)
                st.balloons()
        except Exception as e:
            st.error(f"이미지 생성 실패: {e}")
