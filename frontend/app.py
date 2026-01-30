# frontend/app.py - StudyGenie v2.0 (Design Premium + Features Mindgrasp)
"""
Frontend complet avec:
- Design moderne (glassmorphism, dark theme)
- Q&A avec RAG
- Flashcards automatiques
- Quiz automatiques
- Résumés
"""

import streamlit as st
import requests
import json
from pathlib import Path
import os
from datetime import datetime

import html
# ============================================
# DESIGN PREMIUM - IMPORT MODULE UI
# ============================================
try:
    from ui_premium import (
        load_premium_css,
        render_response_box,
        render_explanation_box,
        render_sources_section,
        render_question_input,
        render_action_buttons,
        render_course_header,
        render_stat_card,
        render_flashcard,
        render_quiz_option,
        render_progress_bar
    )
    PREMIUM_UI_LOADED = True
except ImportError:
    PREMIUM_UI_LOADED = False
    print("⚠️ ui_premium.py non trouvé - Mode design basique")

# ============================================
# CONFIGURATION
# ============================================

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="StudyGenie - AI Study Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Charger le CSS premium si disponible
if PREMIUM_UI_LOADED:
    load_premium_css()

# CSS additionnel pour boutons visibles
st.markdown("""
<style>
/* Forcer visibilité des boutons de formulaire */
.stFormSubmitButton > button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    border: none !important;
    padding: 0.5rem 2rem !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
}

.stFormSubmitButton > button:hover {
    opacity: 0.9 !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4) !important;
}

/* Bouton Annuler style différent */
.stFormSubmitButton:nth-child(2) > button {
    background: rgba(255, 255, 255, 0.1) !important;
    border: 2px solid rgba(255, 255, 255, 0.3) !important;
}
</style>
""", unsafe_allow_html=True)

# ============================================
# SESSION STATE
# ============================================

defaults = {
    'token': None,
    'user': None,
    'current_course': None,
    'show_create_course': False,
    'show_pricing': False,
    'show_landing': True,  # Afficher landing page par défaut
    'last_result': None,
    'last_question': "",
    'show_explanation': False,
    'current_tab': 'qa',  # qa, flashcards, quiz, summary
    'flashcards': [],
    'current_flashcard': 0,
    'show_flashcard_answer': False,
    'quiz_questions': [],
    'quiz_answers': {},
    'quiz_submitted': False,
    'summary': None,
    'lang_radio': 'FR'  # FR ou EN (source unique de vérité)
}

# ============================================
# TRADUCTIONS
# ============================================
TRANSLATIONS = {
    'fr': {
        # Navigation
        'app_title': '🎓 StudyGenie',
        'app_subtitle': 'Ton assistant IA pour étudier 10x plus vite',
        'logout': '🚪 Déconnexion',
        'back': '← Retour',
        'plan': 'Plan',
        'upgrade': '⭐ Passer Pro',
        'modify_plan': '✏️ Modifier le plan',
        'choose_plan': 'Choisir un plan',
        'current_plan': 'Plan actuel',
        'monthly': '/mois',
        
        # Login
        'login_title': '🔐 Connexion',
        'register_title': '📝 Inscription',
        'email': 'Email',
        'password': 'Mot de passe',
        'confirm_password': 'Confirmer',
        'full_name': 'Nom complet (optionnel)',
        'login_btn': '🔓 Se connecter',
        'register_btn': '🚀 S\'inscrire',
        'welcome_back': '✅ Content de te revoir !',
        'welcome': '✅ Bienvenue !',
        
        # Features
        'qa_title': '💬 Q&A',
        'qa_desc': 'Pose des questions sur tes cours',
        'flashcards_title': '🎴 Flashcards',
        'flashcards_desc': 'Génération automatique',
        'quiz_title': '📝 Quiz',
        'quiz_desc': 'Teste tes connaissances',
        'summary_title': '📋 Résumé',
        'summary_desc': 'Synthèse instantanée',
        
        # Dashboard
        'hello': 'Salut',
        'ready_to_learn': 'Prêt à apprendre quelque chose de nouveau ?',
        'my_courses': '📚 Mes Cours',
        'no_courses': '📭 Aucun cours. Crée ton premier cours pour commencer !',
        'new_course': '➕ Nouveau Cours',
        'study': '💬 Étudier',
        'upload': '📤 Upload',
        'courses': 'Cours',
        'questions': 'Questions',
        'this_month': 'Ce mois',
        
        # Course
        'create_course': '➕ Créer un Nouveau Cours',
        'course_name': 'Nom du cours *',
        'course_desc': 'Description',
        'create_btn': '✅ Créer',
        'cancel_btn': '❌ Annuler',
        'choose_study_mode': 'Choisis ton mode d\'étude',
        
        # Upload
        'upload_title': '📤 Upload Fichiers',
        'supported_formats': 'Formats supportés: PDF, DOCX, PPTX, Images, Audio, Vidéo',
        'upload_btn': '🚀 Upload & Indexer',
        'indexing': '⏳ Upload et indexation en cours...',
        'indexing_done': '✅ Indexation terminée !',
        
        # Q&A
        'ask_question': '💬 Pose ta question',
        'question_placeholder': 'Ex: Quelle est la formule de la dérivée ?',
        'search': '🔍 Chercher',
        'answer_found': '✅ Réponse trouvée !',
        'exact_answer': '✅ Réponse Exacte du Cours',
        'explanation': '💡 Explication Pédagogique',
        'show_explanation': '🔽 Voir l\'explication détaillée',
        'hide_explanation': '🔼 Masquer l\'explication',
        'sources': '📖 Sources',
        'new_question': '🧹 Nouvelle question',
        'confidence': 'Confiance',
        
        # Flashcards
        'flashcards_intro': 'Génère des flashcards automatiquement à partir de ton cours !',
        'num_flashcards': 'Nombre de flashcards',
        'generate_flashcards': '🎴 Générer Flashcards',
        'generating': '🤖 Génération en cours...',
        'card': 'Carte',
        'question': 'Question',
        'answer': 'Réponse',
        'previous': '⬅️ Précédent',
        'reveal': '👁️ Révéler',
        'hide': '🙈 Cacher',
        'next': '➡️ Suivant',
        'reset': '🔄 Reset',
        
        # Quiz
        'quiz_intro': 'Génère un quiz pour tester tes connaissances !',
        'num_questions': 'Nombre de questions',
        'generate_quiz': '📝 Générer Quiz',
        'submit': '✅ Soumettre',
        'new_quiz': '🔄 Nouveau Quiz',
        'excellent': '🎉 Excellent !',
        'good': '👍 Bien !',
        'keep_studying': '📚 Continue à réviser !',
        
        # Summary
        'summary_intro': 'Génère un résumé automatique de ton cours !',
        'summary_type': 'Type de résumé',
        'short': 'Court (1 page)',
        'medium': 'Moyen (2-3 pages)',
        'long': 'Détaillé (5+ pages)',
        'generate_summary': '📋 Générer Résumé',
        'download': '📥 Télécharger',
        'download_txt': '📄 Télécharger en TXT',
        'new_summary': '🔄 Nouveau Résumé',
        
        # Errors
        'email_required': 'Email et mot de passe requis',
        'passwords_mismatch': 'Les mots de passe ne correspondent pas',
        'api_unavailable': 'API non disponible',
        'no_content': 'Aucun contenu trouvé',
        'write_question': 'Écris une question d\'abord !'
    },
    'en': {
        # Navigation
        'app_title': '🎓 StudyGenie',
        'app_subtitle': 'Your AI assistant to study 10x faster',
        'logout': '🚪 Logout',
        'back': '← Back',
        'plan': 'Plan',
        'upgrade': '⭐ Go Pro',
        'modify_plan': '✏️ Change Plan',
        'choose_plan': 'Choose a plan',
        'current_plan': 'Current plan',
        'monthly': '/month',
        
        # Login
        'login_title': '🔐 Login',
        'register_title': '📝 Register',
        'email': 'Email',
        'password': 'Password',
        'confirm_password': 'Confirm',
        'full_name': 'Full name (optional)',
        'login_btn': '🔓 Login',
        'register_btn': '🚀 Register',
        'welcome_back': '✅ Welcome back!',
        'welcome': '✅ Welcome!',
        
        # Features
        'qa_title': '💬 Q&A',
        'qa_desc': 'Ask questions about your courses',
        'flashcards_title': '🎴 Flashcards',
        'flashcards_desc': 'Auto-generated',
        'quiz_title': '📝 Quiz',
        'quiz_desc': 'Test your knowledge',
        'summary_title': '📋 Summary',
        'summary_desc': 'Instant synthesis',
        
        # Dashboard
        'hello': 'Hi',
        'ready_to_learn': 'Ready to learn something new?',
        'my_courses': '📚 My Courses',
        'no_courses': '📭 No courses. Create your first course to get started!',
        'new_course': '➕ New Course',
        'study': '💬 Study',
        'upload': '📤 Upload',
        'courses': 'Courses',
        'questions': 'Questions',
        'this_month': 'This month',
        
        # Course
        'create_course': '➕ Create New Course',
        'course_name': 'Course name *',
        'course_desc': 'Description',
        'create_btn': '✅ Create',
        'cancel_btn': '❌ Cancel',
        'choose_study_mode': 'Choose your study mode',
        
        # Upload
        'upload_title': '📤 Upload Files',
        'supported_formats': 'Supported formats: PDF, DOCX, PPTX, Images, Audio, Video',
        'upload_btn': '🚀 Upload & Index',
        'indexing': '⏳ Uploading and indexing...',
        'indexing_done': '✅ Indexing complete!',
        
        # Q&A
        'ask_question': '💬 Ask your question',
        'question_placeholder': 'Ex: What is the derivative formula?',
        'search': '🔍 Search',
        'answer_found': '✅ Answer found!',
        'exact_answer': '✅ Exact Answer from Course',
        'explanation': '💡 Pedagogical Explanation',
        'show_explanation': '🔽 Show detailed explanation',
        'hide_explanation': '🔼 Hide explanation',
        'sources': '📖 Sources',
        'new_question': '🧹 New question',
        'confidence': 'Confidence',
        
        # Flashcards
        'flashcards_intro': 'Generate flashcards automatically from your course!',
        'num_flashcards': 'Number of flashcards',
        'generate_flashcards': '🎴 Generate Flashcards',
        'generating': '🤖 Generating...',
        'card': 'Card',
        'question': 'Question',
        'answer': 'Answer',
        'previous': '⬅️ Previous',
        'reveal': '👁️ Reveal',
        'hide': '🙈 Hide',
        'next': '➡️ Next',
        'reset': '🔄 Reset',
        
        # Quiz
        'quiz_intro': 'Generate a quiz to test your knowledge!',
        'num_questions': 'Number of questions',
        'generate_quiz': '📝 Generate Quiz',
        'submit': '✅ Submit',
        'new_quiz': '🔄 New Quiz',
        'excellent': '🎉 Excellent!',
        'good': '👍 Good!',
        'keep_studying': '📚 Keep studying!',
        
        # Summary
        'summary_intro': 'Generate an automatic summary of your course!',
        'summary_type': 'Summary type',
        'short': 'Short (1 page)',
        'medium': 'Medium (2-3 pages)',
        'long': 'Detailed (5+ pages)',
        'generate_summary': '📋 Generate Summary',
        'download': '📥 Download',
        'download_txt': '📄 Download as TXT',
        'new_summary': '🔄 New Summary',
        
        # Errors
        'email_required': 'Email and password required',
        'passwords_mismatch': 'Passwords do not match',
        'api_unavailable': 'API unavailable',
        'no_content': 'No content found',
        'write_question': 'Write a question first!'
    }
}

