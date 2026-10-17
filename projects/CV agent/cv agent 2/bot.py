"""Personal Telegram CV Career Agent.

Run locally with: py bot.py
The bot stores one private, editable job draft per Telegram chat under data/jobs.
"""

import asyncio
import json
import os
import re
import sys
import textwrap
import uuid
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from anthropic import Anthropic
import requests
from bs4 import BeautifulSoup
from docx import Document
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters


ROOT = Path(__file__).resolve().parent
BUILDER_DIR = ROOT.parent / "new cv and cover letter builder"
STAGE1_PROMPT_PATH = BUILDER_DIR / "claude_stage1_prompt.md"
COVER_SCHEMA_PATH = BUILDER_DIR / "cover_letter_content_example.json"
sys.path.insert(0, str(BUILDER_DIR))

from cover_letter_builder import build_cover_letter
from cv_builder import build_cv

DATA_DIR = ROOT / os.getenv("DATA_DIR", "data")
PROFILE_PATH = DATA_DIR / "master_profile.json"
MASTER_COVER_LETTER_PATH = ROOT / "CV and cover letter" / "Prateek_Parihar_CoverLetter_Generic_Final.docx"
JOBS_DIR = DATA_DIR / "jobs"
OUTPUT_DIR = ROOT / "output"
LOGS_DIR = ROOT / "logs"

ENV_PATH = ROOT.parent / "1.env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH, override=True)
ENV_SOURCE = "1.env or server environment variables"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>()]+")


def load_profile() -> dict[str, Any]:
    with PROFILE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_master_cover_letter() -> str:
    if not MASTER_COVER_LETTER_PATH.exists():
        return ""
    document = Document(MASTER_COVER_LETTER_PATH)
    return "\n".join(paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip())


def job_path(chat_id: int) -> Path:
    return JOBS_DIR / str(chat_id) / "current.json"


def load_job(chat_id: int) -> dict[str, Any] | None:
    path = job_path(chat_id)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_job(chat_id: int, job: dict[str, Any]) -> None:
    path = job_path(chat_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    job["updated_at"] = datetime.now(timezone.utc).isoformat()
    with path.open("w", encoding="utf-8") as handle:
        json.dump(job, handle, ensure_ascii=False, indent=2)


def extract_json(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError("The AI response did not contain JSON.")
    return json.loads(match.group(0))


def response_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []):
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def log_ai_parse_failure(raw_text: str, error: Exception) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    preview = raw_text.replace("\r", " ").replace("\n", " ")[:700]
    with (LOGS_DIR / "bot-error.log").open("a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now(timezone.utc).isoformat()} AI JSON parse failure: {error}; preview={preview!r}\n")


def ask_ai(prompt: str, max_tokens: int, system_prompt: str | None = None) -> dict[str, Any]:
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    json_instruction = (
        "Return only one valid JSON object. Do not include markdown fences, headings, "
        "commentary, apologies, or explanatory text before or after the JSON."
    )
    attempts = [
        prompt + "\n\n" + json_instruction,
        (
            "Your previous response could not be parsed by json.loads. Retry the same task. "
            "Output must be exactly one valid JSON object matching the requested schema. "
            "Use empty strings or empty arrays for unknown values.\n\n"
            + prompt
            + "\n\n"
            + json_instruction
        ),
    ]
    last_error: Exception | None = None
    last_raw = ""
    for attempt in attempts:
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system_prompt or json_instruction,
            messages=[{"role": "user", "content": attempt}],
        )
        last_raw = response_text(response)
        try:
            return extract_json(last_raw)
        except (ValueError, json.JSONDecodeError) as error:
            last_error = error
    if last_error:
        log_ai_parse_failure(last_raw, last_error)
        raise ValueError("The AI response was not valid JSON after retry. Please paste the job description text or try again.") from last_error
    raise ValueError("The AI response was empty.")


def clean_url(raw_url: str) -> str:
    url = raw_url.strip().rstrip(".,;:!?)］]}")
    if url.lower().startswith("www."):
        url = "https://" + url
    return url


def html_to_text(value: str) -> str:
    soup = BeautifulSoup(unescape(value or ""), "html.parser")
    return soup.get_text("\n", strip=True)


