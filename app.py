import streamlit as st
import os
from google import genai
from google.genai import types
import requests
import io
import base64
from PIL import Image
import pdfplumber

# Function to get available Gemini model
def get_available_gemini_model(api_key):
    if not api_key:
        return None, "API 키가 없습니다."
    
    try:
        # 새로운 google-genai SDK 방식의 클라이언트 생성
        temp_client = genai.Client(api_key=api_key)

        available_models = []
        # 복잡한 권한 체크 다 빼고, 이름에 'gemini'가 들어간 것만 무조건 가져옵니다!
        for m in temp_client.models.list():
            if "gemini" in m.name:
                available_models.append(m.name)
        
        if not available_models:
            return None, "generateContent를 지원하는 Gemini 모델을 찾을 수 없습니다. API 키 또는 권한을 확인하세요."

        # Prioritize models
        # Order: 1.5-pro-latest, 1.5-pro, pro, 1.5-flash, flash
        priority_models = [
            "gemini-1.5-pro-latest", "gemini-1.5-pro", "gemini-pro",
            "gemini-1.5-flash", "gemini-flash"
        ]
        
        for p_model_alias in priority_models:
            for a_model_full_name in available_models:
                if p_model_alias in a_model_full_name:
                    return a_model_full_name, None # Found a suitable model
        
        # If no priority model found, return the first available one
        return available_models[0], None
        
    except Exception as e:
        return None, f"Gemini 모델 목록을 가져오는 중 오류 발생: {e}"

# --- 1. 환경 설정 ---

# 디자인 A를 위한 상세 가이드 정의
DESIGN_A_GUIDE = """
[BASE GUIDE - TYPE 1 (Layout & System Only)]
SYSTEM
* Information-first composition
* Diagram-style visual language
* Presentation board style
* Not artistic, not cinematic

PRIORITY
1. High readability priority
2. Balanced spacing and alignment
3. Clean structured layout
4. Strict color distribution

DESIGN
* White-dominant corporate infographic
* High whitespace ratio (70–80%)
* Clean geometric sans-serif placeholders for text areas
* No background color flooding

LAYOUT
* Follow given content hierarchy strictly
* Preserve grouping and sequence (do not rearrange meaning)
* Structured and connected flow lines joining panels to show grouping and sequence

COLOR
* Primary Accent (10–20%): Muted deep green (#249473)
* Secondary Accent (5–12%): Desaturated brown (#3E3523 to #604F32 range)
* Minimal Highlight (2–6%): Burnt orange (#CC5200)
* Base (65–80%): White and near-white

PANEL (GLASS-LIKE SYSTEM)
* Surface: Glass-like panels with near-white tint, very light transparency
* Edges: Defined rounded edges
* Glow: Localized glow only (small radius, low intensity, opacity ~10–20%)
* Shadow: Soft minimal shadow
* Gradient: Soft and controlled (2–3 colors only, low contrast)

FORBIDDEN: No neon, no sci-fi, no photoreal, no high-chroma pastel flood.
"""

# 아이콘 A를 위한 상세 가이드 정의
ICON_A_GUIDE = """
[ICON SYSTEM - TYPE 1]
* Style: 3D isometric product render, high-detail modeling
* Material: Matte clay-texture + soft semi-gloss (not metallic)
* Lighting: Soft studio lighting, top-front key light, no harsh highlights
* Edges: Softly rounded geometric edges
"""

API_KEY = os.getenv("GEMINI_API_KEY")

# 대시보드 레이아웃 및 스타일 설정
st.set_page_config(page_title="나노바나나 인포그래픽 엔진", layout="wide", page_icon="🍌")