def t(key: str) -> str:
    """Récupère la traduction pour la clé donnée"""
    lang_radio = st.session_state.get('lang_radio', 'FR')
    lang = 'fr' if lang_radio == 'FR' else 'en'
    return TRANSLATIONS.get(lang, TRANSLATIONS['fr']).get(key, key)

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ============================================
# API HELPERS
# ============================================

def api_request(method, endpoint, data=None, files=None):
    """Requête API avec gestion token"""
    headers = {}
    
    if st.session_state.token:
        headers['Authorization'] = f"Bearer {st.session_state.token}"
    
    url = f"{API_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=60)
        elif method == "POST":
            if files:
                response = requests.post(url, headers=headers, files=files, timeout=300)
            else:
                headers['Content-Type'] = 'application/json'
                response = requests.post(url, headers=headers, json=data, timeout=120)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=30)
        
        if response.status_code in [200, 201]:
            return response.json()
        else:
            st.error(f"Erreur API: {response.status_code}")
            return None
    
    except requests.exceptions.Timeout:
        st.error("⏱️ Timeout - L'opération prend trop de temps")
        return None
    except Exception as e:
        st.error(f"Erreur connexion: {e}")
        return None


def api_request_pdf(endpoint, data, filename):
    """
    Requête API pour télécharger un PDF
    
    Args:
        endpoint: Endpoint API (ex: /api/export-flashcards-pdf)
        data: Données JSON à envoyer
        filename: Nom du fichier PDF
    
    Returns:
        True si succès, False sinon
    """
    if not st.session_state.token:
        st.error("Non authentifié")
        return False
    
    headers = {
        'Authorization': f"Bearer {st.session_state.token}",
        'Content-Type': 'application/json'
    }
    
    url = f"{API_URL}{endpoint}"
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=120)
        
        if response.status_code == 200:
            # Téléchargement réussi - proposer download
            st.download_button(
                label="📥 Télécharger PDF",
                data=response.content,
                file_name=filename,
                mime="application/pdf",
                use_container_width=True
            )
            return True
        else:
            st.error(f"Erreur PDF: {response.status_code}")
            if response.text:
                st.error(f"Détail: {response.text[:200]}")
            return False
    
    except requests.exceptions.Timeout:
        st.error("⏱️ Timeout - Génération PDF trop longue")
        return False
    except Exception as e:
        st.error(f"Erreur génération PDF: {e}")
        return False


def get_image(course_id, filename):
    """Récupère une image du cours"""
    if not st.session_state.token:
        return None
    
    try:
        url = f"{API_URL}/api/images/{course_id}/{filename}"
        headers = {'Authorization': f"Bearer {st.session_state.token}"}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            from PIL import Image
            from io import BytesIO
            return Image.open(BytesIO(response.content))
        return None
    except:
        return None


