import uuid
from typing import Any

import requests
import streamlit as st

DEFAULT_API_BASE = "http://127.0.0.1:8000"


def _api_request(method: str, url: str, payload: dict[str, Any] | None = None) -> tuple[bool, Any]:
    try:
        if method == "GET":
            res = requests.get(url, timeout=90)
        else:
            res = requests.post(url, json=payload, timeout=120)
    except requests.RequestException as exc:
        return False, f"Request failed: {exc}"

    try:
        data = res.json()
    except ValueError:
        data = res.text
    return (res.ok, data)


def _ensure_state() -> None:
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"sess_{uuid.uuid4().hex[:8]}"
    if "question" not in st.session_state:
        st.session_state.question = ""
    if "tutor_response" not in st.session_state:
        st.session_state.tutor_response = None
    if "student_answer" not in st.session_state:
        st.session_state.student_answer = ""
    if "latest_eval" not in st.session_state:
        st.session_state.latest_eval = None
    if "final_submission_done" not in st.session_state:
        st.session_state.final_submission_done = False
    if "editable_feedback" not in st.session_state:
        st.session_state.editable_feedback = ""
    if "editable_score" not in st.session_state:
        st.session_state.editable_score = 0.0


def _reset_flow() -> None:
    st.session_state.question = ""
    st.session_state.tutor_response = None
    st.session_state.student_answer = ""
    st.session_state.latest_eval = None
    st.session_state.final_submission_done = False
    st.session_state.editable_feedback = ""
    st.session_state.editable_score = 0.0
    st.rerun()


st.set_page_config(page_title="Mini AI Tutor", page_icon="🎓", layout="wide")
_ensure_state()

st.title("Mini AI Tutor")
st.caption("Simple student flow: Question -> Get Answer -> Write Answer -> Submit -> Score + Feedback")

with st.sidebar:
    st.subheader("Setup")
    api_base = st.text_input("FastAPI Base URL", value=DEFAULT_API_BASE).rstrip("/")
    st.text_input("Session ID", key="session_id")
    # Roll number removed for simplicity (user request)

    st.markdown("---")
    st.subheader("Navigation")
    screen = st.radio(
        "Select screen",
        ["1) Student Flow", "2) Final Result", "3) Ingest Data"],
        index=0,
    )

    st.markdown("---")
    if st.button("Reset Student Flow", use_container_width=True):
        _reset_flow()