# HTML 테마를 Streamlit에 주입
st.markdown("""
    <style>
    .stApp { background-color: #FAFAF8; }
    .main-title { font-size: 24px; font-weight: 700; color: #1a1a1a; margin-bottom: 5px; }
    .nanobana-badge { display: inline-block; padding: 2px 12px; border-radius: 99px; background: #edf7f3; border: 1px solid #a8dcc8; color: #266651; font-size: 12px; font-weight: 600; margin-bottom: 10px; }
    .flow-notice { background: #edf7f3; border: 1px solid #a8dcc8; border-radius: 10px; padding: 15px; color: #266651; font-size: 14px; margin-bottom: 20px; }
    
    /* 선택된 버튼 스타일 (Primary) */
    div.stButton > button[kind="primary"] { background-color: #249473 !important; color: white !important; border: none !important; box-shadow: 0 2px 4px rgba(36,148,115,0.3); }
    div.stButton > button[kind="primary"]:hover { background-color: #266651 !important; }
    
    /* 비선택 버튼 스타일 (Secondary) */
    div.stButton > button[kind="secondary"] { background-color: #edf7f3 !important; color: #266651 !important; border: 1px solid #a8dcc8 !important; }
    div.stButton > button[kind="secondary"]:hover { border-color: #249473 !important; background-color: #f0fdf4 !important; }
    
    /* 선택된 탭 강조색 */
    button[data-baseweb="tab"] { color: #555 !important; }
    button[aria-selected="true"] { color: #249473 !important; border-bottom-color: #249473 !important; }
    
    .summary-box { background: #ffffff; border-left: 5px solid #D0A98C; padding: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin: 10px 0; }
    </style>
    """, unsafe_allow_html=True)

# 세션 상태 초기화 (버튼 선택값을 저장)
if 'design_style' not in st.session_state:
    st.session_state.design_style = "Style A"
if 'icon_style' not in st.session_state:
    st.session_state.icon_style = "Icon A"
if 'gen_mode' not in st.session_state:
    st.session_state.gen_mode = "Strict"
# Gemini 모델 선택 상태
if 'selected_gemini_model' not in st.session_state:
    st.session_state.selected_gemini_model = None
if 'gemini_model_error' not in st.session_state:
    st.session_state.gemini_model_error = None
# API 키를 세션 상태에 저장 (환경 변수 우선)
if 'api_key' not in st.session_state:
    st.session_state.api_key = os.getenv("GEMINI_API_KEY")

# --- 2. 사이드바: PDF 문서 업로드 ---
with st.sidebar:
    st.markdown("### 🔑 API 설정")
    
    # 라이브러리 버전 확인용 (디버깅)
    import importlib.metadata
    sdk_version = importlib.metadata.version('google-genai')
    st.caption(f"SDK 버전: `{sdk_version}` (0.4.0 이상 권장)")

    # API 키 입력 필드 (세션 상태와 연동)
    user_input_api_key = st.text_input(
        "Gemini API Key",
        type="password",
        value=st.session_state.api_key if st.session_state.api_key else "", # 기존 값 채우기
        placeholder="AIza..."
    )
    if user_input_api_key != st.session_state.api_key:
        st.session_state.api_key = user_input_api_key
        st.session_state.selected_gemini_model = None  # 키 변경 시 모델 초기화
        st.rerun()

    if st.session_state.api_key:
        st.success("✅ API 키가 입력되었습니다.")
        
        # 모델 자동 선택 로직 호출
        if not st.session_state.selected_gemini_model:
            with st.spinner("사용 가능한 Gemini 모델 검색 중..."):
                model_name, error = get_available_gemini_model(st.session_state.api_key)
                if model_name:
                    st.session_state.selected_gemini_model = model_name
                    st.session_state.gemini_model_error = None
                else:
                    st.session_state.gemini_model_error = error
        
        if st.session_state.selected_gemini_model:
            st.info(f"🤖 모델: **{st.session_state.selected_gemini_model}**")
        elif st.session_state.gemini_model_error:
            st.error(f"❌ {st.session_state.gemini_model_error}")
    else:
        st.warning("⚠️ Gemini API 키를 입력해주세요.")
    
    st.markdown("### 📂 원고 및 설정")
    uploaded_file = st.file_uploader("원고(PDF, TXT)를 여기에 끌어다 놓으세요", type=['pdf', 'txt'])
    manual_text = st.text_area("또는 직접 텍스트 입력", height=150, placeholder="파일이 없을 경우 여기에 내용을 입력하세요...")
    st.divider()
    
    st.markdown("### 📏 출력 크기 (mm → px)")
    dpi = st.selectbox("DPI 선택", [72, 96, 150, 200, 300, 350], index=3)
    col_w, col_h = st.columns(2)
    mm_w = col_w.number_input("가로(mm)", value=210)
    mm_h = col_h.number_input("세로(mm)", value=297)
    
    # 픽셀 계산 로직 (HTML 기능 이식)
    px_w = int(mm_w * (dpi / 25.4))
    px_h = int(mm_h * (dpi / 25.4))
    st.info(f"결과 크기: {px_w} × {px_h} px")

