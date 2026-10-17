import os
import re
import sys
import base64
import tempfile
import threading
from typing import Optional
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

sys.stdout.reconfigure(encoding='utf-8')
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from anthropic import Anthropic
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)

from cv_data import CV_DATA
from prompts import get_cv_prompt, get_cover_letter_prompt
from pdf_generator import generate_cv_pdf, generate_cover_letter_pdf

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "1.env")
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH, override=True)
ENV_SOURCE = "1.env or server environment variables"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CLAUDE_API_KEY  = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
MODEL           = "claude-sonnet-4-6"

client = Anthropic(api_key=CLAUDE_API_KEY)


# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_url(url: str) -> Optional[str]:
    """Scrape readable text from a job posting URL."""
    try:
        resp = requests.get(
            url,
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=15
        )
        soup = BeautifulSoup(resp.text, 'html.parser')
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator='\n', strip=True)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text[:5000]
    except Exception:
        return None


# ── Core document generation ─────────────────────────────────────────────────

async def generate_documents(update: Update, job_description: str):
    cv_path = cl_path = None
    status = await update.message.reply_text("⚙️ Analysing job description…")

    try:
        # Step 1 – Tailor CV
        await status.edit_text("📝 Tailoring your CV to the role…")
        cv_resp = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            messages=[{"role": "user",
                        "content": get_cv_prompt(job_description, CV_DATA)}]
        )
        cv_content = cv_resp.content[0].text

        # Step 2 – Cover letter
        await status.edit_text("✉️ Writing cover letter…")
        cl_resp = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            messages=[{"role": "user",
                        "content": get_cover_letter_prompt(job_description, CV_DATA)}]
        )
        cl_content = cl_resp.content[0].text

        # Step 3 – Build PDFs
        await status.edit_text("📄 Building PDF files…")
        cv_path = generate_cv_pdf(cv_content, CV_DATA)
        cl_path = generate_cover_letter_pdf(cl_content, CV_DATA)

        # Step 4 – Send files
        await status.edit_text("✅ Done! Sending your documents…")

        with open(cv_path, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename="Prateek_Parihar_CV.pdf",
                caption="📄 *ATS-Optimised CV*",
                parse_mode="Markdown"
            )

        with open(cl_path, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename="Prateek_Parihar_Cover_Letter.pdf",
                caption="✉️ *Cover Letter*",
                parse_mode="Markdown"
            )

        await status.delete()

    except Exception as err:
        await status.edit_text(
            f"❌ Something went wrong:\n`{err}`\n\nPlease try again.",
            parse_mode="Markdown"
        )
    finally:
        # Clean up temp files regardless of success/failure
        for p in (cv_path, cl_path):
            if not p:
                continue
            try:
                os.unlink(p)
            except Exception:
                pass


# ── Telegram handlers ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Hi Prateek!*\n\n"
        "Send me a job and I'll instantly generate:\n"
        "✅ ATS-Optimised CV (PDF)\n"
        "✅ Tailored Cover Letter (PDF)\n\n"
        "You can send:\n"
        "📝 Paste the job description text\n"
        "🔗 A job listing URL\n"
        "📷 A screenshot of the job posting\n\n"
        "_Ready when you are!_",
        parse_mode="Markdown"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # Detect URL
    url_match = re.search(r'https?://\S+', text)
    if url_match:
        await update.message.reply_text("🔗 Fetching job description from URL…")
        jd = fetch_url(url_match.group())
        if not jd:
            await update.message.reply_text(
                "❌ Couldn't fetch that URL.\n"
                "Please paste the job description text directly instead."
            )
            return
    else:
        jd = text

    if len(jd.strip()) < 80:
        await update.message.reply_text(
            "⚠️ That looks too short for a job description.\n"
            "Please paste the full text."
        )
        return

    await generate_documents(update, jd)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📷 Reading screenshot with AI vision…")

    try:
        photo = update.message.photo[-1]          # largest resolution
        file  = await context.bot.get_file(photo.file_id)

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            img_path = tmp.name

        with open(img_path, 'rb') as f:
            img_b64 = base64.standard_b64encode(f.read()).decode('utf-8')
        os.unlink(img_path)

        # Claude Vision — extract job description text
        vision_resp = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": img_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract the complete job description from this screenshot. "
                            "Include: job title, company name, location, salary if shown, "
                            "responsibilities, requirements, and qualifications. "
                            "Return the raw text only."
                        )
                    }
                ]
            }]
        )

        jd = vision_resp.content[0].text
        await generate_documents(update, jd)

    except Exception as err:
        await update.message.reply_text(
            f"❌ Could not read the image: `{err}`\n"
            "Try sending the text or URL instead.",
            parse_mode="Markdown"
        )


# ── Railway health server ────────────────────────────────────────────────────

def _start_health_server():
    port = int(os.environ.get("PORT", 8080))
    class _H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        def log_message(self, *args): pass
    t = threading.Thread(target=HTTPServer(('', port), _H).serve_forever, daemon=True)
    t.start()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    _start_health_server()

    if not TELEGRAM_TOKEN:
        print(f"ERROR: TELEGRAM_TOKEN missing in {ENV_SOURCE}")
        return
    if not CLAUDE_API_KEY or CLAUDE_API_KEY == "paste_your_NEW_claude_api_key_here":
        print(f"ERROR: CLAUDE_API_KEY missing in {ENV_SOURCE} — add your new key first!")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("✅ CV Bot is running!")
    print("   Open Telegram → @PrateekCVbot → /start")
    print("   Press Ctrl+C to stop.\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