if screen == "1) Student Flow":
    st.markdown("## Step 1: Put question and get tutor answer")
    st.text_area("Question", key="question", height=110, placeholder="Type your question...")

    if st.button("Get Answer", type="primary"):
        if not st.session_state.question.strip():
            st.warning("Please enter question.")
        else:
            ok, data = _api_request("POST", f"{api_base}/ask", {"question": st.session_state.question.strip()})
            if ok:
                st.session_state.tutor_response = data
                st.success("Tutor answer generated.")
            else:
                st.error("Could not get tutor answer.")
            st.json(data)

    if st.session_state.tutor_response:
        st.markdown("### Tutor Answer")
        st.write(st.session_state.tutor_response.get("tutor_answer", ""))

    st.markdown("---")
    st.markdown("## Step 2: Write your answer and submit")
    st.text_area(
        "Student Answer",
        key="student_answer",
        height=170,
        placeholder="Write your answer here...",
    )

    if st.button("Submit (AI Check)", type="primary"):
        if not st.session_state.question.strip():
            st.warning("Please enter question first.")
        elif not st.session_state.student_answer.strip():
            st.warning("Please write your answer.")
        else:
            payload = {
                "session_id": st.session_state.session_id,
                "question": st.session_state.question.strip(),
                "student_answer": st.session_state.student_answer.strip(),
            }
            ok, data = _api_request("POST", f"{api_base}/answer", payload)
            if ok:
                st.session_state.latest_eval = data
                st.session_state.final_submission_done = False
                st.session_state.editable_feedback = str(data.get("feedback", ""))
                try:
                    st.session_state.editable_score = float(data.get("ai_score", 0.0))
                except (TypeError, ValueError):
                    st.session_state.editable_score = 0.0
                st.success("AI evaluation complete.")
            else:
                st.error("AI evaluation failed.")
            st.json(data)

    if st.session_state.latest_eval:
        st.markdown("### AI Score and Feedback")
        st.write(f"**AI Score:** {st.session_state.latest_eval.get('ai_score')}")
        st.write(f"**AI Feedback:** {st.session_state.latest_eval.get('feedback')}")

        need_update = st.radio(
            "Need to update score/feedback before final submit?",
            ["No, final submit", "Yes, update score & feedback"],
            horizontal=True,
            key="need_update_choice",
        )
        if need_update == "No, final submit":
            st.text_area(
                "Update AI Feedback (optional before final submit)",
                key="editable_feedback",
                height=140,
                placeholder="You can edit feedback text before final submit...",
            )
            if st.button("Final Submit"):
                if st.session_state.latest_eval is None:
                    st.warning("Run AI check first.")
                else:
                    payload = {
                        "evaluation_id": st.session_state.latest_eval.get("evaluation_id", ""),
                        "action": "approve",
                        "reviewer_id": "student_final_submit",
                        "feedback": st.session_state.editable_feedback,
                    }
                    ok, data = _api_request("POST", f"{api_base}/review", payload)
                    if ok:
                        st.session_state.latest_eval = data
                        st.session_state.final_submission_done = True
                        st.success("Final submitted.")
                    else:
                        st.error("Final submit failed.")
                    st.json(data)
        else:
            st.info("Update score/feedback below, then click final submit. No second AI check will run.")
            st.number_input(
                "Update Score (0.0 to 1.0)",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                key="editable_score",
            )
            st.text_area(
                "Update Feedback",
                key="editable_feedback",
                height=140,
                placeholder="Edit feedback text...",
            )
            if st.button("Submit Updated Score & Feedback"):
                if st.session_state.latest_eval is None:
                    st.warning("Run AI check first.")
                else:
                    payload = {
                        "evaluation_id": st.session_state.latest_eval.get("evaluation_id", ""),
                        "action": "override",
                        "human_score": float(st.session_state.editable_score),
                        "reviewer_id": "student_override_submit",
                        "reason_for_override": "manual_score_feedback_update",
                        "feedback": st.session_state.editable_feedback,
                    }
                    ok, data = _api_request("POST", f"{api_base}/review", payload)
                    if ok:
                        st.session_state.latest_eval = data
                        st.session_state.final_submission_done = True
                        st.success("Final submitted with updated score and feedback.")
                    else:
                        st.error("Submit failed.")
                    st.json(data)

elif screen == "2) Final Result":
    st.markdown("## Final Result")
    if not st.session_state.latest_eval:
        st.info("No submission found yet. Complete Student Flow first.")
    elif not st.session_state.final_submission_done:
        st.warning("Submission exists, but final submit not done yet.")
    else:
        st.write("### Your Result (4 items)")
        st.write(f"**Question:** {st.session_state.latest_eval.get('question', '')}")
        st.write(f"**Your Answer:** {st.session_state.latest_eval.get('student_answer', '')}")
        st.write(f"**Score:** {st.session_state.latest_eval.get('final_score')}")
        st.write(f"**Feedback:** {st.session_state.latest_eval.get('feedback', '')}")

elif screen == "3) Ingest Data":
    st.markdown("## Ingest Data")
    st.caption("Only for adding documents into knowledge base index.")
    ingest_path = st.text_input("File path (PDF/DOCX/TXT/MD)", value="")
    if st.button("Ingest File", type="primary"):
        if not ingest_path.strip():
            st.warning("Please enter file path.")
        else:
            ok, data = _api_request("POST", f"{api_base}/ingest", {"file_path": ingest_path.strip()})
            if ok:
                st.success("Ingest completed.")
            else:
                st.error("Ingest failed.")
            st.json(data)