# Gemini 클라이언트 설정 (키가 입력된 경우만)
client = genai.Client(api_key=st.session_state.api_key) if st.session_state.api_key else None

# --- 3. 메인 화면 ---
st.markdown('<p class="main-title">🍌 나노바나나 디자인 엔진 (Imagen 3)</p>', unsafe_allow_html=True)
st.markdown('<span class="nanobana-badge">● BASE GUIDE 1 내장</span>', unsafe_allow_html=True)
st.write("제미나이(Imagen 3) 엔진을 사용하여 고품질 인포그래픽과 조감도를 생성합니다.")

st.markdown("""
    <div class="flow-notice">
    <strong>사용 흐름:</strong> 원고 업로드 → 모드 및 디자인 선택 → 생성 버튼 클릭
    </div>
    """, unsafe_allow_html=True)

with st.container(border=True):
    # 🎯 생성 모드 섹션
    st.markdown("#### 🎯 생성 모드")
    m_col1, m_col2 = st.columns(2)
    if m_col1.button("Strict (구조 보존)", use_container_width=True, 
                     type="primary" if st.session_state.gen_mode == "Strict" else "secondary"):
        st.session_state.gen_mode = "Strict"
        st.rerun()
    if m_col2.button("Generative (재구성)", use_container_width=True, 
                     type="primary" if st.session_state.gen_mode == "Generative" else "secondary"):
        st.session_state.gen_mode = "Generative"
        st.rerun()
    st.caption(f"현재 모드: **{st.session_state.gen_mode}** (Strict는 원고 구조를 보존합니다)")

    st.divider()

    # 🎨 디자인 컨셉 섹션
    st.markdown("#### 🎨 디자인 컨셉")
    d1, d2, d3 = st.columns(3)
    if d1.button("디자인 A (한맥_저명도+고채도)", use_container_width=True, 
                 type="primary" if st.session_state.design_style == "Style A" else "secondary"):
        st.session_state.design_style = "Style A"
        st.rerun()
    if d2.button("디자인 B", use_container_width=True, 
                 type="primary" if st.session_state.design_style == "Style B" else "secondary"):
        st.session_state.design_style = "Style B"
        st.rerun()
    if d3.button("디자인 C", use_container_width=True, 
                 type="primary" if st.session_state.design_style == "Style C" else "secondary"):
        st.session_state.design_style = "Style C"
        st.rerun()
    st.caption(f"현재 디자인: **{st.session_state.design_style}**")

    st.divider()

    # 💎 아이콘 스타일 섹션
    st.markdown("#### 💎 아이콘 스타일")
    i1, i2, i3 = st.columns(3)
    if i1.button("아이콘 A (3D Isometric)", use_container_width=True, 
                 type="primary" if st.session_state.icon_style == "Icon A" else "secondary"):
        st.session_state.icon_style = "Icon A"
        st.rerun()
    if i2.button("아이콘 B", use_container_width=True, 
                 type="primary" if st.session_state.icon_style == "Icon B" else "secondary"):
        st.session_state.icon_style = "Icon B"
        st.rerun()
    if i3.button("아이콘 C", use_container_width=True, 
                 type="primary" if st.session_state.icon_style == "Icon C" else "secondary"):
        st.session_state.icon_style = "Icon C"
        st.rerun()
    st.caption(f"현재 아이콘: **{st.session_state.icon_style}**")

st.divider()

# --- 4. 텍스트 추출 및 AI 연동 로직 ---
def extract_text(file):
    if file.type == "application/pdf":
        with pdfplumber.open(file) as pdf:
            # 모든 페이지의 텍스트를 하나로 합칩니다.
            return "".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    return file.read().decode("utf-8")

doc_content = ""
if uploaded_file:
    doc_content = extract_text(uploaded_file)
elif manual_text:
    doc_content = manual_text

