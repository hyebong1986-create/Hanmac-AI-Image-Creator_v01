import streamlit as st
import os
from google import genai
from google.genai import types
import requests
import io
import base64
from PIL import Image
import pdfplumber

# --- 1. 기능 함수 정의 (최신 규칙 적용) ---

# [수정 완료] 사용 가능한 Imagen 3 모델을 자동으로 찾아내는 똑똑한 함수
def get_available_imagen_model(api_key):
    if not api_key:
        return None, "API 키가 없습니다."
    
    try:
        # 최신 SDK 방식 클라이언트
        temp_client = genai.Client(api_key=api_key)
        available_models = []
        
        # 내 계정의 모델 목록을 싹 가져와서 'imagen'이 들어간 것만 골라냅니다.
        for m in temp_client.models.list():
            if "imagen" in m.name.lower():
                available_models.append(m.name)
        
        # 구글이 추천하는 최신 Imagen 3 순서대로 찾습니다.
        priority_models = [
            "imagen-3.0-generate-002", # 1순위: 가장 최신형
            "imagen-3.0-generate-001",
            "imagen-3",                # 별명
        ]
        
        for p_model in priority_models:
            for a_model in available_models:
                # 이름이 완전히 같거나, 풀네임에 우선순위 이름이 포함되면 당첨!
                if p_model == a_model or p_model in a_model:
                    return a_model, None
        
        # 우선순위 목록에 없어도, 찾은 게 있다면 그거라도 씁니다.
        if available_models:
            return available_models[0], None
            
        # 아예 못 찾았더라도 기본값으로 질러봅니다! (VIP 계정이니까요)
        return "imagen-3.0-generate-002", None
        
    except Exception:
        # 에러가 나도 일단 기본값으로 진행하게 합니다.
        return "imagen-3.0-generate-002", None


# [기존 유지] 사용 가능한 Gemini(텍스트) 모델을 찾는 함수
def get_available_gemini_model(api_key):
    if not api_key:
        return None, "API 키가 없습니다."
    
    try:
        temp_client = genai.Client(api_key=api_key)
        available_models = []
        # 'gemini'가 들어간 모델만 가져옵니다.
        for m in temp_client.models.list():
            if "gemini" in m.name:
                available_models.append(m.name)
        
        if not available_models:
            return None, "Gemini 모델을 찾을 수 없습니다."

        # 최신 Pro 모델 우선
        priority_models = [
            "gemini-2.0-pro", "gemini-1.5-pro",
            "gemini-2.0-flash", "gemini-1.5-flash"
        ]
        
        for p_model in priority_models:
            for a_model in available_models:
                if p_model in a_model:
                    return a_model, None
        
        return available_models[0], None
        
    except Exception as e:
        return None, f"Gemini 모델 목록 오류: {e}"


# --- 2. 환경 설정 및 디자인 가이드 ---

# 혜봉님이 만드신 '한맥 디자인 가이드'는 100% 그대로 보존했습니다! 🍌
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

ICON_A_GUIDE = """
[ICON SYSTEM - TYPE 1]
* Style: 3D isometric product render, high-detail modeling
* Material: Matte clay-texture + soft semi-gloss (not metallic)
* Lighting: Soft studio lighting, top-front key light, no harsh highlights
* Edges: Softly rounded geometric edges
"""

# 대시보드 레이아웃 및 스타일 설정
st.set_page_config(page_title="나노바나나 인포그래픽 엔진", layout="wide", page_icon="🍌")

# HTML/CSS 테마 주입 (혜봉님 커스텀 초록색 테마 그대로)
st.markdown("""
    <style>
    .stApp { background-color: #FAFAF8; }
    .main-title { font-size: 24px; font-weight: 700; color: #1a1a1a; margin-bottom: 5px; }
    .nanobana-badge { display: inline-block; padding: 2px 12px; border-radius: 99px; background: #edf7f3; border: 1px solid #a8dcc8; color: #266651; font-size: 12px; font-weight: 600; margin-bottom: 10px; }
    .flow-notice { background: #edf7f3; border: 1px solid #a8dcc8; border-radius: 10px; padding: 15px; color: #266651; font-size: 14px; margin-bottom: 20px; }
    div.stButton > button[kind="primary"] { background-color: #249473 !important; color: white !important; border: none !important; box-shadow: 0 2px 4px rgba(36,148,115,0.3); }
    div.stButton > button[kind="primary"]:hover { background-color: #266651 !important; }
    div.stButton > button[kind="secondary"] { background-color: #edf7f3 !important; color: #266651 !important; border: 1px solid #a8dcc8 !important; }
    div.stButton > button[kind="secondary"]:hover { border-color: #249473 !important; background-color: #f0fdf4 !important; }
    button[data-baseweb="tab"] { color: #555 !important; }
    button[aria-selected="true"] { color: #249473 !important; border-bottom-color: #249473 !important; }
    .summary-box { background: #ffffff; border-left: 5px solid #D0A98C; padding: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin: 10px 0; }
    </style>
    """, unsafe_allow_html=True)

