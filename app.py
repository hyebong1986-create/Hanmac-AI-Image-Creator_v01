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
# 1. 디자인 시스템 (혜봉님의 마스터 가이드 A 전문 보존)
# =========================
STYLE_A_PROMPT = """
[BASE GUIDE - TYPE 1 (Layout & System Only)]

SYSTEM
* Information-first composition / Diagram-style visual language
* Presentation board style / Not artistic, not cinematic

PRIORITY
1. High readability priority / 2. Balanced spacing and alignment
3. Clean structured layout / 4. Strict color distribution

DESIGN
* White-dominant corporate infographic / High whitespace ratio (70–80%)
* Clean geometric sans-serif placeholders for text areas / No background color flooding

LAYOUT
* Follow given content hierarchy strictly / Preserve grouping and sequence (do not rearrange meaning)
* Structured and connected flow lines joining panels to show grouping and sequence

COLOR
* Primary Accent (10–20%): Muted deep green (#249473)
  - Low saturation, slightly dark tone. Use strictly for the distinct dark title bars at the top of core panels and main flow lines.
* Secondary Accent (5–12%): Desaturated brown (#3E3523 to #604F32 range)
  - Use strictly for the sub-panel title bars within main panels and comparison axes.
* Minimal Highlight (2–6%): Burnt orange (#CC5200)
  - Use for micro focal points only.
* Base (65–80%): White and near-white
  - Dominant background and panel bodies.

PANEL (GLASS-LIKE SYSTEM)
* Surface: Glass-like panels with near-white tint, very light transparency
* Edges: Defined rounded edges
* Glow: Localized glow only (small radius, low intensity, opacity ~10–20%, focused only on edges of dark title bars or connection points)
* Shadow: Soft minimal shadow (short distance, low blur, very shallow depth, just enough to make panels float)
* Gradient: Soft and controlled (2–3 colors only, low contrast, no spotlight effect)

FORBIDDEN
* No neon lighting, no sci-fi cinematic mood, no dramatic lighting, no high contrast lighting
* No photoreal rendering, no glossy reflections, no heavy texture, no exaggerated 3D depth
* No full-canvas mint wash, no high-chroma pastel flood
""".strip()

DESIGN_GUIDES = {
    "Style A": STYLE_A_PROMPT,
    "Style B": "[STYLE: MODERN B] Clean tech-minimalist, blue accent theme.",
    "Style C": "[STYLE: CLASSIC C] Warm tones, elegant serif typography feel."
}