if doc_content:
    
    # 문서 요약 표시
    with st.container():
        st.markdown("### 📋 원고 핵심 요약")
        if client:
            if not st.session_state.selected_gemini_model:
                st.error("사용 가능한 Gemini 모델이 설정되지 않았습니다. API 키를 다시 확인해주세요.")
                st.stop()
                
            with st.spinner("문서 내용을 파악 중입니다..."):
                try:
                    sum_res = client.models.generate_content(  # 요약 기능
                        model=st.session_state.selected_gemini_model,
                        contents=f"다음 내용을 인포그래픽 제작을 위해 핵심만 3줄로 요약해줘: {doc_content[:2000]}"
                    )
                    st.markdown(f'<div class="summary-box">{sum_res.text}</div>', unsafe_allow_html=True)
                except:
                    st.info("요약을 불러오지 못했습니다. 원고 내용은 정상적으로 인식되었습니다.")
        else:
            st.warning("API 키를 입력하면 문서 요약이 표시됩니다.")

# 이미지 생성 버튼 (항상 표시되도록 조건문 밖으로 이동)
if st.button("🚀 조감도 및 아이콘 생성", type="primary"):
    if not doc_content:
        st.error("⚠️ 원고를 업로드하거나 '직접 텍스트 입력' 칸에 내용을 넣어주세요.")
    elif not st.session_state.api_key:
        st.error("사이드바에서 Gemini API 키를 먼저 입력해주세요!")
    elif not st.session_state.selected_gemini_model:
        st.error("사용 가능한 Gemini 모델이 없습니다. API 키 권한을 확인하세요.")
    elif st.session_state.design_style == "선택 전":
        st.warning("디자인 스타일을 먼저 선택해주세요!")
    else:
        try:
            # 1. 제미나이에게 프롬프트 생성 요청
            with st.spinner("나노바나나 엔진이 디자인 가이드를 적용 중..."):
                design_guide = DESIGN_A_GUIDE if st.session_state.design_style == "Style A" else f"DESIGN STYLE: {st.session_state.design_style}"
                icon_guide = ICON_A_GUIDE if st.session_state.icon_style == "Icon A" else f"ICON STYLE: {st.session_state.icon_style}"
                
                prompt_query = f"""
                {design_guide}
                {icon_guide}
                MODE: {st.session_state.gen_mode}
                CONTENT: {doc_content[:1500]}
                
                위 가이드를 엄격히 준수하여 Google Imagen 3 모델이 이해할 수 있는 고해상도 인포그래픽 생성용 영문 상세 프롬프트를 작성해줘. 
                추상적인 단어보다는 시각적인 배치, 질감, 색상 값을 구체적으로 기술할 것.
                """
                
                try:
                    response = client.models.generate_content(
                        model=st.session_state.selected_gemini_model,
                        contents=prompt_query
                    )
                    final_prompt = response.text.strip()
                except Exception as gemini_e:
                    st.error(f"❌ Gemini 프롬프트 생성 오류: {gemini_e}")
                    st.stop()

            # 2. Imagen 3로 이미지 생성 (Forge 대체)
            with st.spinner("Imagen 3 엔진이 고해상도 이미지를 생성 중입니다..."):
                try:
                    # 비율 계산 (Imagen 3 지원 형식으로 매핑)
                    ratio_val = px_w / px_h
                    target_ratio = "1:1"
                    if ratio_val > 1.5: target_ratio = "16:9"
                    elif ratio_val > 1.1: target_ratio = "4:3"
                    elif ratio_val < 0.6: target_ratio = "9:16"
                    elif ratio_val < 0.9: target_ratio = "3:4"

                    image_response = client.models.generate_image(
                        model='imagen-3',
                        prompt=final_prompt,
                        config=types.GenerateImageConfig(
                            aspect_ratio=target_ratio,
                            number_of_images=1,
                            output_mime_type='image/png'
                        )
                    )
                    img_bytes = image_response.generated_images[0].image_bytes
                    
                # --- 5. 결과물 출력 ---
                with st.container(border=True):
                    res_col1, res_col2 = st.columns([0.7, 0.3])
                    with res_col1:
                        st.image(Image.open(io.BytesIO(img_bytes)), use_container_width=True)
                    with res_col2:
                        st.markdown("### 📋 생성 정보 (Imagen 3)")
                        st.write(f"**모드:** {st.session_state.gen_mode}")
                        st.write(f"**디자인:** {st.session_state.design_style}")
                        st.write(f"**비율:** {target_ratio}")
                        with st.expander("생성 프롬프트 보기"):
                            st.write(final_prompt)
                st.balloons()
            except Exception as img_e:
                st.error(f"이미지 생성 중 오류가 발생했습니다: {img_e}")

        except Exception as e:
            st.error(f"예상치 못한 오류가 발생했습니다: {e}")
