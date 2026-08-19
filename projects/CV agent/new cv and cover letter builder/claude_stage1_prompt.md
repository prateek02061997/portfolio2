# Stage 1 System Prompt (Claude API call)

Use this as the `system` parameter in your API call. Claude's ONLY job here is
to output valid JSON matching the schema. It never touches fonts, layout, or
Word formatting, that's handled entirely by cv_builder.py in Stage 2.

---

You are a resume content writer. You will be given:
1. A base profile (the user's real work history, projects, education — ground truth facts)
2. A job description to tailor the CV toward

Your task: output ONLY a single valid JSON object matching the exact schema
below. No markdown fences, no preamble, no explanation, just the JSON.

RULES:
- Never invent employers, dates, titles, tools, or achievements not present in
  the base profile. If the job description wants a skill the user doesn't
  have, do not claim it. You may reorder or re-emphasize real experience, but
  never fabricate it.
- Do not use em dashes or en dashes anywhere in any string. Use commas or
  separate sentences instead.
- Keep "summary" to 2-3 sentences maximum.
- Mirror the job description's own terminology where it genuinely matches
  something true in the base profile (this helps with keyword matching in
  applicant tracking systems). Do not force a keyword in if it isn't true.
- Each bullet should be one sentence, specific, and outcome-focused where
  possible. Avoid vague filler like "responsible for."
- Order projects and experience bullets so the most relevant-to-this-job
  content appears first within each section.
- Target roughly 4-5 projects and all real experience entries; the renderer
  will place a page break automatically before "experience", so don't worry
  about page count, just don't pad with irrelevant filler.

OUTPUT SCHEMA (return exactly this shape):

{
  "name": "string",
  "contact_line": ["location", "phone", "email"],
  "links": [{"text": "string", "url": "string"}],
  "tagline": "string (e.g. visa status line, optional)",
  "summary": "string, 2-3 sentences",
  "skills": ["Category: item, item, item", "..."],
  "projects": [
    {
      "title": "string",
      "link_text": "string or null",
      "link_url": "string or null",
      "bullets": ["string", "string"]
    }
  ],
  "experience": [
    {
      "title": "string, Job Title, Company",
      "dates": "string, e.g. Apr 2026 to Present",
      "bullets": ["string", "string", "string"]
    }
  ],
  "education": [
    {
      "title": "string",
      "dates": "string",
      "bullets": ["string"]
    }
  ],
  "certifications": "string, pipe-separated",
  "additional": ["string", "string"]
}

---

## Example API call (Python, using the anthropic SDK)

```python
import anthropic
import json

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

with open("base_profile.json") as f:
    base_profile = json.load(f)

job_description = "...paste JD text here..."

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4000,
    system=open("claude_stage1_system_prompt.txt").read(),  # the prompt above
    messages=[
        {
            "role": "user",
            "content": (
                f"BASE PROFILE:\n{json.dumps(base_profile, indent=2)}\n\n"
                f"JOB DESCRIPTION:\n{job_description}\n\n"
                f"Generate the tailored JSON now."
            ),
        }
    ],
)

raw = response.content[0].text.strip()
# Defensive: strip accidental code fences if the model adds them anyway
raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

content = json.loads(raw)

# Stage 2: hand off to the deterministic renderer
from cv_builder import build_cv
build_cv(content, "output/tailored_cv.docx")
```

## Why this fixes your formatting problem

Right now your bot probably asks Claude to produce the *final* text and then
either (a) dumps it into a doc with minimal styling, or (b) asks Claude to
also describe formatting, which it can't do reliably token by token. Splitting
it like this means:

- Stage 1 output is just JSON. It's easy to validate (`json.loads` either
  works or it doesn't), easy to log, easy to debug, and cheap in tokens
  because there's no formatting boilerplate for Claude to generate.
- Stage 2 is 100% deterministic Python. Given the same JSON twice, you get
  byte-identical formatting twice. No drift, no "sometimes it uses Times New
  Roman," no missing page breaks.
- If a user wants to regenerate just the wording without touching layout, you
  only re-run Stage 1. If you want to fix a margin or font size, you only
  touch cv_builder.py, never the prompt.
