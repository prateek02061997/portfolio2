import os
import re
import json
import tempfile

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from datetime import date


BLACK  = HexColor('#111111')
MUTED  = HexColor('#444444')
RULE   = HexColor('#aaaaaa')
W      = A4[0]


def _styles():
    return {
        'name': ParagraphStyle(
            'name', fontName='Helvetica-Bold', fontSize=18,
            alignment=TA_CENTER, textColor=BLACK,
            spaceAfter=3, spaceBefore=0, leading=22
        ),
        'contact': ParagraphStyle(
            'contact', fontName='Helvetica', fontSize=9,
            alignment=TA_CENTER, textColor=MUTED,
            spaceAfter=1, leading=13
        ),
        'visa': ParagraphStyle(
            'visa', fontName='Helvetica-Oblique', fontSize=9,
            alignment=TA_CENTER, textColor=MUTED,
            spaceAfter=6, leading=12
        ),
        'section': ParagraphStyle(
            'section', fontName='Helvetica-Bold', fontSize=11,
            alignment=TA_LEFT, textColor=BLACK,
            spaceBefore=10, spaceAfter=1, leading=14
        ),
        'entry_title': ParagraphStyle(
            'entry_title', fontName='Helvetica-Bold', fontSize=10,
            alignment=TA_LEFT, textColor=BLACK,
            spaceBefore=5, spaceAfter=0, leading=13
        ),
        'entry_meta': ParagraphStyle(
            'entry_meta', fontName='Helvetica', fontSize=9,
            alignment=TA_LEFT, textColor=MUTED,
            spaceBefore=0, spaceAfter=1, leading=12
        ),
        'body': ParagraphStyle(
            'body', fontName='Helvetica', fontSize=9.5,
            alignment=TA_LEFT, textColor=BLACK,
            spaceBefore=0, spaceAfter=3, leading=13
        ),
        'bullet': ParagraphStyle(
            'bullet', fontName='Helvetica', fontSize=9.5,
            alignment=TA_LEFT, textColor=BLACK,
            leftIndent=12, firstLineIndent=-12,
            spaceBefore=0, spaceAfter=2, leading=13
        ),
    }


def _section_header(title, s):
    """Return [Paragraph, HRFlowable] for a section header."""
    return [
        Paragraph(title, s['section']),
        HRFlowable(width='100%', thickness=0.8, color=RULE, spaceAfter=4)
    ]


