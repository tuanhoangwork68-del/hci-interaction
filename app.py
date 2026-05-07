# app.py

import os
import csv
from datetime import datetime

import pandas as pd
import streamlit as st
import google.generativeai as genai


# =========================================================
# 페이지 기본 설정
# =========================================================
st.set_page_config(
    page_title="쇼핑몰 고객 상담 챗봇",
    page_icon="🛍️",
    layout="centered"
)

st.title("🛍️ 쇼핑몰 고객 상담 챗봇")
st.caption("Gemini API + Streamlit 기반 고객 응대 챗봇")


# =========================================================
# Gemini API Key 설정
# - secrets에 키가 있으면 자동 사용
# - 없으면 UI에서 직접 입력 가능
# =========================================================
api_key = None

try:
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    pass

if not api_key:
    st.warning("⚠️ GEMINI_API_KEY가 설정되지 않았습니다.")
    api_key = st.text_input(
        "Gemini API Key를 입력하세요",
        type="password"
    )

if not api_key:
    st.stop()

genai.configure(api_key=api_key)


# =========================================================
# 모델 선택 UI
# =========================================================
MODEL_LIST = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash"
]

selected_model = st.selectbox(
    "사용할 Gemini 모델 선택",
    MODEL_LIST,
    index=0  # lite 모델 기본값
)

st.info(f"현재 사용 중인 모델: {selected_model}")


# =========================================================
# 세션 상태 초기화
# - messages: 화면 표시용 전체 대화
# - log_data: CSV 저장용 로그
# =========================================================
if "messages" not in st.session_state:
    st.session_state.messages = []

if "log_data" not in st.session_state:
    st.session_state.log_data = []


# =========================================================
# FAQ CSV 파일 확인 및 로드
# - faq_data.csv가 존재하면 읽어서 Markdown 변환
# - 없으면 에러 없이 진행
# =========================================================
faq_markdown = ""
faq_loaded = False

FAQ_FILE = "faq_data.csv"

if os.path.exists(FAQ_FILE):
    try:
        faq_df = pd.read_csv(FAQ_FILE)

        # DataFrame -> Markdown 변환
        faq_markdown = faq_df.to_markdown(index=False)

        faq_loaded = True

        st.success("✅ faq_data.csv 파일 로드 완료")

    except Exception as e:
        st.warning(f"CSV 파일 읽기 실패: {e}")

else:
    st.info("faq_data.csv 파일 없이 기본 모드로 실행됩니다.")


# =========================================================
# 시스템 프롬프트 구성
# =========================================================
system_prompt = """
당신은 쇼핑몰의 전문 고객 상담사입니다.
사용자의 불편/불만에 대해 정중하고 공감 어린 말투로 응답하세요.

사용자의 불편 사항을 구체적으로 정리하여 수집하세요.
반드시 다음 정보를 자연스럽게 파악하세요:
- 무엇이 문제인지
- 언제 발생했는지
- 어디에서 발생했는지
- 어떻게 발생했는지

그리고 수집된 내용을 사내 고객 응대 담당자에게 전달하여 확인하겠다는 취지로 안내하세요.

대화의 마지막 단계에서는 담당자가 확인 후 회신할 수 있도록
사용자의 이메일 주소를 요청하세요.

만약 사용자가 연락처 제공을 거부하면:
"죄송하지만, 연락처 정보를 받지 못하여 담당자의 검토 내용을 직접 안내해 드리기 어렵습니다."
라고 정중히 마무리하세요.
"""

# CSV가 존재하는 경우에만 추가 규칙 삽입
if faq_loaded:
    system_prompt += f"""

답변을 할 때는 제공된 [CSV 참조 데이터]를 우선적으로 확인하여 안내하세요.
데이터에 없는 내용이라면 임의로 지어내지 말고
"담당 부서 확인 후 안내해 드리겠습니다"
라고 답변하세요.

[CSV 참조 데이터]
{faq_markdown}
"""


# =========================================================
# Gemini 모델 생성
# =========================================================
model = genai.GenerativeModel(
    model_name=selected_model,
    system_instruction=system_prompt
)


# =========================================================
# 사이드바 기능
# - 대화 초기화
# - 로그 다운로드
# =========================================================
with st.sidebar:

    st.subheader("⚙️ 기능")

    # -------------------------
    # 대화 초기화 버튼
    # -------------------------
    if st.button("🧹 대화 초기화"):

        st.session_state.messages = []
        st.session_state.log_data = []

        st.rerun()

    st.divider()

    # -------------------------
    # CSV 다운로드 기능
    # -------------------------
    if st.session_state.log_data:

        log_df = pd.DataFrame(st.session_state.log_data)

        csv_data = log_df.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            label="📥 대화 로그 다운로드 (CSV)",
            data=csv_data,
            file_name="chat_log.csv",
            mime="text/csv"
        )


# =========================================================
# 기존 대화 출력
# =========================================================
for msg in st.session_state.messages:

    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# =========================================================
# 사용자 입력
# =========================================================
user_input = st.chat_input("문의 내용을 입력하세요")


if user_input:

    # =====================================================
    # 사용자 메시지 저장
    # =====================================================
    user_message = {
        "role": "user",
        "content": user_input
    }

    st.session_state.messages.append(user_message)

    # 화면 출력
    with st.chat_message("user"):
        st.markdown(user_input)

    # =====================================================
    # 최근 6턴만 모델에 전달
    # - User/Model 왕복 기준 6턴
    # - 메시지 기준 최대 12개 유지
    # =====================================================
    recent_messages = st.session_state.messages[-12:]

    # Gemini API 형식 변환
    gemini_history = []

    for msg in recent_messages:

        role = "user" if msg["role"] == "user" else "model"

        gemini_history.append({
            "role": role,
            "parts": [msg["content"]]
        })

    # =====================================================
    # 모델 응답 생성
    # =====================================================
    try:

        response = model.generate_content(gemini_history)

        bot_text = response.text

    except Exception as e:

        error_message = str(e)

        # 429 / ResourceExhausted 대응
        if "429" in error_message or "ResourceExhausted" in error_message:

            st.error(
                "현재 사용량이 많아 응답이 지연되고 있습니다. "
                "1분 뒤에 다시 시도해 주세요."
            )

        else:
            st.error(f"오류 발생: {error_message}")

        st.stop()

    # =====================================================
    # 챗봇 응답 저장
    # =====================================================
    assistant_message = {
        "role": "assistant",
        "content": bot_text
    }

    st.session_state.messages.append(assistant_message)

    # =====================================================
    # 화면 출력
    # =====================================================
    with st.chat_message("assistant"):
        st.markdown(bot_text)

    # =====================================================
    # CSV 로그 저장
    # =====================================================
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    st.session_state.log_data.append({
        "time": now,
        "role": "user",
        "message": user_input
    })

    st.session_state.log_data.append({
        "time": now,
        "role": "assistant",
        "message": bot_text
    })
