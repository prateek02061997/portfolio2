import os
import re
import json
import tempfile

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether
from datetime import date


BLACK  = HexColor('#000000')
MUTED  = HexColor('#333333')
RULE   = HexColor('#000000')
PAGE   = letter          # 612 x 792 pt — matches reference CV
W      = PAGE[0]


def _styles():
    """Serif styles tuned to match Prateek_Parihar_CV.pdf (Liberation Serif / US Letter)."""
    return {
        'name': ParagraphStyle(
            'name', fontName='Times-Bold', fontSize=16,
            alignment=TA_CENTER, textColor=BLACK,
            spaceAfter=2, spaceBefore=0, leading=19
        ),
        'contact': ParagraphStyle(
            'contact', fontName='Times-Roman', fontSize=9,
            alignment=TA_CENTER, textColor=BLACK,
            spaceAfter=1, leading=12
        ),
        'visa': ParagraphStyle(
            'visa', fontName='Times-Roman', fontSize=9,
            alignment=TA_CENTER, textColor=BLACK,
            spaceAfter=4, leading=12
        ),
        'section': ParagraphStyle(
            'section', fontName='Times-Bold', fontSize=10.5,
            alignment=TA_LEFT, textColor=BLACK,
            spaceBefore=11, spaceAfter=1, leading=13
        ),
        'entry_title': ParagraphStyle(
            'entry_title', fontName='Times-Roman', fontSize=10.5,
            alignment=TA_LEFT, textColor=BLACK,
            spaceBefore=6, spaceAfter=0, leading=13
        ),
        'entry_meta': ParagraphStyle(
            'entry_meta', fontName='Times-Roman', fontSize=10,
            alignment=TA_LEFT, textColor=BLACK,
            spaceBefore=0, spaceAfter=1, leading=12
        ),
        'body': ParagraphStyle(
            'body', fontName='Times-Roman', fontSize=10,
            alignment=TA_LEFT, textColor=BLACK,
            spaceBefore=0, spaceAfter=3, leading=12
        ),
        'bullet': ParagraphStyle(
            'bullet', fontName='Times-Roman', fontSize=10,
            alignment=TA_LEFT, textColor=BLACK,
            leftIndent=14, firstLineIndent=-14,
            spaceBefore=0, spaceAfter=2.5, leading=12
        ),
    }


