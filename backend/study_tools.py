# backend/study_tools.py - VERSION ENRICHIE AUTOMATIQUE
"""
Outils d'étude pour StudyGenie avec enrichissement visuel automatique.
Génère flashcards, quiz, résumés avec visuels contextuels.
TOUS les contenus sont automatiquement enrichis avec des schémas pertinents.
"""

import anthropic
import os
from typing import Dict, List

# Import conditionnel de l'enrichissement visuel
try:
    from visual_enrichment import enrich_summary, enrich_explanation, enrich_qa_response, auto_enrich_content
    VISUAL_ENRICHMENT_ENABLED = True
    print("✅ Enrichissement visuel activé")
except ImportError as e:
    print(f"⚠️ visual_enrichment.py non trouvé: {e}")
    VISUAL_ENRICHMENT_ENABLED = False
    # Fonctions fallback
    def enrich_summary(text): return text if text else ""
    def enrich_explanation(text): return text if text else ""
    def enrich_qa_response(text): return text if text else ""
    def auto_enrich_content(text, _type=""): return text if text else ""
except Exception as e:
    print(f"❌ Erreur import visual_enrichment: {e}")
    VISUAL_ENRICHMENT_ENABLED = False
    # Fonctions fallback
    def enrich_summary(text): return text if text else ""
    def enrich_explanation(text): return text if text else ""
    def enrich_qa_response(text): return text if text else ""
    def auto_enrich_content(text, _type=""): return text if text else ""

# Initialiser client Anthropic
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def generate_flashcards(course_content: str, num_cards: int = 10, language: str = "fr") -> List[Dict]:
    """
    Génère des flashcards à partir du contenu du cours.
    Les réponses sont automatiquement enrichies avec des visuels contextuels.
    """
    
    lang_prompt = "en français" if language == "fr" else "in English"
    
    prompt = f"""Tu es un expert pédagogique. Génère exactement {num_cards} flashcards {lang_prompt} basées sur ce contenu de cours.

Contenu du cours:
{course_content[:3000]}

Format STRICT à respecter:
Q: [question claire et précise]
R: [réponse concise]
---

Génère exactement {num_cards} flashcards avec ce format."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response = message.content[0].text
        flashcards = []
        
        # Parser les flashcards
        cards = response.split('---')
        for card in cards:
            if 'Q:' in card and 'R:' in card:
                try:
                    q = card.split('R:')[0].replace('Q:', '').strip()
                    r = card.split('R:')[1].strip()
                    
                    # ✨ ENRICHISSEMENT AUTOMATIQUE de la réponse
                    try:
                        r_enriched = auto_enrich_content(r, "flashcard")
                    except Exception as e:
                        print(f"⚠️ Erreur enrichissement flashcard: {e}")
                        r_enriched = r  # Fallback sur réponse brute
                    
                    flashcards.append({
                        "question": q, 
                        "answer": r_enriched
                    })
                except Exception as e:
                    print(f"⚠️ Erreur parsing flashcard: {e}")
                    continue
        
        return flashcards[:num_cards]
    
    except Exception as e:
        print(f"Erreur génération flashcards: {e}")
        return []


def generate_quiz(course_content: str, num_questions: int = 5, language: str = "fr") -> List[Dict]:
    """
    Génère un quiz à choix multiples.
    Les feedbacks sont automatiquement enrichis avec des visuels contextuels.
    """
    
    lang_prompt = "en français" if language == "fr" else "in English"
    
    prompt = f"""Tu es un expert pédagogique. Génère un quiz de {num_questions} questions {lang_prompt}.

Contenu du cours:
{course_content[:3000]}

Format STRICT à respecter pour chaque question:
Q: [question]
A) [option A]
B) [option B]
C) [option C]
D) [option D]
CORRECT: [lettre de la bonne réponse]
FEEDBACK: [explication courte]
---

Génère exactement {num_questions} questions avec ce format."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response = message.content[0].text
        questions = []
        
        # Parser les questions
        q_blocks = response.split('---')
        for block in q_blocks:
            if 'Q:' in block and 'CORRECT:' in block:
                try:
                    q_text = block.split('A)')[0].replace('Q:', '').strip()
                    options = []
                    
                    for letter in ['A)', 'B)', 'C)', 'D)']:
                        if letter in block:
                            start = block.index(letter) + len(letter)
                            end = block.index(chr(ord(letter[0]) + 1) + ')') if chr(ord(letter[0]) + 1) + ')' in block else block.index('CORRECT:')
                            options.append(block[start:end].strip())
                    
                    correct_line = block.split('CORRECT:')[1].split('\n')[0].strip()
                    correct_idx = ord(correct_line[0].upper()) - ord('A')
                    
                    feedback = ""
                    if 'FEEDBACK:' in block:
                        feedback = block.split('FEEDBACK:')[1].strip()
                        # ✨ ENRICHISSEMENT AUTOMATIQUE du feedback
                        try:
                            feedback = auto_enrich_content(feedback, "quiz")
                        except Exception as e:
                            print(f"⚠️ Erreur enrichissement quiz: {e}")
                            # Garder le feedback original
                    
                    questions.append({
                        "question": q_text,
                        "options": options,
                        "correct": correct_idx,
                        "feedback": feedback
                    })
                except:
                    continue
        
        return questions[:num_questions]
    
    except Exception as e:
        print(f"Erreur génération quiz: {e}")
        return []



