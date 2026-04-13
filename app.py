import time
import re
import os
import io

import streamlit as st
import pdfplumber
from PIL import Image

from google import genai
from google.genai import types

# =========================
# 기본 설정
# =========================
DESIGN_GUIDES = {
    "Style A": "[DESIGN STYLE: HANMAC A] SYSTEM: Information-first / Diagram-style. COLOR: Primary #249473 / Secondary #3E3523 / Base White. PANEL: Glass-like, rounded edges.",
    "Style B": "[DESIGN STYLE: MODERN B] Clean tech-minimalist, blue-scale accent, sharp edges.",
    "Style C": "[DESIGN STYLE: CLASSIC C] Paper-texture, serif accents, warm-tone palette."
}

ICON_GUIDES = {
    "Icon A": "[ICON STYLE: 3D CLAY] 3D isometric product render, Matte clay-texture, soft lighting.",
    "Icon B": "[ICON STYLE: FLAT LINE] 2D flat vector icons, thick lines.",
    "Icon C": "[ICON STYLE: GLASS] Frosted glass 3D icons, refractive transparency."
}

STRICT_MODE_LOGIC = """
[MODE: STRICT]
* No structure change / No content change / No summary
* Layout fidelity is highest priority
* Center composition with balanced whitespace frame
"""

GENERATIVE_MODE_LOGIC = """
[MODE: GENERATIVE]
* analyze and summarize the content
* extract key points and structure them into clear sections
* create logical grouping and hierarchy
* optimize for infographic readability
* keep structure simple and organized (3–5 sections recommended)
* maintain clarity and balance over completeness
"""