# 세션 상태 초기화
if 'design_style' not in st.session_state: st.session_state.design_style = "Style A"
if 'icon_style' not in st.session_state: st.session_state.icon_style = "Icon A"
if 'gen_mode' not in st.session_state: st.session_state.gen_mode = "Strict"
if 'selected_gemini_model' not in st.session_state: st.session_state.selected_gemini_model = None
if 'selected_imagen_model' not in st.session_state: st.session_state.selected_imagen_model = None
if 'api_key' not in st.session_state: st.session_state.api_key = os.getenv("GEMINI_API_KEY")

# --- 3. 사이드바 레이아웃 ---
with st.sidebar:
    st.markdown("### 🔑 API 설정")
    
    # [새로운 기능] 라이브러리 버전 확인용 (디버깅)
    import importlib.metadata
    try:
        sdk_version = importlib.metadata.version('google-genai')
        st.caption(f"SDK 버전: `{sdk_version}` (0.4.0 이상 권장)")
    except:
        st.caption("SDK 버전을 확인할 수 없습니다.")

    # API 키 입력 필드
    user_input_api_key = st.text_input(
        "Gemini API Key",
        type="password",
        value=st.session_state.api_key if st.session_state.api_key else "",
        placeholder="AIza..."
    )
    if user_input_api_key != st.session_state.api_key:
        st.session_state.api_key = user_input_api_key
        # 키가 바뀌면 자동 선택된 모델들도 초기화!
        st.session_state.selected_gemini_model = None
        st.session_state.selected_imagen_model = None
        st.rerun()

    if st.session_state.api_key:
        st.success("✅ API 키가 입력되었습니다.")
        
        # 🌟 모델 자동 탐색 로직 가동!
        if not st.session_state.selected_gemini_model:
            with st.spinner("Gemini 모델 검색 중..."):
                model_name, _ = get_available_gemini_model(st.session_state.api_key)
                st.session_state.selected_gemini_model = model_name
        
        # [추가된 기능] VIP 전용 Imagen 3 모델 자동 탐색!
        if not st.session_state.selected_imagen_model:
            with st.spinner("Imagen 3 모델 확인 중..."):
                imagen_model, _ = get_available_imagen_model(st.session_state.api_key)
                st.session_state.selected_imagen_model = imagen_model

        if st.session_state.selected_gemini_model:
            st.info(f"🤖 Gemini: **{st.session_state.selected_gemini_model}**")
        if st.session_state.selected_imagen_model:
            st.info(f"🎨 Imagen: **{st.session_state.selected_imagen_model}**")
            
    else:
        st.warning("⚠️ Gemini API 키를 입력해주세요.")
    
    st.markdown("### 📂 원고 및 설정")
    uploaded_file = st.file_uploader("원고(PDF, TXT)를 여기에 끌어다 놓으세요", type=['pdf', 'txt'])
    manual_text = st.text_area("또는 직접 텍스트 입력", height=150, placeholder="여기에 내용을 입력하세요...")
    st.divider()
    
    st.markdown("### 📏 출력 크기 (mm → px)")
    dpi = st.selectbox("DPI 선택", [72, 96, 150, 300], index=2)
    col_w, col_h = st.columns(2)
    mm_w = col_w.number_input("가로(mm)", value=210) # A4 세로 기준
    mm_h = col_h.number_input("세로(mm)", value=297)
    
    px_w = int(mm_w * (dpi / 25.4))
    px_h = int(mm_h * (dpi / 25.4))
    st.info(f"결과 크기: {px_w} × {px_h} px")

# --- 4. 메인 화면 및 텍스트 추출 ---
st.markdown('<p class="main-title">🍌 나노바나나 디자인 엔진 (Imagen 3)</p>', unsafe_allow_html=True)
st.markdown('<span class="nanobana-badge">● BASE GUIDE 1 내장</span>', unsafe_allow_html=True)
st.write("제미나이(Imagen 3) 엔진을 사용하여 고품질 인포그래픽과 조감도를 생성합니다.")

# 세션 상태에 저장된 API 키로 메인 클라이언트 생성
client = genai.Client(api_key=st.session_state.api_key) if st.session_state.api_key else None

def extract_text(file):
    if file.type == "application/pdf":
        with pdfplumber.open(file) as pdf:
            return "".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    return file.read().decode("utf-8")

doc_content = ""
if uploaded_file: doc_content = extract_text(uploaded_file)
elif manual_text: doc_content = manual_text

# 요약 섹션
if doc_content and client:
    with st.container():
        st.markdown("### 📋 원고 핵심 요약")
        with st.spinner("문서 내용을 파악 중입니다..."):
            try:
                # [수정] Pro 모델 대신 우선순위에 따라 Pro/Flash 자동 선택
                gemini_model = st.session_state.selected_gemini_model or "gemini-1.5-flash"
                sum_res = client.models.generate_content(
                    model=gemini_model,
                    contents=f"다음 내용을 인포그래픽 제작을 위해 핵심만 3줄로 요약해줘: {doc_content[:2000]}"
                )
                st.markdown(f'<div class="summary-box">{sum_res.text}</div>', unsafe_allow_html=True)
            except:
                st.info("요약을 불러오지 못했습니다. 원고 내용은 정상 인식되었습니다.")

# --- 5. 생성 버튼 및 이미지 생성 (최종 핵심 수정) ---
st.divider()
if st.button("🚀 조감도 및 아이콘 생성", type="primary", use_container_width=True):
    # 각종 안전장치
    if not doc_content: st.error("⚠️ 원고를 먼저 입력해주세요!")
    elif not st.session_state.api_key: st.error("사이드바에서 API 키를 먼저 입력해주세요!")
    elif not st.session_state.selected_imagen_model: st.error("사용 가능한 Imagen 3 모델이 없습니다. 결제 설정을 확인하세요.")
    else:
        try:
            # 1. 제미나이에게 프롬프트 생성 요청 (한맥 가이드 적용)
            with st.spinner("나노바나나 엔진이 디자인 가이드를 적용 중..."):
                design_guide = DESIGN_A_GUIDE if st.session_state.design_style == "Style A" else f"DESIGN STYLE: {st.session_state.design_style}"
                icon_guide = ICON_A_GUIDE if st.session_state.icon_style == "Icon A" else f"ICON STYLE: {st.session_state.icon_style}"
                
                # Imagen 3 전용 고화질 프롬프트 요청문
                prompt_query = f"""
                {design_guide}
                {icon_guide}
                MODE: {st.session_state.gen_mode}
                CONTENT: {doc_content[:1500]}
                
                위 가이드를 엄격히 준수하여 Google Imagen 3 모델이 이해할 수 있는 고해상도 인포그래픽 생성용 영문 상세 프롬프트를 작성해줘. 
                추상적인 단어보다는 시각적인 배치, 질감, 색상 값을 구체적으로 기술할 것.
                """
                
                try:
                    gemini_model = st.session_state.selected_gemini_model or "gemini-1.5-flash"
                    response = client.models.generate_content(
                        model=gemini_model,
                        contents=prompt_query
                    )
                    final_prompt = response.text.strip()
                except Exception as e:
                    st.error(f"❌ Gemini 프롬프트 생성 오류: {e}")
                    st.stop()

            # 2. **대망의 Imagen 3 이미지 생성 (최종 핵심 수정 부분!)**
            with st.spinner("Imagen 3 엔진이 고해상도 이미지를 생성 중입니다... (약 90원 결제)"):
                try:
                    # [추가] 가로/세로 비율에 맞는 Imagen 3 전용 비율 매핑
                    ratio_val = px_w / px_h
                    target_ratio = "1:1" # 기본
                    if ratio_val > 1.5: target_ratio = "16:9" # 가로형
                    elif ratio_val > 1.1: target_ratio = "4:3"
                    elif ratio_val < 0.6: target_ratio = "9:16" # 세로형
                    elif ratio_val < 0.9: target_ratio = "3:4"

                    # 자동 선택된 최신 Imagen 3 모델 사용!
                    imagen_model = st.session_state.selected_imagen_model

                    # 🌟 [오타 박멸] 'client.models' (소문자) 확인 완료!
                    image_response = client.models.generate_image(
                        model=imagen_model,
                        prompt=final_prompt,
                        config=types.GenerateImageConfig(
                            aspect_ratio=target_ratio,
                            number_of_images=1, # 1장만 (돈 아껴야죠!)
                            output_mime_type='image/png'
                        )
                    )
                    # 결과물에서 바이트 데이터를 꺼냅니다.
                    img_bytes = image_response.generated_images[0].image_bytes
                    
                    # --- 5. 결과물 출력 ---
                    with st.container(border=True):
                        res_col1, res_col2 = st.columns([0.7, 0.3])
                        with res_col1:
                            st.image(Image.open(io.BytesIO(img_bytes)), use_container_width=True)
                        with res_col2:
                            st.markdown("### 📋 생성 정보 (Imagen 3)")
                            st.write(f"**모델:** {imagen_model}")
                            st.write(f"**모드:** {st.session_state.gen_mode}")
                            st.write(f"**디자인:** {st.session_state.design_style}")
                            st.write(f"**비율:** {target_ratio} (자동)")
                            with st.expander("생성 프롬프트 보기"):
                                st.write(final_prompt)
                    st.balloons() # 성공 세레모니!

                except Exception as img_e:
                    st.error(f"❌ 이미지 생성 중 오류가 발생했습니다: {img_e}")
                    # 결제 유도 메시지 추가 ㅋㅋㅋ
                    st.info("💡 Imagen 3는 구글 AI Studio에서 '유료 플랜(Pay-as-you-go)'으로 전환해야 사용 가능합니다. 결제 설정을 다시 확인해주세요.")

        except Exception as e:
            st.error(f"예상치 못한 오류가 발생했습니다: {e}")
