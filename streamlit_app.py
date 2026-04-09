from typing import Any

import requests
import streamlit as st

from app.qa_workflow import (
    add_question,
    create_submission,
    delete_question,
    find_latest_report_for_student,
    get_submission,
    list_questions,
    list_submissions,
    upsert_report,
)


def _ensure_state() -> None:
    if "student_id" not in st.session_state:
        st.session_state.student_id = ""
    if "student_name" not in st.session_state:
        st.session_state.student_name = ""
    if "latest_submission_id" not in st.session_state:
        st.session_state.latest_submission_id = ""
    if "teacher_id" not in st.session_state:
        st.session_state.teacher_id = "teacher-1"
    if "api_base" not in st.session_state:
        st.session_state.api_base = "http://127.0.0.1:8000"
    if "selected_submission_id" not in st.session_state:
        st.session_state.selected_submission_id = ""
    if "active_report" not in st.session_state:
        st.session_state.active_report = None
    if "teacher_new_question" not in st.session_state:
        st.session_state.teacher_new_question = ""
    if "teacher_generated_ideal_answer" not in st.session_state:
        st.session_state.teacher_generated_ideal_answer = ""
    if "teacher_ai_gen_confidence" not in st.session_state:
        st.session_state.teacher_ai_gen_confidence = 0.0
    if "teacher_ai_gen_error" not in st.session_state:
        st.session_state.teacher_ai_gen_error = ""
    if "teacher_ingest_path" not in st.session_state:
        st.session_state.teacher_ingest_path = ""
    if "teacher_ingest_result" not in st.session_state:
        st.session_state.teacher_ingest_result = None
    if "teacher_ingest_error" not in st.session_state:
        st.session_state.teacher_ingest_error = ""
    if "teacher_filter_student_id" not in st.session_state:
        st.session_state.teacher_filter_student_id = ""
    if "results_student_id" not in st.session_state:
        st.session_state.results_student_id = ""
    if "results_loaded_report" not in st.session_state:
        st.session_state.results_loaded_report = None
    if "results_loaded_submission" not in st.session_state:
        st.session_state.results_loaded_submission = None


def _api_post(url: str, payload: dict[str, Any]) -> tuple[bool, Any]:
    try:
        res = requests.post(url, json=payload, timeout=120)
    except requests.RequestException as exc:
        return False, f"Request failed: {exc}"
    try:
        data = res.json()
    except ValueError:
        data = res.text
    return res.ok, data


def _teacher_generate_ideal_answer() -> None:
    qtxt = (st.session_state.teacher_new_question or "").strip()
    if not qtxt:
        st.session_state.teacher_ai_gen_error = "Please enter a question first."
        st.session_state.teacher_generated_ideal_answer = ""
        st.session_state.teacher_ai_gen_confidence = 0.0
        return

    api_base = (st.session_state.api_base or "").rstrip("/")
    ok, data = _api_post(f"{api_base}/ask", {"question": qtxt})
    if not ok:
        st.session_state.teacher_ai_gen_error = f"Ask API failed: {data}"
        st.session_state.teacher_generated_ideal_answer = ""
        st.session_state.teacher_ai_gen_confidence = 0.0
        return

    if isinstance(data, dict):
        answer = data.get("tutor_answer") or data.get("answer") or ""
        confidence = data.get("confidence", 0.0)
    else:
        answer = str(data)
        confidence = 0.0

    st.session_state.teacher_generated_ideal_answer = str(answer).strip()
    st.session_state.teacher_ai_gen_error = ""
    try:
        st.session_state.teacher_ai_gen_confidence = float(confidence or 0.0)
    except (TypeError, ValueError):
        st.session_state.teacher_ai_gen_confidence = 0.0


def _teacher_clear_question_builder() -> None:
    st.session_state.teacher_new_question = ""
    st.session_state.teacher_generated_ideal_answer = ""
    st.session_state.teacher_ai_gen_confidence = 0.0
    st.session_state.teacher_ai_gen_error = ""


def _teacher_add_question() -> None:
    new_q = (st.session_state.teacher_new_question or "").strip()
    new_a = (st.session_state.teacher_generated_ideal_answer or "").strip()
    if not new_q:
        st.session_state.teacher_ai_gen_error = "Question is required."
        return
    if not new_a:
        st.session_state.teacher_ai_gen_error = "Click 'Generate Ideal Answer (AI)' first."
        return
    add_question(new_q, new_a)
    _teacher_clear_question_builder()