# =========================
# 유틸 
# =========================
def init_session():
    defaults = {
        "api_key": os.getenv("GEMINI_API_KEY", ""), "gen_mode": "Strict", 
        "design_style": "Style A", "icon_style": "Icon A", 
        "summary_text": "", "final_prompt": "", "doc_content": "", "used_image_model": ""
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

def get_client():
    api_key = st.session_state.get("api_key", "").strip()
    if not api_key: return None
    return genai.Client(api_key=api_key)

def safe_pdf_extract(uploaded_file):
    text_chunks = []
    uploaded_file.seek(0)
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip(): text_chunks.append(page_text)
    return "\n".join(text_chunks).strip()

def safe_text_extract(uploaded_file):
    uploaded_file.seek(0)
    raw = uploaded_file.read()
    for enc in ("utf-8", "cp949", "euc-kr"):
        try: return raw.decode(enc)
        except: continue
    return raw.decode("utf-8", errors="ignore")

def mm_to_px(mm_value, dpi): return int(mm_value * (dpi / 25.4))

@st.cache_resource(ttl=3600)
def get_dynamic_model_list(_client, mode="text"):
    try:
        model_list = _client.models.list()
        keyword = "flash" if mode == "text" else "imagen"
        valid_names = [m.name.split('/')[-1] for m in model_list if keyword in m.name.lower()]
        valid_names.sort(key=lambda x: [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', x)], reverse=True)
        if not valid_names: raise ValueError("사용 가능한 모델이 없습니다.")
        return valid_names
    except Exception as e:
        raise RuntimeError(f"명단 확보 실패: {e}")

# [핵심 수술 1] Temperature=0.0 으로 고정하여 매번 똑같은 포맷 유지
def call_text_model(client, prompt, max_retries=2):
    models = get_dynamic_model_list(client, mode="text")
    last_error = None
    for model_name in models:
        for attempt in range(1, max_retries + 1):
            try:
                # config에 temperature=0.0 옵션을 주어 창의성을 완전히 제거합니다.
                res = client.models.generate_content(
                    model=model_name, 
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.0)
                )
                return (res.text or "").strip()
            except Exception as e:
                last_error = e
                err_text = str(e).lower()
                if "404" in err_text: break 
                if "503" in err_text or "429" in err_text or "quota" in err_text:
                    if attempt < max_retries: time.sleep(1.5); continue
                    else: break
                break
    raise RuntimeError(f"엔진 오류: {last_error}")

# [핵심 수술 2] 무조건 지켜야 하는 '절대 마크다운 양식(Template)' 강제
def build_summary_prompt(doc_content, mode):
    src = doc_content[:4000]
    
    if mode == "Strict":
        return f"""
당신은 원고의 내용을 절대 바꾸지 않고 그대로 추출하는 텍스트 포맷터입니다.
아래 지침과 [절대 양식]을 반드시 따르세요.

{STRICT_MODE_LOGIC}

[요구사항]
- 원고의 문장, 단어, 구조를 절대 요약하거나 재구성(Summarize)하지 마십시오.
- 디자이너가 바로 복사/붙여넣기 할 수 있도록 원래 문장들을 100% 살리세요.

[절대 양식 - 이 형태를 무조건 유지할 것]
## 📌 [원고의 메인 타이틀]

### 🔹 핵심 내용
- [원고의 문장 1 그대로]
- [원고의 문장 2 그대로]
- [원고의 문장 3 그대로]

### 📊 강조 포인트 (해당 시)
- [원고의 데이터나 중요한 문장]

원고:
{src}
""".strip()

    else:
        return f"""
당신은 방대한 원고를 완벽하게 분석하고 구조화하는 천재 에디터입니다.
아래 지침과 [절대 양식]을 반드시 따르세요.

{GENERATIVE_MODE_LOGIC}

[요구사항]
- 핵심 포인트와 흐름을 논리적으로 그룹화하여 읽기 쉽게 3~5개 섹션으로 다듬을 것.

[절대 양식 - 이 형태를 무조건 유지할 것]
## 📌 [새롭게 뽑아낸 메인 타이틀]

### 🔹 섹션 1: [섹션 제목]
- [요약된 핵심 포인트 1]
- [요약된 핵심 포인트 2]

### 🔹 섹션 2: [섹션 제목]
- [요약된 핵심 포인트 1]
- [요약된 핵심 포인트 2]

### 📊 핵심 데이터 / 결론
- [가장 중요한 숫자나 결론 1문장]

원고:
{src}
""".strip()

def build_image_prompt_prompt(doc_content, design_style, icon_style, mode):
    selected_design = DESIGN_GUIDES.get(design_style, "")
    selected_icon = ICON_GUIDES.get(icon_style, "")
    mode_logic = STRICT_MODE_LOGIC if mode == "Strict" else GENERATIVE_MODE_LOGIC
    src = doc_content[:2000]
    
    return f"""
Create a highly professional, fully-designed infographic presentation board.
Layout must include beautiful text block areas, titles, and 3D UI elements.
(It is OK to generate dummy text/lorem ipsum, as the layout structure is the primary goal).

Execution Logic:
{mode_logic}

Style instructions:
{selected_design}
{selected_icon}

Theme based on: {src}
Write in English only. Return prompt only. Focus on visual hierarchy, empty spaces for typography, and premium corporate aesthetics.
""".strip()

def build_image_response(client, model_name, prompt, aspect_ratio):
    # 구글 최신 SDK 문법에 맞게 딕셔너리 대신 객체(Config)를 명시적으로 사용합니다.
    if "imagen" in model_name.lower():
        res = client.models.generate_images(
            model=model_name, 
            prompt=prompt, 
            config=types.GenerateImagesConfig(
                number_of_images=1, 
                aspect_ratio=aspect_ratio
            )
        )
        if not res.generated_images:
            raise ValueError("응답은 왔으나 이미지가 비어있습니다. (구글 안전 필터에 차단되었을 확률이 높음)")
        return Image.open(io.BytesIO(res.generated_images[0].image_bytes)), model_name
        
    # 만약 이미지 전용 모델이 아닐 경우 텍스트 모델의 멀티모달 기능 사용 시도
    res = client.models.generate_content(
        model=model_name, 
        contents=prompt, 
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
    )
    for c in getattr(res, "candidates", []):
        for p in getattr(getattr(c, "content", None), "parts", []):
            if getattr(p, "inline_data", None): 
                return Image.open(io.BytesIO(p.inline_data.data)), model_name
    raise ValueError("이 모델은 이미지를 뱉어내지 못했습니다.")

def generate_image(client, prompt, aspect_ratio):
    errors = []
    try:
        models = get_dynamic_model_list(client, mode="image")
    except Exception as e:
        raise RuntimeError(f"이미지 모델 명단을 가져오지 못했습니다: {e}")
        
    for model_name in models:
        try: 
            return build_image_response(client, model_name, prompt, aspect_ratio)
        except Exception as e: 
            # 어떤 모델이 무슨 이유로 뻗었는지 에러 로그를 낱낱이 수집합니다.
            errors.append(f"[{model_name}] 실패 이유: {str(e)}")
            continue
            
    # 화면에 숨김없이 모든 에러를 터트립니다.
    error_details = "\n".join(errors)
    raise RuntimeError(f"모든 이미지 모델이 렌더링에 실패했습니다. 상세 원인:\n{error_details}")


# =========================
# UI 
# =========================
st.set_page_config(page_title="나노바나나 디자인 엔진", page_icon="🍌", layout="wide")
init_session()

st.markdown("""
<style>
.stApp { background-color: #FAFAF8; }
.main-title { font-size: 26px; font-weight: 700; color: #1a1a1a; }
div.stButton > button[kind="primary"] { background-color: #249473 !important; color: white !important; font-weight: bold; border: none; }
.summary-box { background: #ffffff; border-left: 5px solid #249473; padding: 25px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
.small-muted { color: #666; font-size: 13px; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🔑 API 설정")
    input_key = st.text_input("Gemini API Key", type="password", value=st.session_state.api_key)
    if input_key != st.session_state.api_key:
        st.session_state.api_key = input_key
        st.rerun()

    if st.session_state.api_key:
        try:
            test_client = genai.Client(api_key=st.session_state.api_key)
            test_client.models.list()
            st.success("✅ API 키 인증 성공")
        except Exception as e: st.error(f"❌ API 키 인증 실패: {e}")
    else: st.warning("⚠️ API 키를 입력해주세요.")

    st.divider()
    st.markdown("### 📏 출력 크기 (mm → px)")
    dpi = st.selectbox("DPI 선택", [72, 96, 150, 300], index=2)
    mm_w = st.number_input("가로(mm)", value=210)
    mm_h = st.number_input("세로(mm)", value=297)
    px_w, px_h = mm_to_px(mm_w, dpi), mm_to_px(mm_h, dpi)
    st.info(f"계산 결과: {px_w} × {px_h} px")
    st.divider()
    up_file = st.file_uploader("파일 업로드", type=["pdf", "txt"])
    manual_text = st.text_area("직접 입력", height=180)

st.markdown('<p class="main-title">🍌 나노바나나 디자인 엔진 (Format Lock Edition)</p>', unsafe_allow_html=True)

with st.container(border=True):
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Strict (구조 보존)", use_container_width=True, type="primary" if st.session_state.gen_mode == "Strict" else "secondary"): st.session_state.gen_mode = "Strict"
        st.caption("원고의 문장 구조를 건드리지 않고 최대한 유지합니다.")
    with c2:
        if st.button("Generative (재구성)", use_container_width=True, type="primary" if st.session_state.gen_mode == "Generative" else "secondary"): st.session_state.gen_mode = "Generative"
        st.caption("AI가 3~5개 섹션으로 요약 및 재구성합니다.")

    st.divider()
    st.markdown("#### 🎨 디자인 컨셉")
    d1, d2, d3 = st.columns(3)
    for i, (col, label) in enumerate(zip([d1, d2, d3], ["디자인 A (한맥)", "디자인 B", "디자인 C"])):
        style_name = f"Style {chr(65+i)}"
        if col.button(label, use_container_width=True, type="primary" if st.session_state.design_style == style_name else "secondary"): st.session_state.design_style = style_name

    st.divider()
    st.markdown("#### 💎 아이콘 스타일")
    i1, i2, i3 = st.columns(3)
    for i, (col, label) in enumerate(zip([i1, i2, i3], ["아이콘 A (3D)", "아이콘 B", "아이콘 C"])):
        icon_name = f"Icon {chr(65+i)}"
        if col.button(label, use_container_width=True, type="primary" if st.session_state.icon_style == icon_name else "secondary"): st.session_state.icon_style = icon_name


# =========================
# 문서 로드 및 실행
# =========================
doc_content = ""
if up_file:
    try: doc_content = safe_pdf_extract(up_file) if up_file.name.lower().endswith(".pdf") else safe_text_extract(up_file)
    except Exception as e: st.error(f"파일 읽기 실패: {e}")
elif manual_text.strip(): doc_content = manual_text.strip()

if doc_content:
    with st.expander("📄 원고 미리보기"):
        st.text_area("추출된 원고", value=doc_content[:3000], height=220, disabled=True)

client = get_client()

if not st.session_state.api_key:
    st.warning("사이드바에 Gemini API Key를 먼저 넣어줘.")
elif not doc_content:
    st.info("PDF 또는 TXT 파일을 올리거나 직접 원고를 입력해줘.")
else:
    if st.button("✨ 1단계: 원고 분석 및 마크다운 정리", use_container_width=True):
        try:
            with st.spinner(f"[{st.session_state.gen_mode} 모드] 마크다운 포맷 고정 렌더링 중..."):
                st.session_state.summary_text = call_text_model(client, build_summary_prompt(doc_content, st.session_state.gen_mode))
                st.session_state.final_prompt = call_text_model(client, build_image_prompt_prompt(doc_content, st.session_state.design_style, st.session_state.icon_style, st.session_state.gen_mode))
        except Exception as e: st.error(f"1단계 실패: {e}")

    if st.session_state.summary_text:
        st.markdown(f'<div class="summary-box">', unsafe_allow_html=True)
        st.markdown(f"### 📝 {st.session_state.gen_mode} 모드 브리핑 노트")
        st.markdown(st.session_state.summary_text)
        st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.final_prompt:
        st.write("") 
        if st.button("🚀 2단계: 풀 레이아웃 이미지 생성 (통째로 렌더링)", type="primary", use_container_width=True):
            try:
                with st.spinner("아름다운 레이아웃을 디자인 중입니다..."):
                    aspect_ratio = "16:9" if px_w > px_h else "3:4" if px_w < px_h else "1:1"
                    base_img, used_image_model = generate_image(client=client, prompt=st.session_state.final_prompt, aspect_ratio=aspect_ratio)
                    st.session_state.used_image_model = used_image_model

                    final_img = base_img.resize((px_w, px_h))
                    st.image(final_img, use_container_width=True)
                    st.caption(f"사용된 이미지 모델: {used_image_model}")

                    buf = io.BytesIO()
                    final_img.save(buf, format="PNG")
                    st.download_button("PNG 다운로드", data=buf.getvalue(), file_name="nanobanana_layout.png", mime="image/png")
            except Exception as e: st.error(f"2단계 실패: {e}")
