# backend/pdf_export.py - Export PDF StudyGenie
"""
Module d'export PDF pour Q&A, Flashcards, Quiz, Résumé
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from io import BytesIO
from datetime import datetime
import re


def clean_text(text: str) -> str:
    """Nettoie du texte pour un rendu PDF fiable (ReportLab Paragraph).

    - Retire Markdown basique
    - Supprime les blocs ```...``` (ASCII/art) qui causent des carrés noirs
    - Supprime les caractères box-drawing/blocs (■, █, ─, │, etc.)
    - Échappe les entités XML (& < >) pour ReportLab
    """
    if text is None:
        return ""

    text = str(text)

    # 1) Supprimer blocs code/ASCII (triple backticks)
    text = re.sub(r"```[\s\S]*?```", "", text)

    # 2) Retirer markdown basique
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)

    # 3) Remplacer symboles fragiles
    text = text.replace('×', 'x').replace('→', '->').replace('←', '<-')

    # 4) Supprimer caractères qui produisent des carrés / box drawing
    text = re.sub(r"[■█▄▀]+", "", text)
    text = re.sub(r"[│┌┐└┘─┬┴┼╔╗╚╝═]+", "", text)

    # 5) Supprimer emojis courants
    for emo in ['✅','❌','📥','📄','📝','🎓','💡','⚠️','🔍','🎴','📋','🔁','⬅️','➡️','👁️','🙈','⭐']:
        text = text.replace(emo, '')

    # 6) Retirer caractères de contrôle
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)

    # 7) Normaliser espaces
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\n+", "\n\n", text).strip()

    # 8) Échapper XML pour ReportLab Paragraph
    from xml.sax.saxutils import escape as _escape
    text = _escape(text)

    return text


def export_qa_to_pdf(question: str, answer: str, sources: list, course_name: str) -> BytesIO:
    """Exporte Q&A en PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    # Titre
    title = Paragraph(f"<b>Q&A - {course_name}</b>", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 0.5*inch))
    
    # Question
    story.append(Paragraph("<b>Question :</b>", styles['Heading2']))
    story.append(Paragraph(clean_text(question), styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Réponse
    story.append(Paragraph("<b>Réponse :</b>", styles['Heading2']))
    for para in clean_text(answer).split('\n\n'):
        if para.strip():
            story.append(Paragraph(para, styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def export_flashcards_to_pdf(flashcards: list, course_name: str) -> BytesIO:
    """Exporte Flashcards en PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    story.append(Paragraph(f"<b>Flashcards - {course_name}</b>", styles['Title']))
    story.append(Spacer(1, 0.5*inch))
    
    for i, card in enumerate(flashcards, 1):
        story.append(Paragraph(f"<b>Carte {i}/{len(flashcards)}</b>", styles['Heading2']))
        story.append(Paragraph(f"Q: {clean_text(card['question'])}", styles['Normal']))
        story.append(Paragraph(f"R: {clean_text(card['answer'])}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def export_quiz_to_pdf(questions: list, course_name: str) -> BytesIO:
    """Exporte Quiz en PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    story.append(Paragraph(f"<b>Quiz - {course_name}</b>", styles['Title']))
    story.append(Spacer(1, 0.5*inch))
    
    letters = ['A', 'B', 'C', 'D']
    
    for i, q in enumerate(questions, 1):
        story.append(Paragraph(f"<b>Q{i}:</b> {clean_text(q['question'])}", styles['Heading2']))
        for j, opt in enumerate(q.get('options', [])):
            opt_clean = re.sub(r'^[A-D]\)', '', clean_text(opt)).strip()
            story.append(Paragraph(f"{letters[j]}) {opt_clean}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
    
    # Page réponses
    story.append(PageBreak())
    story.append(Paragraph("<b>Réponses</b>", styles['Title']))
    
    for i, q in enumerate(questions, 1):
        correct = q.get('correct', 0)
        if isinstance(correct, str):
            correct_letter = correct[0].upper()
        else:
            correct_letter = letters[correct] if correct < 4 else 'A'
        story.append(Paragraph(f"Q{i}: {correct_letter}", styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer


def export_summary_to_pdf(summary: str, course_name: str) -> BytesIO:
    """Exporte Résumé en PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    story.append(Paragraph(f"<b>Résumé - {course_name}</b>", styles['Title']))
    story.append(Spacer(1, 0.5*inch))
    
    for line in summary.split('\n'):
        line = line.strip()
        if not line:
            continue
        if line.startswith('# '):
            story.append(Paragraph(line[2:], styles['Heading1']))
        elif line.startswith('## '):
            story.append(Paragraph(line[3:], styles['Heading2']))
        elif line.startswith('- '):
            story.append(Paragraph(f"• {clean_text(line[2:])}", styles['Normal']))
        else:
            story.append(Paragraph(clean_text(line), styles['Normal']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer
