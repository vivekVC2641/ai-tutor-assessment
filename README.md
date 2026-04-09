# Mini AI Tutor + Evaluator (Assessment Project)

This project is a production-style educational assistant built for an AI assessment use case:

- ingest study material into a searchable knowledge base
- generate grounded tutor answers from retrieved chunks
- evaluate student answers with rubric-style scoring
- support human review and score override
- expose complete flow through FastAPI and Streamlit

## What Is Implemented

- **RAG Pipeline**
  - Document ingestion with `docling` (markdown export)
  - Two-stage chunking:
    - structure-aware section split (markdown headers)
    - token-window split (`512` chunk size, `50` overlap)
  - Metadata enrichment per chunk (`source`, `section`, `chunk_id`, `content_type`)
  - FAISS vector search (`IndexFlatL2`)

- **Agentic Orchestration**
  - LangGraph pipeline:
    - `retrieve -> tutor -> guardrail -> (optional) evaluator`
  - Evaluator runs when student answer is present and guardrail passes

- **Tutor + Evaluator**
  - Tutor returns grounded answer, sources, confidence, follow-up hint
  - Evaluator returns score, confidence, and feedback
  - JSON parsing hardening with retry logic

- **Human-in-the-Loop (HITL)**
  - `/answer` creates AI evaluation record
  - `/review` supports:
    - `approve` (keep AI score)
    - `override` (human score/feedback)
  - Review stats endpoint for analytics

- **API + UI**
  - FastAPI backend for ingestion, asking, evaluation, and review
  - Streamlit app for end-to-end demo flow

## Tech Stack Used

- FastAPI
- LangGraph
- FAISS (`faiss-cpu`)
- OpenAI/Azure OpenAI client
- Docling
- Streamlit
- Pydantic v2

## Project Structure

```text
mini_ai_tutor/
├── main.py
├── routes/api.py
├── orchestrator/
│   ├── pipeline.py
│   └── indexing.py
├── ingestion/docling_ingestor.py
├── rag/
│   ├── chunker.py
│   ├── retriever.py
│   └── vector_store.py
├── agents/
│   ├── tutor_agent.py
│   ├── evaluator_agent.py
│   └── guardrail_agent.py
├── app/
│   ├── config.py
│   └── prompt_templates.py
├── hitl/review_store.py
├── storage/
│   ├── faiss_index/
│   ├── evaluations.json
│   └── reviews.json
└── streamlit_app.py
```

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create env file:

```bash
cp .env.example .env
```

3. Configure `.env`.

### Azure OpenAI (recommended for this project)

```env
PROVIDER=azure
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_CHAT_DEPLOYMENT=<your_chat_deployment>
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=<your_embedding_deployment>
```

Chunking settings:

```env
CHUNK_SIZE_TOKENS=512
CHUNK_OVERLAP_TOKENS=50
```

4. Run API:

```bash
uvicorn main:app --reload
```

5. Optional Streamlit demo:

```bash
streamlit run streamlit_app.py
```

## API Endpoints

- `POST /ingest`
  - body: `{"file_path":"<absolute-or-relative-path>"}`
  - output: file, sections, chunks, index status
  - supported input files:
    - `.pdf`
    - `.docx`
    - `.txt`
    - `.md`
  - note: ingestion uses `docling` first; if parsing fails, system falls back to plain text read.

- `POST /ask`
  - body: `{"question":"What is ...?"}`
  - output: tutor answer grounded on retrieved chunks

- `POST /answer`
  - body: `{"question":"...", "student_answer":"...", "session_id":"sess_123"}`
  - output: AI evaluation payload (`ai_score`, `feedback`, `status`, etc.)

- `POST /review`
  - approve flow:
    - `{"evaluation_id":"eval_xxx", "action":"approve"}`
  - override flow:
    - `{"evaluation_id":"eval_xxx", "action":"override", "human_score":0.68, "reviewer_id":"teacher-1", "reason_for_override":"...", "feedback":"..."}`

- `GET /review/stats`
  - review analytics

- `GET /status`
  - provider + index readiness

- `GET /health`
  - health check

## Rebuild Index (After Chunking Changes)

Delete old FAISS files and ingest again:

```bash
rm -f storage/faiss_index/index.faiss storage/faiss_index/metadata.json
```

Then ingest files (example):

```bash
curl -X POST "http://127.0.0.1:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{"file_path":"/absolute/path/to/file.md"}'
```