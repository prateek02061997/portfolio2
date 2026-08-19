# CV Career Agent v2

A clean rebuild of the personal Telegram CV assistant. This folder is independent of the original bot in the parent directory.

## Product flow

1. Paste a job description, URL, or job-post screenshot into Telegram.
2. Receive an ATS readiness score, matched evidence, missing requirements, and honest gaps.
3. Choose to generate a CV or a human-style cover letter.
4. Give natural-language edits such as `remove the RAG project for this role` or `add this project`.
5. Download an application-ready PDF and editable DOCX.

## Planned architecture

```text
Telegram
  -> workflow controller
  -> master CV (verified facts) + per-job draft storage
  -> portfolio synchronisation and RAG retrieval
  -> controlled AI generation and quality checks
  -> PDF/DOCX export
```

`cv_data.py` and `pdf_generator.py` were copied from the original bot as reference assets. They will be migrated into the new data model and document-export layer deliberately; the original bot and its keys are not touched.

## Guardrails

- The bot must never invent work experience, qualifications, or outcomes.
- "ATS score" means an evidence-based readiness score, not a hiring guarantee.
- A master-CV update always requires explicit confirmation. Job-specific edits are isolated to that application.
- API keys stay in `.env`, which is intentionally excluded from Git.

## Next build order

1. Define and validate the master CV / project schema.
2. Implement JD intake and ATS analysis.
3. Add job-version editing and document export.
4. Add portfolio or GitHub synchronisation and RAG retrieval.
5. Add a constrained agent for review and improvement loops.
