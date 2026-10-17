# V2 design decisions

## Data sources

- **Master CV:** structured, verified information used as the source of truth.
- **Portfolio:** project details synced from the portfolio site or its GitHub repository.
- **Job description:** the user’s pasted text, URL, or screenshot.
- **Job draft:** a separate tailored CV/letter and edit history for one application.

## RAG

RAG is reserved for portfolio/project material and optional evidence documents. The process retrieves only relevant projects and facts for a job description, rather than sending every document to the model. The verified master CV remains structured data, not an unfiltered retrieval source.

## Agent

The agent can plan a bounded sequence: analyse the JD, retrieve evidence, draft, validate, and suggest revisions. It cannot fabricate claims or update the master CV without user confirmation. This keeps the experience helpful without letting autonomous steps damage factual accuracy.

## Token control

- Store portfolio content locally after synchronisation.
- Retrieve a small number of relevant chunks per JD.
- Reuse saved ATS analysis and drafts until the JD or edit changes.
- Cap review/improvement passes and ask before additional passes.