def _parse_json(raw: str) -> dict:
    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def generate_cv_pdf(cv_content: str, cv_data: dict) -> str:
    """
    Generate a CV PDF that matches the exact layout of Prateek_Parihar_CV.pdf.
    Uses tailored content from Claude but preserves original structure exactly.
    """
    tailored = _parse_json(cv_content)
    s = _styles()

    summary    = tailored.get('summary',    cv_data.get('summary', ''))
    skills     = tailored.get('skills',     cv_data.get('skills', {}))
    projects   = tailored.get('projects',   cv_data.get('projects', []))
    experience = tailored.get('experience', cv_data.get('experience', []))
    education  = tailored.get('education',  cv_data.get('education', []))
    certs      = cv_data.get('certifications', [])
    additional = cv_data.get('additional_experience', [])

    tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    path = tmp.name
    tmp.close()

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm
    )

    el = []

    # -- Header ----------------------------------------------------------------
    el.append(Paragraph(cv_data['name'], s['name']))

    contact_parts = [
        cv_data.get('location', ''),
        cv_data.get('phone', ''),
        cv_data.get('email', ''),
        cv_data.get('linkedin', ''),
        cv_data.get('portfolio', '')
    ]
    el.append(Paragraph('   |   '.join(p for p in contact_parts if p), s['contact']))

    visa = cv_data.get('visa', '')
    if visa:
        el.append(Paragraph(visa, s['visa']))

    # -- Professional Summary --------------------------------------------------
    if summary:
        el += _section_header('PROFESSIONAL SUMMARY', s)
        el.append(Paragraph(summary, s['body']))

    # -- Skills ----------------------------------------------------------------
    if skills:
        el += _section_header('SKILLS', s)
        if isinstance(skills, dict):
            for cat, items in skills.items():
                if items:
                    line = f"<b>{cat}:</b> {', '.join(items)}"
                    el.append(Paragraph(f"&#8226;  {line}", s['bullet']))
        elif isinstance(skills, list):
            el.append(Paragraph(', '.join(skills), s['body']))

    # -- Analytics Projects ----------------------------------------------------
    if projects:
        el += _section_header('ANALYTICS PROJECTS', s)
        for proj in projects[:4]:
            name = proj.get('name', '')
            role = proj.get('role', '')
            url  = proj.get('url', cv_data.get('portfolio', ''))

            title_text = name
            if role:
                title_text += f", {role}"
            if url:
                title_text += f"&nbsp;&nbsp;&nbsp;<font size='8' color='#666666'>{url}</font>"
            el.append(Paragraph(title_text, s['entry_title']))

            for b in proj.get('bullets', []):
                el.append(Paragraph(f"&#8226;  {b}", s['bullet']))

    # -- Professional Experience -----------------------------------------------
    if experience:
        el += _section_header('PROFESSIONAL EXPERIENCE', s)
        for job in experience:
            title   = job.get('title', '')
            company = job.get('company', '')
            period  = job.get('period', '')

            el.append(Paragraph(f"<b>{title}, {company}</b>", s['entry_title']))
            if period:
                el.append(Paragraph(period, s['entry_meta']))

            for b in job.get('bullets', []):
                el.append(Paragraph(f"&#8226;  {b}", s['bullet']))

    # -- Education -------------------------------------------------------------
    if education:
        el += _section_header('EDUCATION', s)
        for edu in education:
            degree = edu.get('degree', '')
            inst   = edu.get('institution', '')
            period = edu.get('period', '')
            note   = edu.get('note', '')

            parts = [p for p in [degree, inst, period] if p]
            el.append(Paragraph(', '.join(parts), s['entry_title']))
            if note:
                el.append(Paragraph(f"&#8226;  {note}", s['bullet']))

    # -- Certifications --------------------------------------------------------
    if certs:
        el += _section_header('CERTIFICATIONS', s)
        for cert in certs:
            el.append(Paragraph(f"&#8226;  {cert}", s['bullet']))

    # -- Additional Experience -------------------------------------------------
    if additional:
        el += _section_header('ADDITIONAL EXPERIENCE', s)
        for item in additional:
            el.append(Paragraph(f"&#8226;  {item}", s['bullet']))

    doc.build(el)
    return path