# =========================
# 2. 엔진 유틸리티 (503 에러 우회용 다중 모델 로직)
# =========================
def init_session():
    defaults = {
        "api_key": "", "gen_mode": "Strict", "design_style": "Style A", 
        "summary_text": "", "final_prompt": "", "doc_content": "", "design_instruction": ""
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

def get_client():
    if not st.session_state.api_key: return None
    return genai.Client(api_key=st.session_state.api_key)

def call_text_model_with_fallback(client, prompt):
    # 서버 체증(503) 발생 시 순차적으로 시도할 모델 리스트
    target_models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    last_error = None

    for model_name in target_models:
        try:
            res = client.models.generate_content(
                model=model_name, 
                contents=prompt, 
                config=types.GenerateContentConfig(temperature=0.0)
            )
            return (res.text or "").strip(), model_name
        except Exception as e:
            last_error = e
            if "503" in str(e) or "quota" in str(e).lower():
                continue # 다음 모델로 시도
            break
    raise RuntimeError(f"모든 엔진이 응답하지 않습니다. 마지막 오류: {last_error}")

def generate_multimodal_image_with_fallback(client, prompt):
    # 노트북LM 기능을 수행하기 위해 이미지 생성이 가능한 모델 리스트
    target_models = ["gemini-2.0-flash", "gemini-1.5-flash"]
    
    for model_name in target_models:
        try:
            res = client.models.generate_content(
                model=model_name, 
                contents=prompt, 
                config=types.GenerateContentConfig(response_modalities=["IMAGE"])
            )
            for part in res.candidates[0].content.parts:
                if part.inline_data:
                    return Image.open(io.BytesIO(part.inline_data.data)), model_name
        except:
            continue
            
    # 최후의 수단: 이미지 전용 모델 Imagen
    res = client.models.generate_images(model="imagen-3", prompt=prompt, config=types.GenerateImagesConfig(number_of_images=1))
    return Image.open(io.BytesIO(res.generated_images[0].image.image_bytes)), "imagen-3"

# =========================
# 3. UI 구성 (한맥 그린 CSS 고정)
# =========================
st.set_page_config(page_title="나노바나나 엔진", page_icon="🍌", layout="wide")
init_session()

st.markdown(f"""
<style>
    .stApp {{ background-color: #FAFAF8; }}
    button[kind="primary"] {{ background-color: #249473 !important; border-color: #249473 !important; color: white !important; font-weight: bold !important; }}
    button[kind="primary"]:hover {{ background-color: #1e7d61 !important; }}
    .summary-box {{ background: #ffffff; border-left: 5px solid #249473; padding: 25px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🔑 API 설정")
    st.session_state.api_key = st.text_input("Gemini API Key", type="password", value=st.session_state.api_key)
    st.divider()
    mm_w, mm_h = st.number_input("가로(mm)", value=210), st.number_input("세로(mm)", value=297)
    px_w, px_h = int(mm_w * (150 / 25.4)), int(mm_h * (150 / 25.4))
    st.divider()
    up_file = st.file_uploader("파일 업로드", type=["pdf", "txt"])
    manual_text = st.text_area("📄 원고 직접 입력", height=150)
    st.session_state.design_instruction = st.text_area("🎨 디자인 추가 지시사항")

st.markdown('# 🍌 나노바나나 디자인 엔진 (NotebookLM Master Ed.)')

with st.container(border=True):
    st.markdown("#### ⚙️ 디자인 시스템 설정")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Strict (구조 보존)", use_container_width=True, type="primary" if st.session_state.gen_mode == "Strict" else "secondary"): st.session_state.gen_mode = "Strict"
    with c2:
        if st.button("Generative (재구성)", use_container_width=True, type="primary" if st.session_state.gen_mode == "Generative" else "secondary"): st.session_state.gen_mode = "Generative"

    st.divider()
    d1, d2, d3 = st.columns(3)
    for i, (col, label) in enumerate(zip([d1, d2, d3], ["디자인 A (한맥)", "디자인 B", "디자인 C"])):
        s_name = f"Style {chr(65+i)}"
        if col.button(label, use_container_width=True, type="primary" if st.session_state.design_style == s_name else "secondary"): st.session_state.design_style = s_name

doc_content = ""
if up_file:
    with pdfplumber.open(up_file) as pdf: doc_content = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
elif manual_text.strip(): doc_content = manual_text.strip()

client = get_client()

if not st.session_state.api_key:
    st.error("⚠️ 사이드바 맨 위에 **Gemini API Key**를 입력해 주세요.")
elif not doc_content:
    st.warning("📄 분석할 **원고**를 넣어주세요.")
else:
    # 1단계: 분석
    if st.button("✨ 1단계: 원고 분석 및 프롬프트 개조", use_container_width=True, type="primary"):
        with st.spinner("서버 상태 확인 및 원고 분석 중..."):
            try:
                text_res, model_used = call_text_model_with_fallback(client, f"원고를 인포그래픽용 한글 마크다운으로 정리해줘. 번역하지 말고 원문 그대로 살려.\n\n원고:\n{doc_content}")
                st.session_state.summary_text = text_res
                st.session_state.final_prompt = f"""
                [TASK] Render a high-fidelity infographic board using the EXACT Korean text provided.
                [CONTENT] {st.session_state.summary_text}
                [DESIGN SYSTEM] {STYLE_A_PROMPT}
                [USER REQUEST] {st.session_state.design_instruction}
                [CRITICAL] DO NOT TRANSLATE. Write the provided Korean characters perfectly as typography.
                """.strip()
                st.success(f"✅ {model_used} 엔진으로 분석 완료!")
            except Exception as e: st.error(str(e))

    if st.session_state.summary_text:
        st.markdown(f'<div class="summary-box">', unsafe_allow_html=True)
        st.markdown(f"### 📝 이미지에 새겨질 한글 원고")
        st.markdown(st.session_state.summary_text)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 2단계: 렌더링
        if st.button("🚀 2단계: 노트북LM 스타일 고품질 렌더링", use_container_width=True, type="primary"):
            with st.spinner("디자인 렌더링 중... (서버 지연 시 우회 경로 탐색)"):
                try:
                    img, model = generate_multimodal_image_with_fallback(client, st.session_state.final_prompt)
                    st.image(img.resize((px_w, px_h)), use_container_width=True)
                    st.caption(f"사용한 렌더링 엔진: {model}")
                except Exception as e: st.error(f"렌더링 실패: {e}")