def _teacher_ingest_file() -> None:
    path = (st.session_state.teacher_ingest_path or "").strip()
    if not path:
        st.session_state.teacher_ingest_error = "Please enter a file path."
        st.session_state.teacher_ingest_result = None
        return
    api_base = (st.session_state.api_base or "").rstrip("/")
    ok, data = _api_post(f"{api_base}/ingest", {"file_path": path})
    if not ok:
        st.session_state.teacher_ingest_error = f"Ingest API failed: {data}"
        st.session_state.teacher_ingest_result = None
        return
    st.session_state.teacher_ingest_error = ""
    st.session_state.teacher_ingest_result = data


def _points_to_bullets(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    lines = [ln.strip(" -\t").strip() for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln]
    if len(lines) <= 1 and ("." in raw):
        parts = [p.strip() for p in raw.split(".") if p.strip()]
        if len(parts) >= 2:
            return [p + "." for p in parts[:6]]
    return lines[:8]


st.set_page_config(page_title="AI Tutor Assessment", page_icon="🎓", layout="wide")
_ensure_state()

st.title("AI Tutor Assessment")
st.caption("Student submits answers → Teacher evaluates per question → Student views results.")

with st.sidebar:
    st.subheader("Navigation")
    screen = st.radio(
        "Go to",
        ["1) Student", "2) Teacher", "3) Results"],
        index=0,
    )
    st.markdown("---")
    st.subheader("Teacher")
    st.text_input("Teacher ID", key="teacher_id")
    st.text_input("FastAPI Base URL", key="api_base")

questions_all = list_questions()
questions_for_student = questions_all[:10]

if screen == "1) Student":
    st.markdown("## Student Portal")
    st.write("You will see only the questions added by the teacher.")

    c1, c2 = st.columns(2)
    with c1:
        st.text_input("Student ID (required)", key="student_id", placeholder="e.g. S101")
    with c2:
        st.text_input("Student Name (optional)", key="student_name", placeholder="e.g. Vivek")

    if not questions_for_student:
        st.warning("No questions available yet. Ask teacher to add questions in Teacher Portal.")
    else:
        st.info(f"Showing {len(questions_for_student)} question(s). (Max 10)")
        answers_by_qid: dict[str, str] = {}
        for idx, q in enumerate(questions_for_student, start=1):
            qid = q.get("question_id", f"q_{idx}")
            st.markdown(f"### Q{idx}. {q.get('question','')}")
            answers_by_qid[qid] = st.text_area(
                "Your answer",
                key=f"student_answer_{qid}",
                height=120,
                placeholder="Write your answer here...",
            )

        st.markdown("---")
        if st.button("Submit Answers", type="primary", use_container_width=True):
            if not st.session_state.student_id.strip():
                st.error("Student ID is required.")
            else:
                submission = create_submission(
                    student_id=st.session_state.student_id,
                    student_name=st.session_state.student_name,
                    answers_by_qid=answers_by_qid,
                )
                st.session_state.latest_submission_id = submission.get("submission_id", "")
                st.success(f"Submitted. Submission ID: {st.session_state.latest_submission_id}")
                st.info("No AI evaluation happens now. Teacher will evaluate later.")

elif screen == "2) Teacher":
    st.markdown("## Teacher Portal")

    tab_manage, tab_evaluate = st.tabs(["Ingest / Manage Questions", "Evaluate Student Answers"])

    with tab_manage:
        st.markdown("### Ingest Data")
        st.caption("Upload study material into the knowledge base (calls FastAPI `/ingest`).")
        st.text_input(
            "File path (PDF/DOCX/TXT/MD)",
            key="teacher_ingest_path",
            placeholder="/absolute/path/to/file.pdf",
        )
        st.button("Ingest File", type="primary", on_click=_teacher_ingest_file)
        if st.session_state.teacher_ingest_error:
            st.error(st.session_state.teacher_ingest_error)
        if st.session_state.teacher_ingest_result is not None:
            st.json(st.session_state.teacher_ingest_result)

        st.markdown("---")
        st.markdown("### Question Bank")
        st.caption("Add/edit by re-adding; delete removes it from student view.")

        st.text_area(
            "Add question",
            key="teacher_new_question",
            height=110,
            placeholder="Enter question...",
        )

        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            st.button(
                "Generate Ideal Answer (AI)",
                type="primary",
                use_container_width=True,
                on_click=_teacher_generate_ideal_answer,
            )
        with c2:
            st.button("Clear", use_container_width=True, on_click=_teacher_clear_question_builder)
        with c3:
            if st.session_state.teacher_ai_gen_confidence:
                st.caption(f"AI generation confidence: {st.session_state.teacher_ai_gen_confidence:.2f}")

        if st.session_state.teacher_ai_gen_error:
            st.warning(st.session_state.teacher_ai_gen_error)

        if st.session_state.teacher_generated_ideal_answer:
            st.markdown("**AI generated ideal answer (preview)**")
            st.write(st.session_state.teacher_generated_ideal_answer)

        st.button("Add Question", type="primary", on_click=_teacher_add_question)

        st.markdown("---")
        qs = list_questions()
        st.write(f"Total questions: **{len(qs)}**")
        for q in qs:
            qid = q.get("question_id", "")
            with st.expander(f"{qid}: {q.get('question','')}", expanded=False):
                st.markdown("**Ideal answer**")
                st.write(q.get("ideal_answer", ""))
                if st.button(f"Delete {qid}", key=f"del_{qid}"):
                    ok = delete_question(qid)
                    if ok:
                        st.success("Deleted.")
                        st.rerun()
                    else:
                        st.error("Could not delete (not found).")

    with tab_evaluate:
        st.markdown("### Submissions")
        st.text_input("Filter by Student ID (optional)", key="teacher_filter_student_id", placeholder="e.g. S101")
        subs_all = list_submissions()
        filt = (st.session_state.teacher_filter_student_id or "").strip()
        subs = (
            [s for s in subs_all if (s.get("student_id") or "").strip() == filt]
            if filt
            else subs_all
        )
        if not subs:
            st.info("No student submissions yet.")
        else:
            options = [
                f"{s.get('submission_id')} | {s.get('student_id')} | {s.get('student_name','')} | {s.get('submitted_at')}"
                for s in subs
            ]
            default_idx = 0
            if st.session_state.selected_submission_id:
                for i, s in enumerate(subs):
                    if s.get("submission_id") == st.session_state.selected_submission_id:
                        default_idx = i
                        break
            picked = st.selectbox("Pick a submission", options, index=default_idx)
            st.session_state.selected_submission_id = picked.split("|", 1)[0].strip()

            submission = get_submission(st.session_state.selected_submission_id)
            if not submission:
                st.error("Submission not found.")
            else:
                st.markdown("---")
                st.write(
                    f"**Student:** {submission.get('student_id')} ({submission.get('student_name','')})  "
                    f"**Submitted:** {submission.get('submitted_at')}"
                )

                q_by_id = {q.get("question_id"): q for q in list_questions()}
                answers = submission.get("answers_by_qid") or {}

                report = st.session_state.active_report
                if not report or report.get("submission_id") != submission.get("submission_id"):
                    report = {
                        "report_id": "",
                        "submission_id": submission.get("submission_id"),
                        "student_id": submission.get("student_id"),
                        "teacher_id": st.session_state.teacher_id,
                        "created_at": submission.get("submitted_at"),
                        "evaluations_by_qid": {},
                        "final_submitted": False,
                        "total_out_of_10": 0.0,
                    }
                    st.session_state.active_report = report

                st.markdown("### Per-question evaluation (out of 10)")

                for idx, (qid, student_ans) in enumerate(answers.items(), start=1):
                    qrow = q_by_id.get(qid) or {}
                    question_text = qrow.get("question", f"Question {qid}")
                    ideal = qrow.get("ideal_answer", "")

                    st.markdown(f"#### Q{idx}. {question_text}")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**Student answer**")
                        st.write(student_ans)
                    with c2:
                        st.markdown("**Ideal answer (teacher)**")
                        st.write(ideal)

                    evals = report.get("evaluations_by_qid", {})
                    existing = evals.get(qid, {})
                    if existing:
                        ai_score = float(existing.get("ai_score_out_of_10", existing.get("score_out_of_10", 0.0)) or 0.0)
                        shown_score = float(existing.get("score_out_of_10", 0.0) or 0.0)
                        st.write(f"**AI Evaluation Score:** {ai_score:.2f} / 10")
                        if existing.get("override_applied"):
                            st.write(f"**Updated Score:** {shown_score:.2f} / 10")

                    b1, b2, b3 = st.columns([1, 1, 2])
                    with b1:
                        if st.button("Run AI evaluation", key=f"ai_{qid}"):
                            if not ideal.strip():
                                st.warning("Ideal answer is empty; generate and add it in Question Bank first.")
                            else:
                                api_base = (st.session_state.api_base or "").rstrip("/")
                                ok, data = _api_post(
                                    f"{api_base}/answer",
                                    {
                                        "question": question_text,
                                        "student_answer": str(student_ans or ""),
                                        "ideal_answer": ideal,
                                        "session_id": f"teacher_eval_{st.session_state.teacher_id}",
                                    },
                                )
                                if not ok:
                                    st.error(f"Evaluation API failed: {data}")
                                else:
                                    score_0_10 = float(data.get("ai_score", 0.0) or 0.0) * 10.0
                                    score_0_10 = max(0.0, min(10.0, score_0_10))
                                    feedback_points = _points_to_bullets(str(data.get("feedback", "")))
                                    evals[qid] = {
                                        "ai_score_out_of_10": score_0_10,
                                        "score_out_of_10": score_0_10,
                                        "feedback_points": feedback_points,
                                        # /answer doesn't expose evaluator confidence directly in response model
                                        "confidence_0_1": 0.0,
                                        "override_applied": False,
                                        "evaluation_id": str(data.get("evaluation_id", "") or ""),
                                        "review_action": "pending",
                                    }
                                    report["evaluations_by_qid"] = evals
                                    st.session_state.active_report = report
                                    st.success("AI evaluation saved for this question.")
                            st.rerun()

                    with b2:
                        current_score = float(existing.get("score_out_of_10", 0.0) or 0.0)
                        update_choice = st.radio(
                            "Need to update?",
                            ["No", "Yes"],
                            horizontal=True,
                            key=f"upd_{qid}",
                            index=1 if existing.get("override_applied") else 0,
                        )
                        if update_choice == "Yes":
                            new_score = st.number_input(
                                "Score",
                                min_value=0.0,
                                max_value=10.0,
                                step=0.5,
                                value=current_score,
                                key=f"score_{qid}",
                            )
                        else:
                            new_score = current_score
                    with b3:
                        current_fb = "\n".join(existing.get("feedback_points", []) or [])
                        if update_choice == "Yes":
                            new_fb = st.text_area(
                                "Feedback (points)",
                                value=current_fb,
                                height=110,
                                key=f"fb_{qid}",
                                placeholder="- Point 1\n- Point 2\n- Point 3",
                            )
                        else:
                            new_fb = current_fb
                            if current_fb:
                                st.markdown("**Feedback**")
                                st.write(current_fb)
                            else:
                                st.write("No feedback yet.")

                    if update_choice == "Yes":
                        if st.button("Submit updates", key=f"save_{qid}"):
                            evaluation_id = str(existing.get("evaluation_id", "") or "")
                            if not evaluation_id:
                                st.error("Run AI evaluation first to create evaluation record.")
                            else:
                                api_base = (st.session_state.api_base or "").rstrip("/")
                                fb_points = _points_to_bullets(new_fb)
                                feedback_text = "\n".join(f"- {p}" for p in fb_points) if fb_points else ""
                                ok, data = _api_post(
                                    f"{api_base}/review",
                                    {
                                        "evaluation_id": evaluation_id,
                                        "action": "override",
                                        "human_score": max(0.0, min(1.0, float(new_score) / 10.0)),
                                        "reviewer_id": st.session_state.teacher_id or "teacher-1",
                                        "reason_for_override": "teacher_manual_update",
                                        "feedback": feedback_text,
                                    },
                                )
                                if not ok:
                                    st.error(f"Review API failed: {data}")
                                else:
                                    final_score_10 = float(data.get("final_score", 0.0) or 0.0) * 10.0
                                    evals[qid] = {
                                        **existing,
                                        "score_out_of_10": max(0.0, min(10.0, final_score_10)),
                                        "feedback_points": _points_to_bullets(str(data.get("feedback", feedback_text))),
                                        "override_applied": True,
                                        "review_action": "override",
                                    }
                                    report["evaluations_by_qid"] = evals
                                    st.session_state.active_report = report
                                    st.success("Override submitted via /review.")
                            st.rerun()
                    else:
                        if existing.get("evaluation_id"):
                            if st.button("Approve AI (Review)", key=f"approve_{qid}"):
                                api_base = (st.session_state.api_base or "").rstrip("/")
                                ok, data = _api_post(
                                    f"{api_base}/review",
                                    {
                                        "evaluation_id": str(existing.get("evaluation_id")),
                                        "action": "approve",
                                        "reviewer_id": st.session_state.teacher_id or "teacher-1",
                                        "feedback": "\n".join(f"- {p}" for p in (existing.get("feedback_points") or [])),
                                    },
                                )
                                if not ok:
                                    st.error(f"Review API failed: {data}")
                                else:
                                    final_score_10 = float(data.get("final_score", 0.0) or 0.0) * 10.0
                                    evals[qid] = {
                                        **existing,
                                        "score_out_of_10": max(0.0, min(10.0, final_score_10)),
                                        "feedback_points": _points_to_bullets(str(data.get("feedback", ""))),
                                        "override_applied": False,
                                        "review_action": "approve",
                                    }
                                    report["evaluations_by_qid"] = evals
                                    st.session_state.active_report = report
                                    st.success("Approved via /review.")
                                st.rerun()

                    st.markdown("---")

                evals = report.get("evaluations_by_qid", {})
                score_values = [float(v.get("score_out_of_10", 0.0) or 0.0) for v in evals.values()]
                overall_out_of_10 = round((sum(score_values) / len(score_values)), 2) if score_values else 0.0
                report["total_out_of_10"] = overall_out_of_10
                st.session_state.active_report = report

                st.markdown("### Report")
                st.write(f"**Overall score:** {overall_out_of_10} / 10")
                if st.button("Submit Final Report", type="primary", use_container_width=True):
                    report["final_submitted"] = True
                    saved = upsert_report(report)
                    st.session_state.active_report = saved
                    st.success(f"Report submitted. Report ID: {saved.get('report_id')}")

elif screen == "3) Results":
    st.markdown("## Results (Student View)")
    st.write("Search by your Student ID (roll number) to load your latest submitted report.")
    st.text_input("Student ID", key="results_student_id", placeholder="e.g. S101")

    if st.button("Search", type="primary"):
        sid = (st.session_state.results_student_id or "").strip()
        if not sid:
            st.warning("Please enter Student ID.")
        else:
            rep = find_latest_report_for_student(sid)
            if not rep:
                st.session_state.results_loaded_report = None
                st.session_state.results_loaded_submission = None
                st.warning("No report found yet for this student (teacher may not have submitted it).")
            elif not rep.get("final_submitted"):
                st.session_state.results_loaded_report = None
                st.session_state.results_loaded_submission = None
                st.warning("Teacher has started evaluation but final report not submitted yet.")
            else:
                st.session_state.results_loaded_report = rep
                st.session_state.results_loaded_submission = get_submission(rep.get("submission_id", ""))

    rep = st.session_state.results_loaded_report
    sub = st.session_state.results_loaded_submission
    if rep and rep.get("final_submitted"):
        st.markdown("### Overall")
        st.write(f"**Student ID:** {rep.get('student_id')}")
        st.write(f"**Overall score:** {rep.get('total_out_of_10')} / 10")

        st.markdown("### Details (Question, Your Answer, Score, Feedback)")
        q_by_id = {q.get("question_id"): q for q in list_questions()}
        answers_by_qid = (sub or {}).get("answers_by_qid") or {}
        evals_by_qid = rep.get("evaluations_by_qid") or {}

        qids_in_order = list(answers_by_qid.keys()) or list(evals_by_qid.keys())
        for idx, qid in enumerate(qids_in_order, start=1):
            qtxt = (q_by_id.get(qid) or {}).get("question", qid)
            ans = str(answers_by_qid.get(qid, "") or "")
            ev = evals_by_qid.get(qid, {}) or {}
            marks = float(ev.get("score_out_of_10", 0.0) or 0.0)
            fb = ev.get("feedback_points") or []

            st.markdown(f"#### Q{idx}. {qtxt}")
            st.markdown("**Your answer**")
            st.write(ans or "-")
            st.write(f"**Score:** {marks:.2f} / 10")
            st.markdown("**Feedback**")
            if fb:
                for p in fb:
                    st.write(f"- {p}")
            else:
                st.write("-")