def generate_cover_letter_pdf(cl_content: str, cv_data: dict) -> str:
    """
    Generate a cover letter PDF matching the format of Prateek_Parihar_Cover_Letter_.pdf.
    cl_content is JSON from Claude with keys: hiring_manager, company, job_title,
    job_ref, job_location, greeting, paragraphs[], closing_line
    """
    _BLACK = HexColor('#111111')
    _MUTED = HexColor('#444444')
    _RULE  = HexColor('#aaaaaa')

    def st(name, **kw):
        defaults = dict(fontName='Helvetica', fontSize=11, textColor=_BLACK, leading=16)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    s_name    = st('cl_name',    fontName='Helvetica-Bold', fontSize=16,
                   alignment=TA_CENTER, spaceAfter=3, leading=20)
    s_contact = st('cl_contact', fontSize=9.5, alignment=TA_CENTER,
                   textColor=_MUTED, spaceAfter=14, leading=13)
    s_date    = st('cl_date',    fontSize=10.5, spaceAfter=14, leading=14)
    s_addr    = st('cl_addr',    fontSize=10.5, spaceAfter=2,  leading=14)
    s_re      = st('cl_re',      fontName='Helvetica-Bold', fontSize=10.5,
                   spaceAfter=12, leading=14)
    s_greet   = st('cl_greet',   fontSize=11, spaceAfter=10, leading=16)
    s_body    = st('cl_body',    fontSize=11, spaceAfter=10, leading=16)
    s_links   = st('cl_links',   fontSize=10, textColor=_MUTED, spaceAfter=10, leading=14)
    s_close   = st('cl_close',   fontSize=11, spaceAfter=4,  leading=16)
    s_sig     = st('cl_sig',     fontName='Helvetica-Bold', fontSize=11,
                   spaceAfter=0, leading=16)

    # Parse JSON from Claude
    data = {}
    match = re.search(r'\{[\s\S]*\}', cl_content)
    if match:
        try:
            data = json.loads(match.group())
        except Exception:
            pass

    hiring_manager = data.get('hiring_manager', '').strip()
    company        = data.get('company', '').strip()
    job_title      = data.get('job_title', '').strip()
    job_ref        = data.get('job_ref', '').strip()
    job_location   = data.get('job_location', '').strip()
    greeting       = data.get('greeting', 'Dear Hiring Manager,').strip()
    paragraphs     = data.get('paragraphs', [cl_content] if not data else ['Cover letter unavailable.'])
    closing_line   = data.get(
        'closing_line',
        "Thanks for taking the time to read this, I'd really welcome the chance to talk further."
    )

    tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    path = tmp.name
    tmp.close()

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=28*mm, rightMargin=28*mm,
        topMargin=25*mm, bottomMargin=25*mm
    )

    el = []

    # -- Name header -----------------------------------------------------------
    el.append(Paragraph(cv_data['name'], s_name))
    contact_line = '  |  '.join(filter(None, [
        cv_data.get('location', ''),
        cv_data.get('phone', ''),
        cv_data.get('email', ''),
    ]))
    el.append(Paragraph(contact_line, s_contact))
    el.append(HRFlowable(width='100%', thickness=0.8, color=_RULE, spaceAfter=16))

    # -- Date ------------------------------------------------------------------
    today = date.today()
    date_str = str(today.day) + today.strftime(' %B %Y')
    el.append(Paragraph(date_str, s_date))

    # -- Addressee -------------------------------------------------------------
    if hiring_manager:
        el.append(Paragraph(hiring_manager, s_addr))
    if company:
        el.append(Paragraph(company, s_addr))

    # -- Re: line --------------------------------------------------------------
    re_parts = [p for p in [job_title, job_location] if p]
    if job_ref:
        re_parts.append(f'Job Ref {job_ref}')
    if re_parts:
        el.append(Spacer(1, 6))
        el.append(Paragraph(f'Re: {", ".join(re_parts)}', s_re))

    # -- Greeting --------------------------------------------------------------
    el.append(Spacer(1, 8))
    el.append(Paragraph(greeting, s_greet))

    # -- Body paragraphs -------------------------------------------------------
    for para in paragraphs:
        cleaned = para.strip().replace('\n', ' ')
        if cleaned:
            el.append(Paragraph(cleaned, s_body))

    # -- Links section ---------------------------------------------------------
    el.append(Spacer(1, 4))
    el.append(Paragraph(
        "You can have a look at my LinkedIn, my project portfolio, and the tourism "
        "platform I built below.",
        s_body
    ))

    linkedin  = cv_data.get('linkedin',  'linkedin.com/in/pprateek26')
    portfolio = cv_data.get('portfolio', 'prateek02061997.github.io/Prateek-Portfolio')
    kiwi_url  = 'kiwibudgettours.com'

    links_text = (
        f'<a href="https://{linkedin}" color="#1a5276">{linkedin}</a>'
        '   |   '
        f'<a href="https://{portfolio}" color="#1a5276">{portfolio}</a>'
        '   |   '
        f'<a href="https://{kiwi_url}" color="#1a5276">{kiwi_url}</a>'
    )
    el.append(Paragraph(links_text, s_links))

    # -- Closing ---------------------------------------------------------------
    el.append(Spacer(1, 6))
    el.append(Paragraph(closing_line, s_body))
    el.append(Spacer(1, 10))
    el.append(Paragraph('Kind regards,', s_close))
    el.append(Paragraph(cv_data['name'].title(), s_sig))

    doc.build(el)
    return path