def find_job_posting(data: Any) -> dict[str, Any] | None:
    if isinstance(data, dict):
        item_type = data.get("@type")
        types = item_type if isinstance(item_type, list) else [item_type]
        if any(str(item).lower() == "jobposting" for item in types):
            return data
        for value in data.values():
            found = find_job_posting(value)
            if found:
                return found
    if isinstance(data, list):
        for item in data:
            found = find_job_posting(item)
            if found:
                return found
    return None


def jsonld_job_text(soup: BeautifulSoup) -> str | None:
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            posting = find_job_posting(json.loads(raw))
        except json.JSONDecodeError:
            continue
        if not posting:
            continue
        organisation = posting.get("hiringOrganization") or {}
        location = posting.get("jobLocation") or {}
        if isinstance(location, list):
            location = location[0] if location else {}
        address = location.get("address") if isinstance(location, dict) else {}
        parts = [
            f"Title: {posting.get('title', '')}",
            f"Company: {organisation.get('name', '') if isinstance(organisation, dict) else organisation}",
            f"Location: {address.get('addressLocality', '') if isinstance(address, dict) else ''}",
            f"Employment Type: {posting.get('employmentType', '')}",
            f"Industry: {posting.get('industry', '')}",
            "Description:",
            html_to_text(str(posting.get("description", ""))),
            "Responsibilities:",
            html_to_text(str(posting.get("responsibilities", ""))),
            "Qualifications:",
            html_to_text(str(posting.get("qualifications", ""))),
            "Skills:",
            html_to_text(str(posting.get("skills", ""))),
        ]
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(part for part in parts if part).strip())
        if len(text) >= 300:
            return text[:12000]
    return None


def fetch_job_url(url: str) -> tuple[str | None, str | None]:
    """Extract readable job-posting text. LinkedIn may still reject unauthenticated requests."""
    url = clean_url(url)
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
                "Accept-Language": "en-NZ,en;q=0.9",
            },
            timeout=20,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        structured_text = jsonld_job_text(soup)
        if structured_text:
            return structured_text, None
        for element in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            element.decompose()
        main = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup
        text = re.sub(r"\n{3,}", "\n\n", main.get_text("\n", strip=True))
        # A successful job page should have meaningful body content, not just a login wall.
        if re.search(r"sign in to (view|continue)|authwall|enable javascript|access denied", text, re.IGNORECASE):
            return None, "The site blocked automated reading or showed a login/JavaScript wall."
        if len(text) < 300:
            return None, "The page loaded, but it did not expose enough job-description text."
        return text[:12000], None
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else "unknown"
        return None, f"The job site returned HTTP {status}."
    except requests.Timeout:
        return None, "The job site timed out from this server PC."
    except requests.RequestException as error:
        return None, f"The server PC could not reach that link: {error.__class__.__name__}."


def short_profile(profile: dict[str, Any]) -> str:
    """The verified evidence supplied to the model; never ask it to fill factual gaps."""
    return json.dumps(profile, ensure_ascii=False, indent=2)


def load_stage1_prompt() -> str:
    text = STAGE1_PROMPT_PATH.read_text(encoding="utf-8")
    sections = text.split("\n---\n")
    if len(sections) < 3:
        raise ValueError("claude_stage1_prompt.md has an invalid structure.")
    return sections[1].strip()


def analyse_job(profile: dict[str, Any], jd: str) -> dict[str, Any]:
    return ask_ai(
                f"""You are an expert Senior Resume Writer, ATS Optimization Specialist, HR Recruiter,
and Career Coach. Read the complete job description and assess it against the verified
candidate profile below. Do not assume qualifications that are not in the profile.
Return JSON only with this schema:
{{
  "company": "",
    "position": "",
    "industry": "",
    "required_skills": [""],
    "preferred_skills": [""],
    "responsibilities": [""],
    "keywords": [""],
    "tools": [""],
    "soft_skills": [""],
    "experience_level": "",
    "ats_match_score": 0,
    "missing_skills": ["only truthful skill gaps"],
    "important_keywords_missing": ["JD keywords not evidenced in the profile"],
    "strengths": ["evidence-based strengths"],
    "weaknesses": ["genuine weaknesses or constraints"],
    "suggestions": ["truthful ways to improve interview chances"]
}}
Score is ATS match out of 100, not a guarantee of interview or hiring. Be direct and
recruiter-realistic. Never recommend inventing experience.

VERIFIED PROFILE:
{short_profile(profile)}

JOB DESCRIPTION:
{jd}""",
        1800,
    )


