# Mini AI Tutor + Evaluator (Assessment Project)

This project is a production-style educational assistant built for an AI assessment use case:

- ingest study material into a searchable knowledge base
- generate grounded tutor answers from retrieved chunks
- evaluate student answers with rubric-style scoring
- support human review and score override
- expose complete flow through FastAPI and Streamlit

## What Is Implemented

- RAG with ingestion, chunking, embeddings, and FAISS retrieval.
- Multi-agent flow with tutor, evaluator, and orchestration pipeline.
- HITL review with approve/override and stored review history.
- Streamlit portals for Teacher, Student, and Results.

## Tech Stack Used

- FastAPI
- LangGraph
- FAISS (`faiss-cpu`)
- OpenAI / Azure OpenAI
- Docling
- Streamlit
- Pydantic v2

## Project Structure

```text
ai-tutor-assessment/
├── main.py
├── routes/api.py
├── streamlit_app.py
├── agents/
├── orchestrator/
├── rag/
├── ingestion/
├── hitl/
├── app/
├── storage/
└── README.md
```

## Setup

1. `pip install -r requirements.txt`
2. `cp .env.example .env` and set API keys in `.env`
3. Run API: `uvicorn main:app --reload`
4. Run UI: `streamlit run streamlit_app.py`

## API Endpoints

- `POST /ingest` - Ingest a document file path and update the vector index.
- `POST /ask` - Generate tutor answer for a question using retrieved context.
- `POST /answer` - Evaluate a student answer and create evaluation record (supports optional `ideal_answer`).
- `POST /review` - Approve or override an evaluation by `evaluation_id`.
- `GET /review/stats` - Return review analytics summary.
- `GET /status` - Return provider and index readiness state.
- `GET /health` - Basic health check.

## Normal Flow (Teacher → Student → Result)

```text
Teacher Portal
  ├─ Ingest data (/ingest)
  ├─ Create question bank (/ask)
  ├─ Evaluate student answers (/answer)
  └─ Approve/override review (/review)
            │
            v
Student Portal
  ├─ View teacher questions
  └─ Submit answers
            │
            v
Result Page
  └─ Search by Student ID → show answer + score/10 + feedback + overall score
```

## Rebuild Index (After Chunking Changes)

```bash
rm -f storage/faiss_index/index.faiss storage/faiss_index/metadata.json
```

Re-ingest files after cleanup (example):

```bash
curl -X POST "http://127.0.0.1:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{"file_path":"/absolute/path/to/file.md"}'
```

For future enhancement, we can extend this system with advanced specialized agents; see [`README_ENHANCEMENT_ROADMAP.md`](README_ENHANCEMENT_ROADMAP.md).