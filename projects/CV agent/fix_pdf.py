import re
import json

NEW_CL_FUNCTION = '''

def generate_cover_letter_pdf(cl_content: str, cv_data: dict) -> str:
    """
    Generate a cover letter PDF matching the format of Prateek_Parihar_Cover_Letter_.pdf.
    cl_content is JSON from Claude with: hiring_manager, company, job_title, job_ref,
    job_location, greeting, paragraphs[], closing_line
    """
    import tempfile
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from datetime import date

    _BLACK = HexColor(\'#111111\')
    _MUTED = HexColor(\'#444444\')
    _RULE  = HexColor(\'#aaaaaa\')

    def st(name, **kw):
        defaults = dict(fontName=\'Helvetica\', fontSize=11, textColor=_BLACK, leading=16)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    s_name    = st(\'cl_name\',    fontName=\'Helvetica-Bold\', fontSize=16, alignment=TA_CENTER, spaceAfter=3, leading=20)
    s_contact = st(\'cl_contact\', fontSize=9.5, alignment=TA_CENTER, textColor=_MUTED, spaceAfter=14, leading=13)
    s_date    = st(\'cl_date\',    fontSize=10.5, spaceAfter=14, leading=14)
    s_addr    = st(\'cl_addr\',    fontSize=10.5, spaceAfter=2,  leading=14)
    s_re      = st(\'cl_re\',     fontName=\'Helvetica-Bold\', fontSize=10.5, spaceAfter=12, leading=14)
    s_greet   = st(\'cl_greet\',  fontSize=11, spaceAfter=10, leading=16)
    s_body    = st(\'cl_body\',   fontSize=11, spaceAfter=10, leading=16)
    s_links   = st(\'cl_links\',  fontSize=10, textColor=_MUTED, spaceAfter=10, leading=14)
    s_close   = st(\'cl_close\',  fontSize=11, spaceAfter=4,  leading=16)
    s_sig     = st(\'cl_sig\',    fontName=\'Helvetica-Bold\', fontSize=11, spaceAfter=0, leading=16)

    # Parse JSON from Claude
    data = {}
    match = re.search(r\'\\{[\\s\\S]*\\}\', cl_content)
    if match:
        try:
            data = json.loads(match.group())
        except Exception:
            pass

    hiring_manager = data.get(\'hiring_manager\', \'\').strip()
    company        = data.get(\'company\', \'\').strip()
    job_title      = data.get(\'job_title\', \'\').strip()
    job_ref        = data.get(\'job_ref\', \'\').strip()
    job_location   = data.get(\'job_location\', \'\').strip()
    greeting       = data.get(\'greeting\', \'Dear Hiring Manager,\').strip()
    paragraphs     = data.get(\'paragraphs\', [cl_content] if not data else [\'Cover letter content unavailable.\'])
    closing_line   = data.get(\'closing_line\', "Thanks for taking the time to read this, I\'d really welcome the chance to talk further.")

    tmp = tempfile.NamedTemporaryFile(suffix=\'.pdf\', delete=False)
    path = tmp.name
    tmp.close()

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=28*mm, rightMargin=28*mm,
        topMargin=25*mm, bottomMargin=25*mm
    )

    el = []

    # ── Name header ───────────────────────────────────────────────────────────
    el.append(Paragraph(cv_data[\'name\'], s_name))
    contact_line = \'  |  \'.join(filter(None, [
        cv_data.get(\'location\', \'\'),
        cv_data.get(\'phone\', \'\'),
        cv_data.get(\'email\', \'\'),
    ]))
    el.append(Paragraph(contact_line, s_contact))
    el.append(HRFlowable(width=\'100%\', thickness=0.8, color=_RULE, spaceAfter=16))

    # ── Date ──────────────────────────────────────────────────────────────────
    today = date.today()
    date_str = str(today.day) + today.strftime(\' %B %Y\')
    el.append(Paragraph(date_str, s_date))

    # ── Addressee ─────────────────────────────────────────────────────────────
    if hiring_manager:
        el.append(Paragraph(hiring_manager, s_addr))
    if company:
        el.append(Paragraph(company, s_addr))

    # ── Re: line ──────────────────────────────────────────────────────────────
    re_parts = [p for p in [job_title, job_location] if p]
    if job_ref:
        re_parts.append(f\'Job Ref {job_ref}\')
    if re_parts:
        el.append(Spacer(1, 6))
        el.append(Paragraph(f\'Re: {", ".join(re_parts)}\', s_re))

    # ── Greeting ──────────────────────────────────────────────────────────────
    el.append(Spacer(1, 8))
    el.append(Paragraph(greeting, s_greet))

    # ── Body paragraphs ───────────────────────────────────────────────────────
    for para in paragraphs:
        cleaned = para.strip().replace(\'\\n\', \' \')
        if cleaned:
            el.append(Paragraph(cleaned, s_body))

    # ── Links section ─────────────────────────────────────────────────────────
    el.append(Spacer(1, 4))
    el.append(Paragraph(
        \'You can have a look at my LinkedIn, my project portfolio, and the tourism platform I built below.\',
        s_body
    ))

    linkedin  = cv_data.get(\'linkedin\',  \'linkedin.com/in/pprateek26\')
    portfolio = cv_data.get(\'portfolio\', \'prateek02061997.github.io/Prateek-Portfolio\')
    kiwi_url  = \'kiwibudgettours.com\'

    links_text = (
        f\'<a href="https://{linkedin}" color="#1a5276">{linkedin}</a>\'
        \'   |   \'
        f\'<a href="https://{portfolio}" color="#1a5276">{portfolio}</a>\'
        \'   |   \'
        f\'<a href="https://{kiwi_url}" color="#1a5276">{kiwi_url}</a>\'
    )
    el.append(Paragraph(links_text, s_links))

    # ── Closing ───────────────────────────────────────────────────────────────
    el.append(Spacer(1, 6))
    el.append(Paragraph(closing_line, s_body))
    el.append(Spacer(1, 10))
    el.append(Paragraph(\'Kind regards,\', s_close))
    el.append(Paragraph(cv_data[\'name\'].title(), s_sig))

    doc.build(el)
    return path
'''

with open('pdf_generator.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find where the first generate_cover_letter_pdf starts
cl_start = content.index('\ndef generate_cover_letter_pdf(')
# Keep only everything before it (the CV generator + helpers)
before_cl = content[:cl_start]

new_content = before_cl + NEW_CL_FUNCTION

with open('pdf_generator.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f'Done. pdf_generator.py rewritten. Total chars: {len(new_content)}')
