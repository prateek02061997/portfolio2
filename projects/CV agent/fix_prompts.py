new_cl = '''

def get_cover_letter_prompt(job_description: str, cv_data: dict) -> str:
    return f"""You are writing a cover letter for Prateek Parihar. Write it the way a real person would — conversational, direct, confident — not like a template.

Study this SAMPLE cover letter and write in exactly this voice and style:
---
Dear Matt,
I\'m writing to apply for the Data Analyst role on your Digital team. What caught my attention about this one isn\'t just the tools list, it\'s the variety. Getting to work across infrastructure, environmental and engineering projects, and actually seeing data make a difference to how those projects run, is exactly the kind of work I want to be doing.

I hold a Master of Applied Business (Business Analytics) from Unitec, and Excel, Power BI and SQL are tools I use every day, not just ones I\'ve studied. In my current role at AA New Zealand, I work with operational and performance data to find the root cause behind an issue, not just report on it. Before that, at Wipro, I spent close to a year and a half running data quality checks, calibrations and UAT across large datasets, catching inconsistencies before they became someone else\'s problem. That\'s the same instinct this role is asking for.

A few other things from the ad that line up with how I actually work: I\'ve supported automation and process improvement initiatives in my own project work, including building a small AI powered assistant that pulls answers from a set of documents automatically rather than someone doing it by hand. I keep documentation accurate as I go, not as an afterthought, and I\'ve spent most of my career working inside project teams with people from different backgrounds and priorities, so building an effective working relationship across a business isn\'t new to me, it\'s just what the job has always required.

I also manage my own small tourism business, Kiwi Budget Tours, on the side, which has taught me a lot about delivering something end to end on a budget and a timeline, with no one else to catch what I miss.

I hold an NZ Open Work Visa valid to February 2029, so there\'s no sponsorship needed and I can start as soon as you need me to.
---

RULES:
1. Extract hiring manager FIRST NAME ONLY from JD if mentioned. If not found, use empty string.
2. Extract company name and exact job title from the JD.
3. Extract job reference number if mentioned (look for "Ref", "Reference", "Job ID", "Req").
4. Extract job location city if mentioned.
5. Write EXACTLY 4 paragraphs in first person, natural, human voice — no clichés, no templates:
   - Para 1: State the role and what specifically caught attention about THIS job (not generic)
   - Para 2: Draw 2-3 direct lines from Prateek\'s real jobs to what the JD is asking for
   - Para 3: More specific examples that match the JD — real details, real projects
   - Para 4: Visa note + warm confident close
6. Under 340 words total across all paragraphs.
7. No bullet points, no bold, no headings — just flowing paragraphs.
8. Never start a paragraph with "I am", "I would", "I am excited", "I am passionate".
9. The closing_line must always be exactly: "Thanks for taking the time to read this, I\'d really welcome the chance to talk further."

Prateek\'s real background to draw from:
- AA New Zealand (current, Apr 2026-present): data logician, roadside telemetry analytics, protecting service KPIs, root cause analysis
- Teleperformance/Uber Eats: customer insights specialist, root cause analysis, weekly trend reports for leadership
- Upstox: customer onboarding analytics, isolated operational bottlenecks
- Wipro: data associate, SQL + Power BI, data quality checks, calibrations, UAT, large healthcare datasets
- Kiwi Budget Tours: founder, built AI-powered tourism platform (kiwibudgettours.com), runs it solo end-to-end
- Gen AI project: 70% reduction in manual reporting time using Claude + OpenAI API
- Gilmours project: identified 20% delivery delay reduction through process redesign
- RAG assistant: built retrieval pipeline with TF-IDF and cosine similarity
- MAB Business Analytics, Unitec 2025 | Azure AI-900 | Google Analytics certified
- NZ Open Work Visa valid to Feb 2029, no sponsorship needed

Return ONLY valid JSON — nothing else, no markdown, no extra text:
{{{{
  "hiring_manager": "First name only or empty string",
  "company": "Company name",
  "job_title": "Exact job title from JD",
  "job_ref": "Reference number or empty string",
  "job_location": "City or empty string",
  "greeting": "Dear Matt," or "Dear Hiring Manager,",
  "paragraphs": ["paragraph 1 text", "paragraph 2 text", "paragraph 3 text", "paragraph 4 text"],
  "closing_line": "Thanks for taking the time to read this, I\'d really welcome the chance to talk further."
}}}}

JOB DESCRIPTION:
{{job_description}}
"""
'''

with open('prompts.py', 'r') as f:
    content = f.read()

first_func_end = content.index('def get_cover_letter_prompt')
cv_prompt_section = content[:first_func_end].rstrip()

new_content = cv_prompt_section + new_cl

with open('prompts.py', 'w') as f:
    f.write(new_content)

print('Done. New prompts.py written successfully.')