def page_landing():
    """Landing page marketing avant login"""
    
    # Sélecteur de langue en haut à droite
    col_space, col_lang = st.columns([5, 1])
    with col_lang:
        st.radio(
            "🌐",
            ["FR", "EN"],
            key="lang_radio",
            horizontal=True,
            label_visibility="collapsed"
        )
    
    # ============================================
    # HERO SECTION
    # ============================================
    
    # Logo centré
    logo_path = Path("assets/studygenie_logo.png")
    if logo_path.exists():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(str(logo_path), width=350)
    
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0 3rem 0;">
        <h1 style="font-size: 3rem; margin-bottom: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
            Étudie 10x Plus Vite avec l'IA
        </h1>
        <p style="font-size: 1.3rem; color: var(--text-secondary); max-width: 700px; margin: 0 auto 2rem auto;">
            StudyGenie transforme tes cours en flashcards, quiz et résumés intelligents. 
            Pose des questions, obtiens des réponses avec sources précises.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # CTA Principal
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Commencer Gratuitement", use_container_width=True, type="primary"):
            st.session_state.show_landing = False
            st.rerun()
        
        st.markdown("""
        <p style="text-align: center; color: var(--text-muted); font-size: 0.9rem; margin-top: 0.5rem;">
            ✨ Aucune carte bancaire requise • 50 questions offertes
        </p>
        """, unsafe_allow_html=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # ============================================
    # FEATURES SECTION
    # ============================================
    
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0 1rem 0;">
        <h2 style="font-size: 2rem;">🎯 Tout ce dont tu as besoin</h2>
        <p style="color: var(--text-secondary);">4 outils puissants alimentés par l'IA Claude</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="glass-card" style="padding: 2rem; height: 100%;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">💬</div>
            <h3 style="color: var(--text-primary); margin-bottom: 0.5rem;">Q&A Intelligent</h3>
            <p style="color: var(--text-secondary);">
                Pose n'importe quelle question sur tes cours. StudyGenie analyse tes documents 
                et te donne des réponses précises avec les sources et numéros de pages.
            </p>
            <ul style="color: var(--text-muted); font-size: 0.9rem; margin-top: 1rem;">
                <li>✓ Réponses avec citations exactes</li>
                <li>✓ Numéros de pages référencés</li>
                <li>✓ Score de confiance</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="glass-card" style="padding: 2rem; height: 100%; margin-top: 1rem;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">📝</div>
            <h3 style="color: var(--text-primary); margin-bottom: 0.5rem;">Quiz Personnalisés</h3>
            <p style="color: var(--text-secondary);">
                Génère automatiquement des quiz QCM adaptés à tes cours. 
                Teste tes connaissances avec correction instantanée.
            </p>
            <ul style="color: var(--text-muted); font-size: 0.9rem; margin-top: 1rem;">
                <li>✓ 3 à 10 questions par quiz</li>
                <li>✓ 4 choix de réponse</li>
                <li>✓ Explications détaillées</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="glass-card" style="padding: 2rem; height: 100%;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">🎴</div>
            <h3 style="color: var(--text-primary); margin-bottom: 0.5rem;">Flashcards Automatiques</h3>
            <p style="color: var(--text-secondary);">
                Crée des flashcards intelligentes en un clic. Révise efficacement 
                avec la méthode de répétition espacée.
            </p>
            <ul style="color: var(--text-muted); font-size: 0.9rem; margin-top: 1rem;">
                <li>✓ 3 à 20 cartes générées</li>
                <li>✓ Questions/réponses pertinentes</li>
                <li>✓ Navigation intuitive</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="glass-card" style="padding: 2rem; height: 100%; margin-top: 1rem;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">📋</div>
            <h3 style="color: var(--text-primary); margin-bottom: 0.5rem;">Résumés Structurés</h3>
            <p style="color: var(--text-secondary);">
                Obtiens des résumés clairs et bien organisés. 
                Choisir la longueur : court, moyen ou détaillé.
            </p>
            <ul style="color: var(--text-muted); font-size: 0.9rem; margin-top: 1rem;">
                <li>✓ 3 niveaux de détail</li>
                <li>✓ Format Markdown structuré</li>
                <li>✓ Points clés mis en avant</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # ============================================
    # STATS SECTION
    # ============================================
    
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0;">
        <h2 style="font-size: 2rem; margin-bottom: 2rem;">📊 Pourquoi StudyGenie ?</h2>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div style="text-align: center; padding: 1.5rem;">
            <div style="font-size: 3rem; color: #667eea; margin-bottom: 0.5rem;">⚡</div>
            <h3 style="font-size: 2.5rem; color: var(--text-primary); margin: 0;">10x</h3>
            <p style="color: var(--text-secondary);">Plus rapide qu'étudier seul</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="text-align: center; padding: 1.5rem;">
            <div style="font-size: 3rem; color: #667eea; margin-bottom: 0.5rem;">🎯</div>
            <h3 style="font-size: 2.5rem; color: var(--text-primary); margin: 0;">95%</h3>
            <p style="color: var(--text-secondary);">Précision des réponses</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style="text-align: center; padding: 1.5rem;">
            <div style="font-size: 3rem; color: #667eea; margin-bottom: 0.5rem;">🚀</div>
            <h3 style="font-size: 2.5rem; color: var(--text-primary); margin: 0;">5 min</h3>
            <p style="color: var(--text-secondary);">Pour créer un quiz complet</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # ============================================
    # PRICING SECTION
    # ============================================
    
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0 1rem 0;">
        <h2 style="font-size: 2rem;">💰 Plans & Tarifs</h2>
        <p style="color: var(--text-secondary);">Choisis le plan qui te convient</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="glass-card" style="padding: 1.5rem; text-align: center; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);">
            <h3 style="color: #ffffff; font-size: 1.3rem; font-weight: 600;">Free</h3>
            <div style="font-size: 2rem; margin: 1rem 0; font-weight: bold; color: #ffffff;">$0</div>
            <p style="color: #a0aec0; font-size: 0.85rem;">Pour essayer</p>
            <hr style="margin: 1rem 0; opacity: 0.3; border-color: #ffffff;">
            <ul style="text-align: left; color: #e2e8f0; font-size: 0.85rem; padding-left: 1.2rem; list-style: none;">
                <li style="margin: 0.5rem 0;">✓ 1 cours</li>
                <li style="margin: 0.5rem 0;">✓ 20 questions/mois</li>
                <li style="margin: 0.5rem 0;">✓ Pas d'audio</li>
                <li style="margin: 0.5rem 0;">✓ Export basique</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="glass-card" style="padding: 1.5rem; text-align: center; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);">
            <h3 style="color: #ffffff; font-size: 1.3rem; font-weight: 600;">Basic</h3>
            <div style="font-size: 2rem; margin: 1rem 0; font-weight: bold; color: #667eea;">$9.99</div>
            <p style="color: #a0aec0; font-size: 0.85rem;">par mois</p>
            <hr style="margin: 1rem 0; opacity: 0.3; border-color: #ffffff;">
            <ul style="text-align: left; color: #e2e8f0; font-size: 0.85rem; padding-left: 1.2rem; list-style: none;">
                <li style="margin: 0.5rem 0;">✓ 3 cours</li>
                <li style="margin: 0.5rem 0;">✓ 250 questions/mois</li>
                <li style="margin: 0.5rem 0;">✓ 30min audio/mois</li>
                <li style="margin: 0.5rem 0;">✓ Tout de Free +</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="glass-card" style="padding: 1.5rem; text-align: center; background: rgba(255,255,255,0.05); border: 2px solid #667eea;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 0.25rem 0.8rem; border-radius: 15px; display: inline-block; font-size: 0.7rem; margin-bottom: 0.5rem;">
                ⭐ POPULAIRE
            </div>
            <h3 style="color: #ffffff; font-size: 1.3rem; font-weight: 600;">Pro</h3>
            <div style="font-size: 2rem; margin: 1rem 0; font-weight: bold; color: #667eea;">$24.99</div>
            <p style="color: #a0aec0; font-size: 0.85rem;">par mois</p>
            <hr style="margin: 1rem 0; opacity: 0.3; border-color: #ffffff;">
            <ul style="text-align: left; color: #e2e8f0; font-size: 0.85rem; padding-left: 1.2rem; list-style: none;">
                <li style="margin: 0.5rem 0;">✓ 10 cours</li>
                <li style="margin: 0.5rem 0;">✓ 1000 questions/mois</li>
                <li style="margin: 0.5rem 0;">✓ 3h audio/mois</li>
                <li style="margin: 0.5rem 0;">✓ Support prioritaire</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="glass-card" style="padding: 1.5rem; text-align: center; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);">
            <h3 style="color: #ffffff; font-size: 1.3rem; font-weight: 600;">Premium</h3>
            <div style="font-size: 2rem; margin: 1rem 0; font-weight: bold; color: #ffffff;">$49.99</div>
            <p style="color: #a0aec0; font-size: 0.85rem;">par mois</p>
            <hr style="margin: 1rem 0; opacity: 0.3; border-color: #ffffff;">
            <ul style="text-align: left; color: #e2e8f0; font-size: 0.85rem; padding-left: 1.2rem; list-style: none;">
                <li style="margin: 0.5rem 0;">✓ 50 cours</li>
                <li style="margin: 0.5rem 0;">✓ 3000 questions/mois</li>
                <li style="margin: 0.5rem 0;">✓ 10h audio/mois</li>
                <li style="margin: 0.5rem 0;">✓ Support VIP 24/7</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # ============================================
    # CTA FINAL
    # ============================================
    
    st.markdown("""
    <div style="text-align: center; padding: 3rem 0 2rem 0; background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%); border-radius: 20px; margin: 2rem 0;">
        <h2 style="font-size: 2rem; margin-bottom: 1rem;">Prêt à transformer tes études ?</h2>
        <p style="color: var(--text-secondary); font-size: 1.1rem; margin-bottom: 2rem;">
            Rejoins des centaines d'étudiants qui réussissent mieux avec StudyGenie
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🎓 Créer mon Compte Gratuit", use_container_width=True, type="primary", key="cta_bottom"):
            st.session_state.show_landing = False
            st.rerun()
    
    # ============================================
    # FOOTER
    # ============================================
    
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0 1rem 0; margin-top: 3rem; border-top: 1px solid rgba(255,255,255,0.1);">
        <p style="color: var(--text-muted); font-size: 0.85rem;">
            © 2025 StudyGenie • Apprends plus vite, retiens mieux
		Étudiant, prof ou pro : StudyGenie s'adapte à toi
        </p>
        <p style="color: var(--text-muted); font-size: 0.8rem; margin-top: 0.5rem;">
            <a href="#" style="color: var(--text-muted); text-decoration: none;">Conditions</a> • 
            <a href="#" style="color: var(--text-muted); text-decoration: none;">Confidentialité</a> • 
            <a href="#" style="color: var(--text-muted); text-decoration: none;">Contact</a>
        </p>
    </div>
    """, unsafe_allow_html=True)

# ============================================
# PAGE: LOGIN
# ============================================

def page_login():
    """Page de connexion/inscription avec design moderne"""
    
    # Sélecteur de langue en haut à droite
    col_space, col_lang = st.columns([5, 1])
    with col_lang:
        st.radio(
            "🌐",
            ["FR", "EN"],
            key="lang_radio",
            horizontal=True,
            label_visibility="collapsed"
        )
    
    # Header centré avec logo
    logo_path = Path("assets/studygenie_logo.png")
    if logo_path.exists():
        col_left, col_center, col_right = st.columns([1, 2, 1])
        with col_center:
            st.image(str(logo_path), width=400)
            st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align: center; padding: 3rem 0;">
            <h1 style="font-size: 3.5rem; margin-bottom: 0.5rem;">{t('app_title')}</h1>
            <p style="font-size: 1.2rem; color: var(--text-secondary);">
                {t('app_subtitle')}
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Features highlights
    col1, col2, col3, col4 = st.columns(4)
    features = [
        ("💬", t('qa_title'), t('qa_desc')),
        ("🎴", t('flashcards_title'), t('flashcards_desc')),
        ("📝", t('quiz_title'), t('quiz_desc')),
        ("📋", t('summary_title'), t('summary_desc'))
    ]
    
    for col, (icon, title, desc) in zip([col1, col2, col3, col4], features):
        with col:
            st.markdown(f"""
            <div class="glass-card" style="text-align: center; padding: 1.5rem;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">{icon}</div>
                <div style="font-weight: 600; color: var(--text-primary);">{title}</div>
                <div style="font-size: 0.85rem; color: var(--text-muted);">{desc}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Forms
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"### {t('register_title')}")
        
        with st.form("register_form"):
            email_reg = st.text_input(t('email'), key="email_reg", placeholder="your@email.com")
            password_reg = st.text_input(t('password'), type="password", key="password_reg")
            password_confirm = st.text_input(t('confirm_password'), type="password")
            full_name = st.text_input(t('full_name'))
            
            submit_reg = st.form_submit_button(t('register_btn'), use_container_width=True)
            
            if submit_reg:
                if not email_reg or not password_reg:
                    st.error(t('email_required'))
                elif password_reg != password_confirm:
                    st.error(t('passwords_mismatch'))
                else:
                    with st.spinner("..."):
                        result = api_request("POST", "/api/register", {
                            "email": email_reg,
                            "password": password_reg,
                            "full_name": full_name or None
                        })
                        
                        if result:
                            st.session_state.token = result['access_token']
                            st.session_state.user = result['user']
                            st.success(t('welcome'))
                            st.rerun()
    
    with col2:
        st.markdown(f"### {t('login_title')}")
        
        with st.form("login_form"):
            email_login = st.text_input(t('email'), key="email_login", placeholder="your@email.com")
            password_login = st.text_input(t('password'), type="password", key="password_login")
            
            submit_login = st.form_submit_button(t('login_btn'), use_container_width=True)
            
            if submit_login:
                if not email_login or not password_login:
                    st.error(t('email_required'))
                else:
                    with st.spinner("..."):
                        result = api_request("POST", "/api/login", {
                            "email": email_login,
                            "password": password_login
                        })
                        
                        if result:
                            st.session_state.token = result['access_token']
                            st.session_state.user = result['user']
                            st.success(t('welcome_back'))
                            st.rerun()


# ============================================
# PAGE: PRICING / UPGRADE
# ============================================

def show_pricing_page():
    """Page de tarification pour upgrade"""
    
    st.markdown(f"## {t('choose_plan')}")
    
    # Bouton retour
    if st.button(t('back')):
        st.session_state.show_pricing = False
        st.rerun()
    
    st.markdown("---")
    
    # Plans
    plans = [
        {
            'name': 'Basic',
            'price': '9.99',
            'features_fr': ['5 cours', '500 pages/cours', '500 questions/mois', 'Claude Sonnet 4'],
            'features_en': ['5 courses', '500 pages/course', '500 questions/month', 'Claude Sonnet 4'],
            'plan_id': 'basic'
        },
        {
            'name': 'Pro',
            'price': '19.99',
            'features_fr': ['20 cours', '2000 pages/cours', '2000 questions/mois', 'Claude Sonnet 4', 'Support prioritaire'],
            'features_en': ['20 courses', '2000 pages/course', '2000 questions/month', 'Claude Sonnet 4', 'Priority support'],
            'plan_id': 'pro'
        },
        {
            'name': 'Premium',
            'price': '49.99',
            'features_fr': ['Cours illimités', 'Pages illimitées', 'Questions illimitées', 'Claude Sonnet 4', 'Support VIP'],
            'features_en': ['Unlimited courses', 'Unlimited pages', 'Unlimited questions', 'Claude Sonnet 4', 'VIP support'],
            'plan_id': 'premium'
        }
    ]
    
    cols = st.columns(3)
    
    lang = 'fr' if st.session_state.get('lang_radio', 'FR') == 'FR' else 'en'
    
    for i, plan in enumerate(plans):
        with cols[i]:
            st.markdown(f"""
            <div style="background: rgba(99, 102, 241, 0.1); border: 2px solid rgba(99, 102, 241, 0.3); 
                        border-radius: 16px; padding: 1.5rem; text-align: center; height: 100%;">
                <h3 style="color: #818cf8;">{plan['name']}</h3>
                <p style="font-size: 2rem; font-weight: bold; margin: 1rem 0;">
                    ${plan['price']}<span style="font-size: 1rem; color: #888;">{t('monthly')}</span>
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            features = plan['features_fr'] if lang == 'fr' else plan['features_en']
            for feature in features:
                st.markdown(f"✅ {feature}")
            
            st.markdown("")
            
            if st.button(f"Choisir {plan['name']}" if lang == 'fr' else f"Choose {plan['name']}", 
                        key=f"choose_{plan['plan_id']}", 
                        use_container_width=True,
                        type="primary" if plan['plan_id'] == 'pro' else "secondary"):
                # Appeler l'API pour créer une session checkout
                checkout_url = create_checkout_session(plan['plan_id'])
                if checkout_url:
                    st.markdown(f'<meta http-equiv="refresh" content="0;url={checkout_url}">', unsafe_allow_html=True)
                    st.success(f"Redirection vers Stripe... / Redirecting to Stripe...")


def create_checkout_session(plan: str) -> str:
    """Crée une session checkout Stripe"""
    try:
        response = api_request("POST", "/api/create-checkout-session", {
            "plan": plan,
            "success_url": "http://localhost:8501?success=true",
            "cancel_url": "http://localhost:8501?canceled=true"
        })
        
        if response and response.get('checkout_url'):
            return response['checkout_url']
        else:
            st.error("Erreur création session / Error creating session")
            return None
    except Exception as e:
        st.error(f"Erreur: {e}")
        return None


# ============================================
# PAGE: DASHBOARD
# ============================================

def page_dashboard():
    """Dashboard principal avec stats et cours"""
    
    # Afficher la page de pricing si demandé (AVANT tout le reste)
    if st.session_state.get('show_pricing'):
        show_pricing_page()
        return
    
    # Sélecteur de langue en haut à droite
    col_space, col_lang = st.columns([6, 1])
    with col_lang:
        st.radio(
            "🌐",
            ["FR", "EN"],
            key="lang_radio",
            horizontal=True,
            label_visibility="collapsed"
        )
    
    user = st.session_state.user
    
    # Logo dans le dashboard
    logo_path = Path("assets/studygenie_logo.png")
    if logo_path.exists():
        col_logo, col_spacer = st.columns([1, 3])
        with col_logo:
            st.image(str(logo_path), width=200)
    
    # Header
    st.markdown(f"""
    <div style="margin-bottom: 2rem;">
        <h1>👋 {t('hello')} {user.get('full_name') or user.get('email', '').split('@')[0]} !</h1>
        <p style="color: var(--text-secondary);">{t('ready_to_learn')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Stats
    stats = api_request("GET", "/api/stats")
    
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(f"📚 {t('courses')}", stats.get('total_courses', 0))
        with col2:
            st.metric(f"❓ {t('questions')}", stats.get('total_questions', 0))
        with col3:
            st.metric(f"📅 {t('this_month')}", stats.get('questions_this_month', 0))
        with col4:
            plan = stats.get('subscription_type', 'free').upper()
            st.metric(f"⭐ {t('plan')}", plan)
        
        current_plan = stats.get('subscription_type', 'free')
        
        # Affichage selon le plan
        if current_plan == 'free':
            # Plan Free - Afficher limite et bouton "Ajouter un plan"
            st.markdown("---")
            questions_used = stats.get('questions_this_month', 0)
            questions_limit = 50
            progress = min(questions_used / questions_limit, 1.0)
            
            if PREMIUM_UI_LOADED:
                render_progress_bar(progress, f"{t('questions')}: {questions_used}/{questions_limit}")
            else:
                st.progress(progress)
                st.caption(f"{t('questions')}: {questions_used}/{questions_limit}")
            
            if progress >= 0.8:
                st.warning("⚠️ Limite proche / Limit approaching!")
            
            # Bouton Ajouter un plan (pour Free)
            if st.button(t('upgrade'), type="primary", use_container_width=True):
                st.session_state.show_pricing = True
                st.rerun()
        else:
            # Plan payant (Basic/Pro/Premium) - Afficher bouton "Modifier le plan"
            st.markdown("---")
            col_plan1, col_plan2 = st.columns([3, 1])
            
            with col_plan1:
                plan_info = {
                    'basic': {'courses': 5, 'pages': 500, 'questions': 500},
                    'pro': {'courses': 20, 'pages': 2000, 'questions': 2000},
                    'premium': {'courses': '∞', 'pages': '∞', 'questions': '∞'}
                }
                info = plan_info.get(current_plan, {})
                st.success(f"✅ Plan {current_plan.upper()} actif | {info.get('courses', '?')} cours | {info.get('questions', '?')} questions/mois")
            
            with col_plan2:
                if st.button(t('modify_plan'), use_container_width=True):
                    st.session_state.show_pricing = True
                    st.rerun()
    
    st.markdown("---")
    
    # Liste des cours
    st.markdown(f"### {t('my_courses')}")
    
    courses = api_request("GET", "/api/courses")
    
    if courses and len(courses) > 0:
        for course in courses:
            with st.container():
                col1, col2, col3 = st.columns([4, 2, 1])
                
                with col1:
                    status_icon = "✅" if course.get('indexed') else "⏳"
                    st.markdown(f"**{status_icon} {course['name']}**")
                    
                    # NOUVEAU : Afficher fichiers avec détails
                    files_count = course.get('files_count', 0)
                    if files_count > 0:
                        # Récupérer détails des fichiers
                        course_details = api_request("GET", f"/api/courses/{course['id']}")
                        if course_details and 'files' in course_details:
                            files = course_details['files']
                            
                            # Compter types de fichiers
                            pdf_count = sum(1 for f in files if f.get('file_type') == 'pdf')
                            audio_count = sum(1 for f in files if f.get('file_type') == 'audio')
                            video_count = sum(1 for f in files if f.get('file_type') == 'video')
                            other_count = files_count - pdf_count - audio_count - video_count
                            
                            # Afficher résumé
                            parts = []
                            if pdf_count: parts.append(f"📄 {pdf_count} PDF")
                            if audio_count: parts.append(f"🎵 {audio_count} audio")
                            if video_count: parts.append(f"🎬 {video_count} vidéo")
                            if other_count: parts.append(f"📁 {other_count} autre(s)")
                            
                            files_summary = " • ".join(parts) if parts else f"{files_count} fichier(s)"
                            st.caption(f"{files_summary} • {course.get('chunks_count', 0)} chunks")
                    else:
                        st.caption(f"{course.get('pages_count', 0)} pages • {course.get('chunks_count', 0)} chunks")
                
                with col2:
                    if course.get('indexed'):
                        if st.button(t('study'), key=f"study_{course['id']}", use_container_width=True):
                            st.session_state.current_course = course
                            st.session_state.current_tab = 'qa'
                            st.session_state.last_result = None
                            st.rerun()
                    else:
                        if st.button(t('upload'), key=f"upload_{course['id']}", use_container_width=True):
                            st.session_state.current_course = course
                            st.rerun()
                
                with col3:
                    if st.button("🗑️", key=f"del_{course['id']}"):
                        if api_request("DELETE", f"/api/courses/{course['id']}"):
                            st.rerun()
                
                st.markdown("---")
    else:
        st.info(t('no_courses'))
    
    # Bouton créer cours
    if st.button(t('new_course'), type="primary", use_container_width=False):
        st.session_state.show_create_course = True
        st.rerun()


# ============================================
# PAGE: CREATE COURSE
# ============================================

def page_create_course():
    """Création de cours"""
    
    st.markdown("### ➕ Créer un Nouveau Cours")
    
    with st.form("create_course"):
        name = st.text_input("Nom du cours *", placeholder="Ex: Thermodynamique GCH2530")
        description = st.text_area("Description", placeholder="Notes du prof Tremblay...")
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("✅ Créer", use_container_width=True, type="primary")
        with col2:
            cancel = st.form_submit_button("❌ Annuler", use_container_width=True)
        
        if submit and name:
            result = api_request("POST", "/api/courses", {
                "name": name,
                "description": description
            })
            if result:
                st.session_state.current_course = result
                st.session_state.show_create_course = False
                st.success("✅ Cours créé !")
                st.rerun()
        
        if cancel:
            st.session_state.show_create_course = False
            st.rerun()


# ============================================
# PAGE: UPLOAD FILES
# ============================================

def page_upload_files():
    """Upload et indexation de fichiers"""
    
    course = st.session_state.current_course
    
    st.markdown(f"### 📤 Upload - {course['name']}")
    
    # ============================================
    # ONGLETS : FICHIERS ET MICRO
    # ============================================
    
    tab1, tab2 = st.tabs(["📁 Importer des fichiers", "🎤 Enregistrer audio"])
    
    # ============================================
    # TAB 1 : UPLOAD FICHIERS
    # ============================================
    
    with tab1:
        st.info("""
        **Formats supportés:** PDF, DOCX, PPTX, Images (JPG/PNG), Audio (MP3/WAV), Vidéo (MP4)
        """)
        
        uploaded_files = st.file_uploader(
            "Glisse tes fichiers ici",
            accept_multiple_files=True,
            type=['pdf', 'jpg', 'jpeg', 'png', 'pptx', 'docx', 'mp4', 'mp3', 'wav']
        )
        
        if uploaded_files:
            st.write(f"**{len(uploaded_files)} fichier(s):**")
            for f in uploaded_files:
                st.caption(f"• {f.name}")
            
            if st.button("🚀 Upload & Indexer", type="primary", key="upload_files_btn"):
                with st.spinner("⏳ Upload et indexation en cours..."):
                    files_list = [('files', (f.name, f.getvalue(), f.type or 'application/octet-stream')) for f in uploaded_files]
                    
                    url = f"{API_URL}/api/courses/{course['id']}/upload"
                    headers = {'Authorization': f"Bearer {st.session_state.token}"}
                    
                    try:
                        response = requests.post(url, headers=headers, files=files_list, timeout=300)
                        if response.status_code in [200, 201]:
                            st.success("✅ Indexation terminée !")
                            st.balloons()
                            import time
                            time.sleep(2)
                            st.session_state.current_course = None
                            st.rerun()
                        else:
                            st.error(f"Erreur: {response.text}")
                    except Exception as e:
                        st.error(f"Erreur: {e}")
    
    # ============================================
    # TAB 2 : ENREGISTREMENT AUDIO
    # ============================================
    
    with tab2:
        st.markdown("### 🎤 Enregistrer un cours vocal")
        
        st.info("""
        **Utilisation :**
        1. Cliquez sur le micro ci-dessous
        2. Autorisez l'accès au microphone (si demandé)
        3. Parlez clairement et articulez bien
        4. Cliquez sur "Stop" quand vous avez terminé
        5. Cliquez sur "Transcrire et Indexer"
        
        **💡 Idéal pour :**
        - Notes vocales après lecture
        - Résumé oral d'un chapitre
        - Explications personnelles
        - Dictée de cours
        """)
        
        # Composant d'enregistrement Streamlit natif
        audio_bytes = st.audio_input("Cliquez pour enregistrer")
        
        if audio_bytes:
            st.success("✅ Enregistrement capturé !")
            
            # Afficher le lecteur audio
            st.audio(audio_bytes, format='audio/wav')
            
            st.info("📊 Prêt à être transcrit et indexé")
            
            # Bouton pour transcrire
            if st.button("🚀 Transcrire et Indexer", type="primary", key="transcribe_btn"):
                with st.spinner("🎤 Transcription en cours... (peut prendre 1-2 minutes)"):
                    try:
                        import tempfile
                        import datetime
                        
                        # Créer fichier temporaire
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        temp_file = Path(tempfile.gettempdir()) / f"recording_{timestamp}.wav"
                        
                        # Sauvegarder l'audio
                        with open(temp_file, 'wb') as f:
                            f.write(audio_bytes.getvalue())
                        
                        # Préparer pour upload
                        with open(temp_file, 'rb') as f:
                            files_list = [('files', (f"recording_{timestamp}.wav", f, 'audio/wav'))]
                            
                            url = f"{API_URL}/api/courses/{course['id']}/upload"
                            headers = {'Authorization': f"Bearer {st.session_state.token}"}
                            
                            response = requests.post(url, headers=headers, files=files_list, timeout=300)
                        
                        # Nettoyer fichier temporaire
                        try:
                            temp_file.unlink()
                        except:
                            pass
                        
                        if response.status_code in [200, 201]:
                            result = response.json()
                            st.success("✅ Enregistrement transcrit et indexé avec succès !")
                            st.info(f"📊 {result.get('chunks_indexed', 0)} chunks indexés")
                            st.balloons()
                            
                            import time
                            time.sleep(2)
                            st.session_state.current_course = None
                            st.rerun()
                        else:
                            st.error(f"❌ Erreur lors du traitement: {response.text}")
                    
                    except Exception as e:
                        st.error(f"❌ Erreur: {e}")
                        import traceback
                        st.code(traceback.format_exc())
        
        else:
            st.warning("👆 Cliquez sur le micro ci-dessus pour commencer l'enregistrement")
    
    # ============================================
    # BOUTON RETOUR
    # ============================================
    
    st.markdown("---")
    if st.button("← Retour", key="back_btn"):
        st.session_state.current_course = None
        st.rerun()


# ============================================
# PAGE: STUDY (Q&A + Flashcards + Quiz + Summary)
# ============================================

def page_study():
    """Page d'étude principale avec onglets"""
    
    course = st.session_state.current_course
    
    # Sélecteur de langue en haut à droite
    col_space, col_lang = st.columns([6, 1])
    with col_lang:
        st.radio(
            "🌐",
            ["FR", "EN"],
            key="lang_radio",
            horizontal=True,
            label_visibility="collapsed"
        )
    
    # Header
    if PREMIUM_UI_LOADED:
        render_course_header(course['name'], t('choose_study_mode'))
    else:
        st.title(f"📚 {course['name']}")
    
    # Onglets de fonctionnalités
    col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1, 1, 1, 1])
    
    tabs = [
        ('qa', t('qa_title'), col1),
        ('flashcards', t('flashcards_title'), col2),
        ('quiz', t('quiz_title'), col3),
        ('summary', t('summary_title'), col4),
        ('files', '📁 Fichiers', col5)  # NOUVEAU
    ]
    
    for tab_id, tab_label, col in tabs:
        with col:
            btn_type = "primary" if st.session_state.current_tab == tab_id else "secondary"
            if st.button(tab_label, key=f"tab_{tab_id}", use_container_width=True, type=btn_type):
                st.session_state.current_tab = tab_id
                st.rerun()
    
    with col6:
        if st.button(t('back'), use_container_width=True):
            st.session_state.current_course = None
            st.session_state.last_result = None
            st.rerun()
    
    st.markdown("---")
    
    # Contenu selon l'onglet
    if st.session_state.current_tab == 'qa':
        render_qa_tab(course)
    elif st.session_state.current_tab == 'flashcards':
        render_flashcards_tab(course)
    elif st.session_state.current_tab == 'quiz':
        render_quiz_tab(course)
    elif st.session_state.current_tab == 'summary':
        render_summary_tab(course)
    elif st.session_state.current_tab == 'files':
        render_files_tab(course)  # NOUVEAU


# ============================================
# TAB: Q&A
# ============================================

def render_qa_tab(course):
    """Onglet Questions/Réponses"""
    
    st.markdown(f"### {t('ask_question')}")
    
    question = st.text_area(
        "Question",
        placeholder=t('question_placeholder'),
        height=100,
        label_visibility="collapsed"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        search = st.button(t('search'), type="primary", use_container_width=True)
    
    # Recherche
    if search and question:
        with st.spinner("🔍 Recherche en cours..."):
            lang = 'fr' if st.session_state.get('lang_radio', 'FR') == 'FR' else 'en'
            result = api_request("POST", "/api/ask", {
                "course_id": course['id'],
                "question": question,
                "language": lang
            })
            
            if result:
                st.session_state.last_result = result
                st.session_state.last_question = question
    
    elif search and not question:
        st.warning(t('write_question'))
    
    # Affichage résultat
    if st.session_state.last_result:
        result = st.session_state.last_result
        
        st.success(t('answer_found'))
        
        # Réponse - ✅ CORRECTION : Utiliser 'answer' au lieu de 'strict_answer'
        answer_text = result.get('answer', result.get('answer', result.get('strict_answer','')))
        
        if PREMIUM_UI_LOADED:
            render_response_box(answer_text, title=t('exact_answer'))
        else:
            st.markdown(f"### {t('exact_answer')}")
            st.markdown(answer_text)
        
        # Explication
        if result.get('explanation'):
            if PREMIUM_UI_LOADED:
                render_explanation_box(
                    result['explanation'],
                    show_button=True,
                    question=st.session_state.last_question,
                    course_id=course['id'],
                    title=t('explanation'),
                    btn_hide=t('hide_explanation'),
                    btn_show=t('show_explanation')
                )
            else:
                if 'show_explanation' not in st.session_state:
                    st.session_state.show_explanation = False
                
                if st.session_state.show_explanation:
                    if st.button(t('hide_explanation')):
                        st.session_state.show_explanation = False
                        st.rerun()
                    st.info(result['explanation'])
                else:
                    if st.button(t('show_explanation')):
                        st.session_state.show_explanation = True
                        st.rerun()
        
        # Sources
        if result.get('sources'):
            if PREMIUM_UI_LOADED:
                render_sources_section(result['sources'], title=t('sources'))
            else:
                with st.expander(t('sources')):
                    for i, src in enumerate(result['sources'], 1):
                        # Afficher source texte
                        st.write(f"**Source {i}** - Page {src.get('page', 'N/A')}")
                        st.caption(src.get('text', '')[:200])
                        
                        # NOUVEAU : Vérifier si c'est un fichier audio/vidéo
                        filename = src.get('filename', '')
                        if any(filename.endswith(ext) for ext in ['.wav', '.mp3', '.m4a', '.mp4', '.avi', '.mov']):
                            st.markdown("🎵 **Fichier audio original disponible**")
                            
                            # Récupérer file_id depuis le cours
                            try:
                                files_response = requests.get(
                                    f"{API_URL}/api/courses/{course['id']}",
                                    headers={'Authorization': f"Bearer {st.session_state.token}"}
                                )
                                if files_response.status_code == 200:
                                    course_data = files_response.json()
                                    for file_info in course_data.get('files', []):
                                        if file_info['filename'] == filename:
                                            # Afficher lecteur audio
                                            audio_url = f"{API_URL}/api/courses/{course['id']}/files/{file_info['id']}/download"
                                            st.audio(audio_url)
                                            
                                            # Bouton téléchargement
                                            st.markdown(f"[⬇️ Télécharger {filename}]({audio_url})")
                                            break
                            except Exception as e:
                                st.caption(f"⚠️ Lecture audio indisponible: {e}")
        
        # Metadata
        meta = result.get('metadata', {})
        st.caption(f"⏱️ {meta.get('response_time', 0):.1f}s • 📊 {t('confidence')}: {result.get('confidence', 0):.0%}")
        
        # Boutons téléchargement
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # TXT
            content_txt = f"Question: {st.session_state.last_question}\n\nRéponse: {result.get('answer', '')}"
            st.download_button(
                "📥 TXT",
                content_txt,
                file_name=f"qa_{course['name']}.txt",
                mime="text/plain",
                use_container_width=True
            )
        
        with col2:
            # Markdown
            content_md = f"# Question\n\n{st.session_state.last_question}\n\n# Réponse\n\n{result.get('answer', '')}"
            st.download_button(
                "📥 MD",
                content_md,
                file_name=f"qa_{course['name']}.md",
                mime="text/markdown",
                use_container_width=True
            )
        
        with col3:
            # PDF
            if st.button("📥 PDF", use_container_width=True, key="btn_pdf_qa"):
                with st.spinner("Génération PDF..."):
                    success = api_request_pdf(
                        "/api/export-qa-pdf",
                        {
                            "question": st.session_state.last_question,
                            "answer": result.get('answer', ''),
                            "sources": result.get('sources', []),
                            "course_id": course['id']
                        },
                        f"qa_{course['name']}.pdf"
                    )
                    if success:
                        st.success("✅ PDF généré !")
                    else:
                        st.error("❌ Erreur génération PDF")
        
        with col4:
            # Nouvelle question
            if st.button(t('new_question'), use_container_width=True):
                st.session_state.last_result = None
                st.session_state.last_question = ""
                st.session_state.show_explanation = False
                st.rerun()


# ============================================
# TAB: FLASHCARDS
# ============================================

def render_flashcards_tab(course):
    """Onglet Flashcards"""
    
    st.markdown(f"### 🎴 {t('flashcards_title')}")
    
    # Générer flashcards
    if not st.session_state.flashcards:
        st.info(t('flashcards_intro'))
        
        num_cards = st.slider(t('num_flashcards'), 5, 20, 10)
        
        if st.button(t('generate_flashcards'), type="primary"):
            with st.spinner(t('generating')):
                lang = 'fr' if st.session_state.get('lang_radio', 'FR') == 'FR' else 'en'
                result = api_request("POST", "/api/generate-flashcards", {
                    "course_id": course['id'],
                    "num_cards": num_cards,
                    "language": lang
                })
                
                if result and result.get('flashcards'):
                    st.session_state.flashcards = result['flashcards']
                    st.session_state.current_flashcard = 0
                    st.rerun()
                else:
                    # Fallback
                    st.session_state.flashcards = [
                        {"question": "Example question", "answer": "Example answer"},
                    ]
                    st.warning(t('api_unavailable'))
                    st.rerun()
    
    else:
        # Afficher flashcard actuelle
        cards = st.session_state.flashcards
        idx = st.session_state.current_flashcard
        card = cards[idx]
        
        # Progress
        st.caption(f"{t('card')} {idx + 1} / {len(cards)}")
        if PREMIUM_UI_LOADED:
            render_progress_bar((idx + 1) / len(cards))
        else:
            st.progress((idx + 1) / len(cards))
        
        # Flashcard
        st.markdown("---")
        
        if st.session_state.show_flashcard_answer:
            # Afficher réponse (rendue dans le cadre en une seule fois)
            answer_text = card.get('answer', '') or ''

            def _answer_to_html(text: str) -> str:
                parts = text.split("```")
                out_parts = []
                for i, part in enumerate(parts):
                    if i % 2 == 0:
                        p = html.escape(part).replace('\n', '<br>')
                        if p.strip():
                            out_parts.append(
                                "<div style='white-space: pre-wrap; overflow-wrap: anywhere;'>" + p + "</div>"
                            )
                    else:
                        code = html.escape(part)
                        out_parts.append(
                            "<pre style='background: rgba(0,0,0,0.35); padding: 12px; border-radius: 10px; "
                            "overflow-x:auto; white-space: pre;'><code>" + code + "</code></pre>"
                        )
                return "\n".join(out_parts)

            answer_html = _answer_to_html(answer_text)

            st.markdown(f"""
            <div style="background: rgba(16, 185, 129, 0.1); border: 2px solid rgba(16, 185, 129, 0.3);
                        border-radius: 16px; padding: 2rem; max-width: 100%;">
                <div style="font-size: 1rem; color: var(--text-muted); margin-bottom: 1rem; text-align: center;">
                    {t('answer')}
                </div>
                {answer_html}
            </div>
            """, unsafe_allow_html=True)
        else:
            # Afficher question
            st.markdown(f"""
            <div style="background: rgba(99, 102, 241, 0.1); border: 2px solid rgba(99, 102, 241, 0.3); 
                        border-radius: 16px; padding: 2rem; text-align: center; min-height: 150px;
                        display: flex; flex-direction: column; justify-content: center;">
                <div style="font-size: 1rem; color: var(--text-muted); margin-bottom: 1rem;">{t('question')}</div>
                <div style="font-size: 1.3rem; font-weight: 600; color: var(--text-primary);">{card['question']}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Contrôles
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            if st.button(t('previous'), disabled=(idx == 0), use_container_width=True):
                st.session_state.current_flashcard = idx - 1
                st.session_state.show_flashcard_answer = False
                st.rerun()
        
        with col2:
            btn_label = t('hide') if st.session_state.show_flashcard_answer else t('reveal')
            if st.button(btn_label, use_container_width=True):
                st.session_state.show_flashcard_answer = not st.session_state.show_flashcard_answer
                st.rerun()
        
        with col3:
            if st.button(t('next'), disabled=(idx >= len(cards) - 1), use_container_width=True):
                st.session_state.current_flashcard = idx + 1
                st.session_state.show_flashcard_answer = False
                st.rerun()
        
        with col4:
            # Bouton PDF
            if st.button("📥 PDF", use_container_width=True, key="btn_pdf_flash"):
                with st.spinner("Génération PDF..."):
                    success = api_request_pdf(
                        "/api/export-flashcards-pdf",
                        {
                            "flashcards": st.session_state.flashcards,
                            "course_id": course['id']
                        },
                        f"flashcards_{course['name']}.pdf"
                    )
                    if success:
                        st.success("✅ PDF généré !")
        
        with col5:
            if st.button(t('reset'), use_container_width=True):
                st.session_state.flashcards = []
                st.session_state.current_flashcard = 0
                st.session_state.show_flashcard_answer = False
                st.rerun()


# ============================================
# TAB: QUIZ
# ============================================

def render_quiz_tab(course):
    """Onglet Quiz"""
    
    st.markdown(f"### 📝 {t('quiz_title')}")
    
    if not st.session_state.quiz_questions:
        st.info(t('quiz_intro'))
        
        num_questions = st.slider(t('num_questions'), 3, 10, 5)
        
        if st.button(t('generate_quiz'), type="primary", key="btn_generate_quiz"):
            with st.spinner(t('generating')):
                lang = 'fr' if st.session_state.get('lang_radio', 'FR') == 'FR' else 'en'
                result = api_request("POST", "/api/generate-quiz", {
                    "course_id": course['id'],
                    "num_questions": num_questions,
                    "language": lang
                })
                
                if result and result.get('questions'):
                    st.session_state.quiz_questions = result['questions']
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_submitted = False
                    st.rerun()
                else:
                    # Fallback demo
                    st.session_state.quiz_questions = [
                        {
                            "question": "Quelle est l'unité de l'énergie ?",
                            "options": ["Watt", "Joule", "Newton", "Pascal"],
                            "correct": 1
                        },
                        {
                            "question": "E = mc² est la formule de ?",
                            "options": ["L'énergie cinétique", "L'énergie potentielle", "L'équivalence masse-énergie", "La force"],
                            "correct": 2
                        }
                    ]
                    st.warning("API non disponible, quiz de démonstration")
                    st.rerun()
    
    else:
        questions = st.session_state.quiz_questions
        
        # Afficher questions
        for i, q in enumerate(questions):
            st.markdown(f"**Question {i + 1}:** {q['question']}")
            
            # ✅ CORRECTION : Nettoyer les options
            options = q['options']
            cleaned_options = []
            for opt in options:
                opt_clean = opt.strip()
                # Retirer préfixes comme "A)", "B)", "A.A)", etc.
                import re
                opt_clean = re.sub(r'^[A-D]\.\s*[A-D]\)\s*', '', opt_clean)
                opt_clean = re.sub(r'^[A-D]\)\s*', '', opt_clean)
                cleaned_options.append(opt_clean)
            
            options = cleaned_options
            letters = ['A', 'B', 'C', 'D']
            
            selected = st.session_state.quiz_answers.get(i)
            
            # Créer les options
            for j, opt in enumerate(options):
                if st.session_state.quiz_submitted:
                    # Après soumission - afficher résultats
                    if j == q.get('correct', 0):
                        # Bonne réponse
                        st.markdown(f"""
                        <div style="padding: 0.75rem 1rem; margin: 0.25rem 0; border-radius: 8px; 
                                    background: rgba(16, 185, 129, 0.2); border: 2px solid #10B981;
                                    color: #10B981; font-weight: 500;">
                            ✅ {letters[j]}. {opt}
                        </div>
                        """, unsafe_allow_html=True)
                    elif selected == j:
                        # Mauvaise réponse sélectionnée
                        st.markdown(f"""
                        <div style="padding: 0.75rem 1rem; margin: 0.25rem 0; border-radius: 8px; 
                                    background: rgba(239, 68, 68, 0.2); border: 2px solid #EF4444;
                                    color: #EF4444; font-weight: 500;">
                            ❌ {letters[j]}. {opt}
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        # Autre option
                        st.markdown(f"""
                        <div style="padding: 0.75rem 1rem; margin: 0.25rem 0; border-radius: 8px; 
                                    background: rgba(30, 30, 50, 0.6); border: 1px solid rgba(255,255,255,0.1);
                                    color: #94A3B8;">
                            {letters[j]}. {opt}
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    # Avant soumission - boutons cliquables
                    is_selected = selected == j
                    btn_style = "primary" if is_selected else "secondary"
                    btn_icon = "🔘" if is_selected else "⚪"
                    
                    if st.button(
                        f"{btn_icon} {letters[j]}. {opt}", 
                        key=f"q{i}_opt{j}", 
                        use_container_width=True,
                        type=btn_style
                    ):
                        st.session_state.quiz_answers[i] = j
                        st.rerun()
            
            # Afficher feedback après soumission
            if st.session_state.quiz_submitted and q.get('feedback'):
                st.info(f"💡 {q['feedback']}")
            
            st.markdown("---")
        
        # Boutons
        col1, col2 = st.columns(2)
        
        with col1:
            if not st.session_state.quiz_submitted:
                if st.button(t('submit'), type="primary", use_container_width=True, key="btn_quiz_submit"):
                    st.session_state.quiz_submitted = True
                    st.rerun()
        
        with col2:
            # =========================
            # Export Quiz (PDF)
            # =========================
            st.markdown('---')
            if st.button('📥 PDF', use_container_width=True, key='btn_pdf_quiz'):
                with st.spinner('Génération PDF...'):
                    success = api_request_pdf(
                        '/api/export-quiz-pdf',
                        {'course_id': course['id'], 'questions': st.session_state.quiz_questions},
                        f"quiz_{course['name']}.pdf"
                    )
                if success:
                    st.success('✅ PDF généré !')

            if st.button(t('new_quiz'), use_container_width=True, key="btn_new_quiz"):
                st.session_state.quiz_questions = []
                st.session_state.quiz_answers = {}
                st.session_state.quiz_submitted = False
                st.rerun()
        
        # Score
        if st.session_state.quiz_submitted:
            correct = sum(1 for i, q in enumerate(questions) 
                         if st.session_state.quiz_answers.get(i) == q['correct'])
            total = len(questions)
            score = correct / total * 100
            
            if score >= 80:
                st.success(f"🎉 Excellent ! {correct}/{total} ({score:.0f}%)")
            elif score >= 60:
                st.warning(f"👍 Bien ! {correct}/{total} ({score:.0f}%)")
            else:
                st.error(f"{t('keep_studying')} {correct}/{total} ({score:.0f}%)")


# ============================================
# TAB: SUMMARY
# ============================================

def render_summary_tab(course):
    """Onglet Résumé"""
    
    st.markdown(f"### 📋 {t('summary_title')}")
    
    lang = 'fr' if st.session_state.get('lang_radio', 'FR') == 'FR' else 'en'
    
    if not st.session_state.summary:
        st.info(t('summary_intro'))
        
        # Options selon la langue
        options = [t('short'), t('medium'), t('long')]
        
        col1, col2 = st.columns(2)
        
        with col1:
            summary_type = st.selectbox(t('summary_type'), options)
        
        with col2:
            num_pages = st.slider("📄 Nombre de pages", min_value=1, max_value=50, value=10, 
                                 help="Nombre de pages du cours à inclure dans le résumé")
        
        if st.button(t('generate_summary'), type="primary"):
            with st.spinner(t('generating')):
                # Map vers short/medium/long
                length_map = {
                    t('short'): "short",
                    t('medium'): "medium", 
                    t('long'): "long"
                }
                
                result = api_request("POST", "/api/generate-summary", {
                    "course_id": course['id'],
                    "length": length_map.get(summary_type, "medium"),
                    "language": lang
                })
                
                if result and result.get('summary'):
                    st.session_state.summary = result['summary']
                    st.rerun()
                else:
                    # Fallback
                    st.session_state.summary = """
## Résumé du Cours

### Points Clés
- Point 1: Concept fondamental A
- Point 2: Concept fondamental B
- Point 3: Applications pratiques

### Formules Importantes
- Formule 1: E = mc²
- Formule 2: F = ma

### À Retenir
Ce cours couvre les bases de la matière avec des applications concrètes.

*Résumé de démonstration - API non disponible*
                    """
                    st.warning("API non disponible, résumé de démonstration")
                    st.rerun()
    
    else:
        # Afficher résumé avec visuels ASCII rendus correctement
        summary_text = st.session_state.summary
        
        # Parser et afficher avec visuels
        parts = summary_text.split('```')
        
        for i, part in enumerate(parts):
            if i % 2 == 0:
                # Texte normal (Markdown)
                if part.strip():
                    st.markdown(part)
            else:
                # Bloc de code (visuel ASCII)
                st.code(part, language='')
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # TXT
            st.download_button(
                label="📥 TXT",
                data=st.session_state.summary,
                file_name=f"resume_{course['name']}.txt",
                mime="text/plain",
                use_container_width=True
            )
        
        with col2:
            # Markdown
            st.download_button(
                label="📥 MD",
                data=st.session_state.summary,
                file_name=f"resume_{course['name']}.md",
                mime="text/markdown",
                use_container_width=True
            )
        
        with col3:
            # PDF
            if st.button("📥 PDF", use_container_width=True, key="btn_pdf_summary"):
                with st.spinner("Génération PDF..."):
                    success = api_request_pdf(
                        "/api/export-summary-pdf",
                        {
                            "summary": st.session_state.summary,
                            "course_id": course['id']
                        },
                        f"resume_{course['name']}.pdf"
                    )
                    if success:
                        st.success("✅ PDF généré !")
        
        with col4:
            # Nouveau résumé
            if st.button(t('new_summary'), use_container_width=True):
                st.session_state.summary = None
                st.rerun()


# ============================================
# TAB: FICHIERS
# ============================================

def render_files_tab(course):
    """Onglet Fichiers - Liste et gestion des fichiers du cours"""
    
    st.markdown("### 📁 Fichiers du cours")
    
    # Récupérer les fichiers
    course_details = api_request("GET", f"/api/courses/{course['id']}")
    
    if not course_details or 'files' not in course_details:
        st.warning("⚠️ Impossible de charger les fichiers")
        return
    
    files = course_details['files']
    
    if not files:
        st.info("📭 Aucun fichier dans ce cours")
        return
    
    st.caption(f"{len(files)} fichier(s) total")
    st.markdown("---")
    
    # Grouper par type
    files_by_type = {
        'pdf': [],
        'audio': [],
        'video': [],
        'image': [],
        'other': []
    }
    
    for f in files:
        file_type = f.get('file_type', 'other')
        if file_type in files_by_type:
            files_by_type[file_type].append(f)
        else:
            files_by_type['other'].append(f)
    
    # Afficher par catégorie
    categories = [
        ('pdf', '📄 Documents PDF', files_by_type['pdf']),
        ('audio', '🎵 Fichiers Audio', files_by_type['audio']),
        ('video', '🎬 Fichiers Vidéo', files_by_type['video']),
        ('image', '🖼️ Images', files_by_type['image']),
        ('other', '📁 Autres', files_by_type['other'])
    ]
    
    for cat_id, cat_title, cat_files in categories:
        if not cat_files:
            continue
        
        st.markdown(f"#### {cat_title} ({len(cat_files)})")
        
        for file_info in cat_files:
            with st.expander(f"📎 {file_info['filename']}", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    # Infos fichier
                    file_size_mb = file_info.get('file_size', 0) / (1024 * 1024)
                    st.caption(f"**Taille:** {file_size_mb:.2f} MB")
                    
                    if file_info.get('pages_count'):
                        st.caption(f"**Pages:** {file_info['pages_count']}")
                    
                    if file_info.get('media_duration'):
                        duration = file_info['media_duration']
                        mins = int(duration // 60)
                        secs = int(duration % 60)
                        st.caption(f"**Durée:** {mins}:{secs:02d}")
                    
                    st.caption(f"**Uploadé:** {file_info['uploaded_at'][:10]}")
                
                with col2:
                    # Bouton téléchargement
                    download_url = f"{API_URL}/api/courses/{course['id']}/files/{file_info['id']}/download"
                    
                    # Bouton téléchargement
                    try:
                        response = requests.get(
                            download_url,
                            headers={'Authorization': f"Bearer {st.session_state.token}"}
                        )
                        if response.status_code == 200:
                            st.download_button(
                                label="⬇️ Télécharger",
                                data=response.content,
                                file_name=file_info['filename'],
                                mime='application/octet-stream',
                                key=f"dl_{file_info['id']}"
                            )
                        else:
                            st.caption("⚠️ Téléchargement indisponible")
                    except Exception as e:
                        st.caption(f"⚠️ Erreur téléchargement: {e}")
                
                # Lecteur audio/vidéo si applicable
                if cat_id == 'audio':
                    st.markdown("**🎧 Écouter :**")
                    try:
                        # Récupérer fichier avec token
                        response = requests.get(
                            download_url,
                            headers={'Authorization': f"Bearer {st.session_state.token}"}
                        )
                        if response.status_code == 200:
                            # Passer bytes directement au lecteur
                            st.audio(response.content, format='audio/wav')
                        else:
                            st.caption(f"⚠️ Erreur chargement audio ({response.status_code})")
                    except Exception as e:
                        st.caption(f"⚠️ Lecture audio indisponible: {e}")
                
                elif cat_id == 'video':
                    st.markdown("**📺 Regarder :**")
                    try:
                        response = requests.get(
                            download_url,
                            headers={'Authorization': f"Bearer {st.session_state.token}"}
                        )
                        if response.status_code == 200:
                            st.video(response.content)
                        else:
                            st.caption(f"⚠️ Erreur chargement vidéo ({response.status_code})")
                    except Exception as e:
                        st.caption(f"⚠️ Lecture vidéo indisponible: {e}")
                
                elif cat_id == 'image':
                    st.markdown("**🖼️ Aperçu :**")
                    try:
                        st.image(download_url, use_container_width=True)
                    except Exception as e:
                        st.caption(f"⚠️ Aperçu image indisponible: {e}")
        
        st.markdown("---")
    
    # Stats résumé
    st.info(f"""
    **📊 Résumé:**
    - {len(files_by_type['pdf'])} PDF
    - {len(files_by_type['audio'])} audio
    - {len(files_by_type['video'])} vidéo
    - {len(files_by_type['image'])} image
    - {len(files_by_type['other'])} autre(s)
    """)


# ============================================
# NAVIGATION PRINCIPALE
# ============================================

def main():
    """Point d'entrée principal"""
    
    # Initialiser les valeurs par défaut du session_state
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # Sidebar
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 1rem 0;">
            <h2 style="margin: 0;">🎓 StudyGenie</h2>
            <p style="color: var(--text-muted); font-size: 0.85rem;">AI Study Assistant</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.user:
            st.markdown("---")
            user = st.session_state.user
            st.markdown(f"**👤 {user.get('email', 'User')}**")
            plan = user.get('subscription_type', 'free').upper()
            st.caption(f"{t('plan')}: {plan}")
            
            st.markdown("---")
            
            if st.button(t('logout'), use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
    
    # Routing
    if not st.session_state.user:
        if st.session_state.show_landing:
            page_landing()
        else:
            page_login()
    elif st.session_state.show_create_course:
        page_create_course()
    elif st.session_state.current_course:
        if st.session_state.current_course.get('indexed'):
            page_study()
        else:
            page_upload_files()
    else:
        page_dashboard()


if __name__ == "__main__":
    main()