def generate_summary(course_content: str = None, course_id: int = None, length: str = "medium", language: str = "fr", **kwargs) -> str:
    """
    Génère un résumé automatique.

    - course_content: texte du cours (prioritaire)
    - length: "short" | "medium" | "long"
    - kwargs:
        - num_pages: int (objectif de longueur exprimé en pages; converti en cible de mots)
    """
    # Compat ancien appel (course_id sans contenu)
    if course_content is None:
        return "⚠️ Erreur: generate_summary() nécessite course_content (texte du cours)."

    lang_prompt = "en français" if language == "fr" else "in English"

    # Objectif pages -> mots (approximation stable)
    num_pages = int(kwargs.get("num_pages", 0) or 0)
    target_words = num_pages * 260 if num_pages > 0 else 0

    # Config longueur (base)
    length_configs = {
        "short": {
            "instruction": "COURT : 5-7 points clés, concis. ~300-450 mots.",
            "max_tokens": 3000,
            "content_cap": 8000,
        },
        "medium": {
            "instruction": "MOYEN : 8-12 points clés, explications concises. ~600-900 mots.",
            "max_tokens": 4500,
            "content_cap": 16000,
        },
        "long": {
            "instruction": "DÉTAILLÉ : 12-18 points clés, explications développées, exemples et applications. ~1000-1800 mots.",
            "max_tokens": 6500,
            "content_cap": 26000,
        }
    }

    config = length_configs.get(length, length_configs["medium"])

    # Ajuster matière envoyée au modèle selon num_pages (sans excès)
    content_cap = config["content_cap"]
    if num_pages > 0:
        content_cap = min(60000, max(content_cap, num_pages * 2000))

    # Ajuster tokens selon num_pages (cap safe)
    max_tokens_summary = config["max_tokens"]
    if num_pages > 0:
        max_tokens_summary = min(8000, max(max_tokens_summary, num_pages * 180))

    prompt = f"""Tu es un expert pédagogique. Crée un résumé structuré {lang_prompt} de ce cours.

Contenu du cours:
{course_content[:content_cap]}

**LONGUEUR REQUISE:** {config['instruction']}
{('**CIBLE:** ~' + str(target_words) + ' mots (objectif basé sur num_pages).') if target_words else ''}

Structure attendue:
# [Titre du cours]

## Introduction
- Contexte et objectifs (2-4 phrases)

## Points Clés
- Liste de points avec explications

## Formules / Définitions (si présentes dans le cours)
- Liste uniquement si le contenu du cours en contient

## Applications / Exemples (si présents dans le cours)
- Applications concrètes

## À retenir
- 3-6 phrases maximum

⚠️ Règles:
- Ne pas inventer de notions.
- Ne pas utiliser de placeholders ("Concept A", "Formule 1").
- Rester fidèle au contenu fourni.
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens_summary,
            messages=[{"role": "user", "content": prompt}]
        )
        summary = message.content[0].text
        return summary.strip() if summary else ""
    except Exception as e:
        print(f"Erreur génération résumé: {e}")
        return f"Erreur lors de la génération du résumé: {str(e)}"

def generate_explanation(question: str, answer: str, course_id: int, language: str = "fr") -> str:
    """
    Génère une explication pédagogique ENRICHIE.
    L'explication est automatiquement analysée et enrichie avec des visuels.
    """
    
    lang_prompt = "en français" if language == "fr" else "in English"
    
    prompt = f"""Tu es un professeur pédagogue. La réponse brute à la question est fournie ci-dessous.

Question: {question}
Réponse brute: {answer}

Ta mission: Transformer cette réponse en explication pédagogique complète {lang_prompt}.

Structure attendue:
1. Reformulation simple de la réponse
2. Contexte et pourquoi c'est important
3. Explication étape par étape si applicable
4. Exemples concrets
5. Points clés à retenir

Utilise du Markdown. Sois clair, engageant, pédagogique."""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        explanation = message.content[0].text
        
        # ✨ ENRICHISSEMENT AUTOMATIQUE AVEC VISUELS
        enriched_explanation = enrich_explanation(explanation)
        
        return enriched_explanation
    
    except Exception as e:
        print(f"Erreur génération explication: {e}")
        return answer  # Fallback sur la réponse brute


# ============================================
# EXEMPLE D'UTILISATION
# ============================================

if __name__ == "__main__":
    # Test du résumé enrichi
    sample_course = """
    La dérivée d'une fonction mesure son taux de variation. 
    Pour une fonction f(x), la dérivée f'(x) indique si la fonction croît ou décroît.
    
    Règles importantes:
    - Si f(x) = x^n, alors f'(x) = n·x^(n-1)
    - La dérivée d'une somme est la somme des dérivées
    - Point critique: f'(x) = 0
    
    Processus d'étude:
    1. Calculer la dérivée
    2. Trouver les points critiques
    3. Étudier le signe
    4. Tracer le tableau de variation
    """
    
    print("=== TEST RÉSUMÉ ENRICHI ===")
    summary = generate_summary(sample_course, length="short", language="fr")
    print(summary)
