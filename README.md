# Medical Report Simplifier

Upload a lab report or prescription (PDF, PNG, JPG) and get a plain-language explanation in 35 languages
(Hindi, Punjabi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Odia, Urdu, Nepali, Assamese,
and more), with warnings for values outside the range printed in the report.

It is an educational tool. It never diagnoses, never advises on medicines or treatment, and always tells the
reader to see a doctor.

## How it stays safe
1. Numbers, units and low/normal/high status are decided by code, never by the LLM.
2. The LLM only writes explanations, from structured facts plus approved reference passages.
3. Every output is checked: numerical fidelity, unit preservation, range accuracy, entity completeness,
   unsafe advice / diagnosis / false reassurance, unsupported condition names, output script, and an
   independent second LLM "judge" that back-translates and audits the text.
4. If a check fails, the model is asked once more. If it still fails, the user sees plain extracted facts only.
5. Unknown or ambiguous reference ranges are never judged. Report flags that contradict the range become "unknown".

## Run it
    python -m venv .venv && source .venv/bin/activate
    pip install -r backend/requirements.txt -r frontend/requirements.txt
    pip install -r backend/requirements-ml.txt      # optional: semantic retrieval (FAISS)
    cp .env.example .env                            # add LLM_API_KEY, or set LLM_PROVIDER=mock to try the flow
    python -m rag.ingestion                         # build the vector index
    uvicorn backend.app.main:app --reload           # terminal 1
    streamlit run frontend/app.py                   # terminal 2 (run from the project root)

Scanned files need Tesseract (`sudo apt install tesseract-ocr tesseract-ocr-hin tesseract-ocr-pan`).
Docker: `docker compose up --build`.

## Test and evaluate
    pytest
    python -m evaluation.safety_eval
    python -m evaluation.hallucination_eval --mode detector
    python -m evaluation.hallucination_eval --mode pipeline --languages hi,pa,bn,ta,te --fail-on-regression

## Before real use
- Have a clinician review `rag/documents/*.md` (drafts).
- Have native speakers review outputs per language (tier 2 languages especially).
- Grow `evaluation/datasets/test_cases.json` with real, anonymised reports.

## What each test gets
For every lab value: what the test is, what your result means, should I be worried, and when to see a doctor,
all in the chosen language. "When to see a doctor" follows an urgency level decided by code
(routine / review / soon / prompt) and lists emergency warning symptoms from the knowledge base.
The urgency thresholds in `range_checker.py` are a heuristic and must be validated by a clinician.
Tests are sent to the LLM in small batches (`LLM_BATCH_SIZE`); if one batch fails verification only those
tests show the localised basic template, the rest keep their full explanation.