def generate_cv(profile: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    edits = "\n".join(f"- {item}" for item in job.get("edits", [])) or "- No extra edits requested."
    prompt = (
        f"BASE PROFILE:\n{short_profile(profile)}\n\n"
        f"JOB DESCRIPTION:\n{job['job_description']}\n\n"
        f"USER REQUESTED CHANGES:\n{edits}\n\n"
        "Generate the tailored JSON now."
    )
    try:
        return ask_ai(prompt, 4200, load_stage1_prompt())
    except (ValueError, json.JSONDecodeError) as error:
        raise ValueError("Claude returned malformed CV JSON after retry.") from error


def generate_letter(profile: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    edits = "\n".join(f"- {item}" for item in job.get("edits", [])) or "- No extra edits requested."
    master_letter = load_master_cover_letter() or "No master cover letter text was available. Use the verified profile as the factual source."
    cover_schema = json.loads(COVER_SCHEMA_PATH.read_text(encoding="utf-8"))
    system_prompt = (
        load_stage1_prompt().split("OUTPUT SCHEMA")[0]
        + "\nFor this task, return only one JSON object matching this cover letter schema exactly:\n"
        + json.dumps(cover_schema, ensure_ascii=False, indent=2)
    )
    prompt = (
        f"BASE PROFILE:\n{short_profile(profile)}\n\n"
        f"MASTER COVER LETTER STYLE CONTEXT:\n{master_letter}\n\n"
        f"JOB DESCRIPTION:\n{job['job_description']}\n\n"
        f"USER REQUESTED CHANGES:\n{edits}\n\n"
        f"Use today's date: {date.today().strftime('%d %B %Y')}."
    )
    try:
        return ask_ai(prompt, 2000, system_prompt)
    except (ValueError, json.JSONDecodeError) as error:
        raise ValueError("Claude returned malformed cover letter JSON after retry.") from error


def build_pdf(title: str, lines: list[str], path: Path) -> None:
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 0.12 * inch)]
    for line in lines:
        if line.startswith("# "):
            story.extend([Spacer(1, 0.08 * inch), Paragraph(line[2:], styles["Heading3"])])
        else:
            story.append(Paragraph(line.replace("&", "&amp;"), styles["BodyText"]))
    SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.55 * inch, rightMargin=0.55 * inch,
                      topMargin=0.5 * inch, bottomMargin=0.5 * inch).build(story)


def export_documents(profile: dict[str, Any], job: dict[str, Any]) -> list[Path]:
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = re.sub(r"[^A-Za-z0-9]+", "_", job["analysis"].get("position", "role")).strip("_") or "role"
    base = OUTPUT_DIR / f"Prateek_Parihar_{safe_title}_{stamp}"
    files: list[Path] = []
    if "cv" in job:
        cv = job["cv"]
        cv_docx, cv_pdf = Path(f"{base}_CV.docx"), Path(f"{base}_CV.pdf")
        build_cv(cv, str(cv_docx))
        cv_lines = [" | ".join(cv["contact_line"]), cv.get("tagline", ""), "# PROFESSIONAL SUMMARY", cv["summary"], "# SKILLS"]
        cv_lines.extend(cv.get("skills", []))
        cv_lines.append("# PROJECTS")
        for project in cv.get("projects", []):
            cv_lines.append(f"<b>{project['title']}</b>")
            cv_lines.extend(project.get("bullets", []))
        cv_lines.append("# EXPERIENCE")
        for item in cv.get("experience", []):
            cv_lines.append(f"<b>{item['title']}</b> | {item['dates']}")
            cv_lines.extend(item.get("bullets", []))
        cv_lines.append("# EDUCATION")
        for item in cv.get("education", []):
            cv_lines.append(f"<b>{item['title']}</b> | {item['dates']}")
            cv_lines.extend(item.get("bullets", []))
        if cv.get("certifications"):
            cv_lines.append("# CERTIFICATIONS")
            cv_lines.append(cv["certifications"])
        if cv.get("additional"):
            cv_lines.append("# ADDITIONAL EXPERIENCE")
            cv_lines.extend(cv["additional"])
        build_pdf(cv["name"], cv_lines, cv_pdf)
        files.extend([cv_pdf, cv_docx])
    if "letter" in job:
        letter_data = job["letter"]
        letter_docx, letter_pdf = Path(f"{base}_Cover_Letter.docx"), Path(f"{base}_Cover_Letter.pdf")
        build_cover_letter(letter_data, str(letter_docx))
        letter_lines = [
            letter_data["contact_line"],
            letter_data["date"],
            *letter_data["recipient_lines"],
            letter_data["salutation"],
            *letter_data["body_paragraphs"],
            letter_data["closing"],
            letter_data["sign_off_name"],
        ]
        build_pdf("Cover Letter", letter_lines, letter_pdf)
        files.extend([letter_pdf, letter_docx])
    return files


def keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1. Generate Resume", callback_data="generate_cv")],
        [InlineKeyboardButton("2. Edit Resume", callback_data="edit")],
        [InlineKeyboardButton("3. Generate Cover Letter", callback_data="generate_letter")],
        [InlineKeyboardButton("4. Generate Both", callback_data="generate_both")],
        [InlineKeyboardButton("5. Analyze Again", callback_data="analyze_again")],
    ])


def post_resume_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1. Edit Resume", callback_data="edit")],
        [InlineKeyboardButton("2. Generate Cover Letter", callback_data="generate_letter")],
        [InlineKeyboardButton("3. Export", callback_data="export")],
    ])


def post_letter_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Generate Resume", callback_data="generate_cv")],
        [InlineKeyboardButton("Edit Request", callback_data="edit")],
        [InlineKeyboardButton("Export", callback_data="export")],
    ])


def analysis_message(analysis: dict[str, Any]) -> str:
    def bullets(items: list[str], limit: int = 5) -> str:
        selected = [str(item).strip() for item in items if str(item).strip()][:limit]
        return "\n".join(f"• {item}" for item in selected) if selected else "None identified"

    return (
        f"✓ ATS Match Score: {analysis.get('ats_match_score', '—')}/100\n\n"
        f"Top Missing Skills\n{bullets(analysis.get('missing_skills', []))}\n\n"
        f"Top Missing Keywords\n{bullets(analysis.get('important_keywords_missing', []))}\n\n"
        f"Strongest Matches\n{bullets(analysis.get('strengths', []), 4)}\n\n"
        f"Main Risks\n{bullets(analysis.get('weaknesses', []), 4)}\n\n"
        f"Best Next Actions\n{bullets(analysis.get('suggestions', []), 4)}"
    )