def _section_header(title, s):
    """Return [Paragraph, HRFlowable] for a section header."""
    return [
        Paragraph(title, s['section']),
        HRFlowable(width='100%', thickness=0.7, color=RULE, spaceAfter=4)
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
        path, pagesize=PAGE,
        leftMargin=40, rightMargin=40,
        topMargin=28, bottomMargin=32
    )

    el = []

    # -- Header ----------------------------------------------------------------
    el.append(Paragraph(cv_data['name'], s['name']))

    linkedin  = cv_data.get('linkedin', '')
    portfolio = cv_data.get('portfolio', '')
    email     = cv_data.get('email', '')

    def _link(url, label, href=None):
        href = href or f'https://{url}'
        return f'<a href="{href}" color="#1a5276"><u>{label}</u></a>'

    contact_parts = [
        cv_data.get('location', ''),
        cv_data.get('phone', ''),
        _link(None, email, href=f'mailto:{email}') if email else '',
        _link(linkedin, linkedin) if linkedin else '',
        _link(portfolio, portfolio) if portfolio else '',
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
        header = _section_header('ANALYTICS PROJECTS', s)
        for i, proj in enumerate(projects):
            name = proj.get('name', '')
            role = proj.get('role', '')
            url  = proj.get('url', '')

            title_text = f"<b>{name},</b>"
            if role:
                title_text += f" <i>{role}</i>"
            if url:
                title_text += (
                    f"  <font size='9'>"
                    f'<a href="https://{url}" color="#1a5276"><u>{url}</u></a>'
                    f"</font>"
                )
            block = [Paragraph(title_text, s['entry_title'])]
            for b in proj.get('bullets', []):
                block.append(Paragraph(f"&#8226;  {b}", s['bullet']))

            # Keep each project intact; bind the section header to the first one
            el.append(KeepTogether((header + block) if i == 0 else block))

    # -- Professional Experience -----------------------------------------------
    if experience:
        header = _section_header('PROFESSIONAL EXPERIENCE', s)
        for i, job in enumerate(experience):
            title   = job.get('title', '')
            company = job.get('company', '')
            period  = job.get('period', '')

            block = [Paragraph(f"<b>{title},</b> <i>{company}</i>", s['entry_title'])]
            if period:
                block.append(Paragraph(period, s['entry_meta']))
            for b in job.get('bullets', []):
                block.append(Paragraph(f"&#8226;  {b}", s['bullet']))

            # Keep each job intact; bind the section header to the first one
            el.append(KeepTogether((header + block) if i == 0 else block))

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
        defaults = dict(fontName='Times-Roman', fontSize=11, textColor=_BLACK,
                        leading=14, alignment=TA_LEFT)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    s_name    = st('cl_name',    fontName='Times-Bold', fontSize=12,
                   spaceAfter=9, leading=15)
    s_contact = st('cl_contact', fontSize=11, spaceAfter=9)
    s_date    = st('cl_date',    fontSize=11, spaceAfter=9)
    s_addr    = st('cl_addr',    fontSize=11, spaceAfter=9)
    s_re      = st('cl_re',      fontSize=11, spaceAfter=9)
    s_greet   = st('cl_greet',   fontSize=11, spaceAfter=9)
    s_body    = st('cl_body',    fontSize=11, spaceAfter=11)
    s_links   = st('cl_links',   fontSize=10, spaceAfter=11)
    s_close   = st('cl_close',   fontSize=11, spaceAfter=2)
    s_sig     = st('cl_sig',     fontSize=11, spaceAfter=0)

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
        path, pagesize=PAGE,
        leftMargin=45, rightMargin=45,
        topMargin=40, bottomMargin=40
    )

    el = []

    # -- Name header (left-aligned, serif — matches reference) -----------------
    el.append(Paragraph(cv_data['name'].title(), s_name))
    contact_line = '  |  '.join(filter(None, [
        cv_data.get('location', ''),
        cv_data.get('phone', ''),
        cv_data.get('email', ''),
    ]))
    el.append(Paragraph(contact_line, s_contact))

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
        el.append(Paragraph(f'Re: {", ".join(re_parts)}', s_re))

    # -- Greeting --------------------------------------------------------------
    el.append(Paragraph(greeting, s_greet))

    # -- Body paragraphs -------------------------------------------------------
    for para in paragraphs:
        cleaned = para.strip().replace('\n', ' ')
        if cleaned:
            el.append(Paragraph(cleaned, s_body))

    # -- Links section ---------------------------------------------------------
    el.append(Paragraph(
        "You can have a look at my LinkedIn, my project portfolio, and the tourism "
        "platform I built below.",
        s_body
    ))

    linkedin  = cv_data.get('linkedin',  'linkedin.com/in/pprateek26')
    portfolio = cv_data.get('portfolio', 'prateek02061997.github.io/Prateek-Portfolio')
    kiwi_url  = 'kiwibudgettours.com'

    links_text = (
        f'<a href="https://{linkedin}" color="#1a5276"><u>{linkedin}</u></a>'
        '   |   '
        f'<a href="https://{portfolio}" color="#1a5276"><u>{portfolio}</u></a>'
        '   |   '
        f'<a href="https://{kiwi_url}" color="#1a5276"><u>{kiwi_url}</u></a>'
    )
    el.append(Paragraph(links_text, s_links))

    # -- Closing ---------------------------------------------------------------
    el.append(Paragraph(closing_line, s_body))
    el.append(Paragraph(f"Kind regards, {cv_data['name'].title()}", s_sig))

    doc.build(el)
    return path
