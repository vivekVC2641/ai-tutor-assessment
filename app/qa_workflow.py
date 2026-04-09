from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from app.local_store import JsonStore, now_iso


def _store_path(rel: str) -> Path:
    return Path(rel)


QUESTION_BANK_FILE = _store_path("storage/question_bank.json")
SUBMISSIONS_FILE = _store_path("storage/student_submissions.json")
REPORTS_FILE = _store_path("storage/teacher_reports.json")


@dataclass(frozen=True)
class Question:
    question_id: str
    question: str
    ideal_answer: str
    created_at: str


def list_questions() -> list[dict]:
    rows = JsonStore(QUESTION_BANK_FILE).load_list()
    rows.sort(key=lambda x: x.get("created_at") or "", reverse=False)
    return rows


def add_question(question: str, ideal_answer: str) -> dict:
    store = JsonStore(QUESTION_BANK_FILE)
    rows = store.load_list()
    q = {
        "question_id": f"q_{uuid.uuid4().hex[:10]}",
        "question": question.strip(),
        "ideal_answer": ideal_answer.strip(),
        "created_at": now_iso(),
    }
    rows.append(q)
    store.save(rows)
    return q


def delete_question(question_id: str) -> bool:
    store = JsonStore(QUESTION_BANK_FILE)
    rows = store.load_list()
    new_rows = [r for r in rows if r.get("question_id") != question_id]
    if len(new_rows) == len(rows):
        return False
    store.save(new_rows)
    return True


def create_submission(student_id: str, student_name: str, answers_by_qid: dict[str, str]) -> dict:
    store = JsonStore(SUBMISSIONS_FILE)
    rows = store.load_list()
    submission = {
        "submission_id": f"sub_{uuid.uuid4().hex[:12]}",
        "student_id": student_id.strip(),
        "student_name": student_name.strip(),
        "answers_by_qid": {k: (v or "").strip() for k, v in answers_by_qid.items()},
        "submitted_at": now_iso(),
    }
    rows.append(submission)
    store.save(rows)
    return submission


def list_submissions() -> list[dict]:
    rows = JsonStore(SUBMISSIONS_FILE).load_list()
    rows.sort(key=lambda x: x.get("submitted_at") or "", reverse=True)
    return rows


def get_submission(submission_id: str) -> dict | None:
    for row in list_submissions():
        if row.get("submission_id") == submission_id:
            return row
    return None


def upsert_report(report: dict) -> dict:
    store = JsonStore(REPORTS_FILE)
    rows = store.load_list()
    rid = report.get("report_id")
    if not rid:
        report = dict(report)
        report["report_id"] = f"rep_{uuid.uuid4().hex[:12]}"
        report["updated_at"] = now_iso()
        rows.append(report)
        store.save(rows)
        return report

    updated = False
    for i, r in enumerate(rows):
        if r.get("report_id") == rid:
            report = dict(report)
            report["report_id"] = rid
            report["updated_at"] = now_iso()
            rows[i] = report
            updated = True
            break
    if not updated:
        report = dict(report)
        report["report_id"] = rid
        report["updated_at"] = now_iso()
        rows.append(report)
    store.save(rows)
    return report


def list_reports() -> list[dict]:
    rows = JsonStore(REPORTS_FILE).load_list()
    rows.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
    return rows


def find_latest_report_for_student(student_id: str) -> dict | None:
    student_id = student_id.strip()
    subs = [s for s in list_submissions() if (s.get("student_id") or "").strip() == student_id]
    if not subs:
        return None
    sub_ids = {s.get("submission_id") for s in subs if s.get("submission_id")}
    for r in list_reports():
        if r.get("submission_id") in sub_ids:
            return r
    return None