def cv_message(cv: dict[str, Any]) -> str:
    review = cv.get("resume_review", {})
    if not review:
        return "Resume drafted from your verified profile using the new document template. Choose Export to receive PDF and editable DOCX files."

    def bullets(items: list[str]) -> str:
        selected = [str(item).strip() for item in items if str(item).strip()][:5]
        return "\n".join(f"• {item}" for item in selected) if selected else "None identified"
    return (
        f"Resume ATS Score\n{review.get('ats_score', '—')}/100\n\n"
        f"Missing Keywords (if any)\n{bullets(review.get('missing_keywords', []))}\n\n"
        f"Improvements Made\n{bullets(review.get('improvements_made', []))}\n\n"
        f"Keyword Coverage\n{bullets(review.get('keyword_coverage', []))}\n\n"
        f"Recruiter Feedback\n{review.get('recruiter_feedback', 'Resume drafted and ready for review.')}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Send or paste a full job description or job link. I will analyse ATS match first and wait for your choice before generating anything."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    chat_id = update.effective_chat.id
    current = load_job(chat_id)
    url_match = URL_RE.search(text)
    if current and current.get("awaiting_new_analysis"):
        current["awaiting_new_analysis"] = False
        save_job(chat_id, current)
        current = None
    if url_match:
        status = await update.message.reply_text("Reading the job link…")
        url = clean_url(url_match.group(0))
        jd, reason = await asyncio.to_thread(fetch_job_url, url)
        if not jd:
            await status.edit_text(
                f"I could not read the job description from that link. {reason or 'The site did not expose readable job text.'}\n\n"
                "Please paste the job description text here and I will analyse it immediately."
            )
            return
        await status.edit_text("Link read. Analysing ATS readiness…")
        try:
            profile = load_profile()
            analysis = await asyncio.to_thread(analyse_job, profile, jd)
            job = {"id": str(uuid.uuid4()), "job_description": jd, "source_url": url, "analysis": analysis, "edits": [], "created_at": datetime.now(timezone.utc).isoformat()}
            save_job(chat_id, job)
            await status.edit_text(analysis_message(analysis), reply_markup=keyboard())
        except Exception as error:
            await status.edit_text(f"I read the link but could not analyse it. {error}")
        return
    if current and len(text) < 1800:
        current.setdefault("edits", []).append(text)
        current["draft_stale"] = True
        save_job(chat_id, current)
        if "cv" in current:
            reply_markup = post_resume_keyboard()
        elif "letter" in current:
            reply_markup = post_letter_keyboard()
        else:
            reply_markup = keyboard()
        await update.message.reply_text("Saved for this job version. Choose Generate when ready.", reply_markup=reply_markup)
        return
    if len(text) < 120:
        await update.message.reply_text("Please paste the full job description (at least a few paragraphs).")
        return
    status = await update.message.reply_text("Analysing the job description and calculating ATS readiness…")
    try:
        profile = load_profile()
        analysis = await asyncio.to_thread(analyse_job, profile, text)
        job = {"id": str(uuid.uuid4()), "job_description": text, "analysis": analysis, "edits": [], "created_at": datetime.now(timezone.utc).isoformat()}
        save_job(chat_id, job)
        await status.edit_text(analysis_message(analysis), reply_markup=keyboard())
    except Exception as error:
        await status.edit_text(f"I could not analyse that job description. {error}")


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    job = load_job(chat_id)
    if not job:
        await query.edit_message_text("Please paste a job description first.")
        return
    if query.data == "edit":
        await query.edit_message_text("Send your change as a normal message. It applies only to this job version—for example: ‘remove the AI Agent project’ or ‘make the letter more direct’." )
        return
    if query.data == "analyze_again":
        job["awaiting_new_analysis"] = True
        save_job(chat_id, job)
        await query.edit_message_text("Paste the new job description or job link and I will analyse it from STEP 1.")
        return
    if query.data == "export":
        if job.get("draft_stale"):
            await query.edit_message_text("You have saved edits after the last draft. Please generate the resume or cover letter again before exporting.", reply_markup=post_resume_keyboard() if "cv" in job else post_letter_keyboard())
            return
        if "cv" not in job and "letter" not in job:
            await query.edit_message_text("Nothing has been generated yet. Choose Generate Resume, Generate Cover Letter, or Generate Both first.", reply_markup=keyboard())
            return
        status = await query.message.reply_text("Exporting generated documents…")
        try:
            profile = load_profile()
            files = await asyncio.to_thread(export_documents, profile, job)
            for file_path in files:
                with file_path.open("rb") as file:
                    await query.message.reply_document(document=file, filename=file_path.name)
            await status.edit_text("Export complete. Your generated PDF and editable DOCX files are ready.", reply_markup=post_resume_keyboard() if "cv" in job else post_letter_keyboard())
        except Exception as error:
            await status.edit_text(f"I could not export the documents. {error}", reply_markup=post_resume_keyboard() if "cv" in job else post_letter_keyboard())
        return
    status = await query.message.reply_text("Creating the requested draft…")
    try:
        profile = load_profile()
        if query.data in {"generate_cv", "generate_both"}:
            job["cv"] = await asyncio.to_thread(generate_cv, profile, job)
        if query.data in {"generate_letter", "generate_both"}:
            job["letter"] = await asyncio.to_thread(generate_letter, profile, job)
        job["draft_stale"] = False
        save_job(chat_id, job)
        if query.data == "generate_letter" and "cv" not in job:
            await status.edit_text("Cover letter drafted. Choose Export when you want the PDF and editable DOCX files.", reply_markup=post_letter_keyboard())
        else:
            message = cv_message(job["cv"])
            if query.data == "generate_both":
                message += "\n\nCover letter drafted as well. Choose Export when you want the files."
            await status.edit_text(message, reply_markup=post_resume_keyboard())
    except Exception as error:
        await status.edit_text(f"I could not generate the requested draft. {error}", reply_markup=keyboard())


def main() -> None:
    if not TELEGRAM_TOKEN or not ANTHROPIC_API_KEY:
        raise RuntimeError(f"Add TELEGRAM_TOKEN and CLAUDE_API_KEY to {ENV_SOURCE} before starting the bot.")
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    print("CV Career Agent is online. Paste a JD or job link in Telegram.", flush=True)
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(callbacks))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception:
        # Do not allow the Telegram client to echo a sensitive token in a traceback.
        raise RuntimeError(
            f"Telegram could not start. Check that TELEGRAM_TOKEN in {ENV_SOURCE} is a current token from BotFather and that this computer has internet access."
        ) from None


if __name__ == "__main__":
    main()
