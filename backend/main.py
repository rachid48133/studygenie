

from dotenv import load_dotenv
load_dotenv()

# backend/main.py - API FastAPI pour StudyGenie (VERSION CORRIGÉE AVEC RAG)
"""
Backend complet pour application étudiants
- Authentification
- Upload fichiers
- Indexation automatique RAG
- Questions/Réponses RAG
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timedelta
import bcrypt
import jwt
import os
from pathlib import Path
import json

# ============================================
# IMPORT RAG ENGINE (VERSION AMÉLIORÉE)
# ============================================
from rag_engine import index_course, search_and_answer_improved

# ============================================
# NOUVEAUX IMPORTS - FONCTIONNALITÉS AVANCÉES
# ============================================
# ⚠️ IMPORTS COMMENTÉS - Modules manquants ou incomplets
# from agent_explain import generate_explanation  # ❌ Fonction inexistante
# from image_extractor import extract_images_from_pdf, get_images_for_pages  # ❌ Module absent
# from export_service import export_answer_to_txt, export_answer_to_pdf  # ❌ Module absent

# ✅ IMPORT AUDIO/VIDÉO PROCESSOR
try:
    from audio_video_processor import process_media_file, is_media_file
    MEDIA_PROCESSING_ENABLED = True
    print("✅ Traitement audio/vidéo activé")
except ImportError as e:
    MEDIA_PROCESSING_ENABLED = False
    print(f"⚠️ Traitement média désactivé: {e}")

# ✅ IMPORTS NÉCESSAIRES (disponibles dans FastAPI)
from fastapi.responses import FileResponse
# Note: StreamingResponse commenté car non utilisé pour flashcards/quiz/résumé

# ============================================
# IMPORT STUDY TOOLS - Flashcards, Quiz, Résumés
# ============================================
try:
    from study_tools import generate_flashcards, generate_quiz, generate_summary
    STUDY_TOOLS_AVAILABLE = True
except ImportError:
    STUDY_TOOLS_AVAILABLE = False
    print("⚠️ study_tools.py non trouvé - Fonctionnalités désactivées")

# ============================================
# IMPORT PDF EXPORT
# ============================================
try:
    from pdf_export import (
        export_qa_to_pdf,
        export_flashcards_to_pdf,
        export_quiz_to_pdf,
        export_summary_to_pdf
    )
    from fastapi.responses import StreamingResponse
    PDF_EXPORT_ENABLED = True
    print("✅ Export PDF activé")
except ImportError as e:
    PDF_EXPORT_ENABLED = False
    print(f"⚠️ Export PDF non disponible: {e}")
    print("   Installez: pip install reportlab --break-system-packages")

# ============================================

# CONFIGURATION
# ============================================

# Base de données
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./studygenie.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# JWT
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 jours

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # DO NOT hardcode keys
# Stockage
UPLOAD_DIR = Path("uploads")
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# ============================================
# ADMIN OVERRIDES
# ============================================
ADMIN_EMAILS = {"rachidocp2000@hotmail.com"}

def is_admin(user) -> bool:
    """Retourne True si utilisateur est admin (accès total + PRO)."""
    return (getattr(user, "email", "") or "").lower() in ADMIN_EMAILS


# ============================================
# MODELS DATABASE
# ============================================

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String)
    subscription_type = Column(String, default="free")  # free, basic, pro, premium
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Stripe
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    
    # Relations
    courses = relationship("Course", back_populates="user", cascade="all, delete-orphan")
    queries = relationship("Query", back_populates="user", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "subscription_type": self.subscription_type,
            "is_admin": (self.email or "").lower() in ADMIN_EMAILS,
            "created_at": str(self.created_at)
        }


class Course(Base):
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    
    # Indexation
    indexed = Column(Boolean, default=False)
    indexing_status = Column(String, default="pending")  # pending, processing, completed, failed
    indexing_progress = Column(Integer, default=0)  # 0-100
    chunks_count = Column(Integer, default=0)
    pages_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    user = relationship("User", back_populates="courses")
    files = relationship("CourseFile", back_populates="course", cascade="all, delete-orphan")
    queries = relationship("Query", back_populates="course", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "indexed": self.indexed,
            "indexing_status": self.indexing_status,
            "indexing_progress": self.indexing_progress,
            "chunks_count": self.chunks_count,
            "pages_count": self.pages_count,
            "files_count": len(self.files),
            "created_at": str(self.created_at)
        }


class CourseFile(Base):
    __tablename__ = "course_files"
    
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_type = Column(String)  # pdf, image, pptx, docx, audio, video
    file_size = Column(Integer)  # bytes
    file_path = Column(String, nullable=False)
    pages_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    # ============================================
    # COLONNES AUDIO/VIDÉO (AJOUTÉES)
    # ============================================
    original_media_path = Column(String, nullable=True)  # Chemin audio/vidéo original
    transcription_path = Column(String, nullable=True)   # Chemin transcription texte
    media_duration = Column(Float, nullable=True)        # Durée en secondes
    
    # Relations
    course = relationship("Course", back_populates="files")
    
    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "pages_count": self.pages_count,
            "uploaded_at": str(self.uploaded_at),
            "original_media_path": self.original_media_path,
            "media_duration": self.media_duration
        }


class Query(Base):
    __tablename__ = "queries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text)
    sources = Column(Text)  # JSON string
    confidence = Column(Float)
    response_time = Column(Float)  # seconds
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relations
    user = relationship("User", back_populates="queries")
    course = relationship("Course", back_populates="queries")
    
    def to_dict(self):
        return {
            "id": self.id,
            "course_id": self.course_id,
            "question": self.question,
            "answer": self.answer,
            "sources": json.loads(self.sources) if self.sources else [],
            "confidence": self.confidence,
            "response_time": self.response_time,
            "created_at": str(self.created_at)
        }


# Créer tables
Base.metadata.create_all(bind=engine)

# ============================================
# PYDANTIC SCHEMAS
# ============================================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict


class CourseCreate(BaseModel):
    name: str
    description: Optional[str] = None


class QuestionRequest(BaseModel):
    course_id: int
    question: str
    language: Optional[str] = "fr"  # Langue de réponse: "fr" ou "en"


# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(title="StudyGenie API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production: spécifier les domaines
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# ============================================
# DÉPENDANCES
# ============================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    
    # 🔥 OVERRIDE ADMIN: admin = PRO (bypass quotas)
    if is_admin(user):
        user.subscription_type = "pro"

    return user


def check_subscription(user: User, feature: str = "basic") -> bool:
    """Vérifie si l'utilisateur a accès à une fonctionnalité"""

    # 🔓 Accès total pour un email spécifique (admin / super user)
    if is_admin(user):
        return True

    # Accès standard
    if feature == "basic":
        return True

    elif feature == "pro":
        return user.subscription_type == "pro"

    elif feature == "unlimited_questions":
        return user.subscription_type == "pro"

    return False



   
# ============================================
# ROUTES AUTHENTIFICATION
# ============================================

@app.post("/api/register", response_model=Token)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Inscription nouvel utilisateur"""
    
    # Vérifier si email existe
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password
    password_hash = bcrypt.hashpw(user_data.password.encode(), bcrypt.gensalt()).decode()
    
    # Créer user
    user = User(
        email=user_data.email,
        password_hash=password_hash,
        full_name=user_data.full_name,
        subscription_type="free"
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Créer token
    access_token = create_access_token({"user_id": user.id})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user.to_dict()
    }


# ============================================
# HEALTH CHECK & INFO
# ============================================

@app.get("/health")
async def health_check():
    """Health check pour monitoring production"""
    try:
        # Vérifier DB
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Vérifier API keys
    api_keys_ok = all([
        os.getenv('ANTHROPIC_API_KEY'),
        os.getenv('OPENAI_API_KEY'),
        os.getenv('VOYAGE_API_KEY')
    ])
    
    overall_status = "healthy" if (db_status == "healthy" and api_keys_ok) else "degraded"
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": db_status,
            "api_keys": "configured" if api_keys_ok else "missing",
            "media_processing": MEDIA_PROCESSING_ENABLED
        },
        "version": "1.0.0"
    }


@app.get("/")
async def root():
    """Info API"""
    return {
        "app": "StudyGenie API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


# ============================================
# ROUTES AUTHENTIFICATION
# ============================================

@app.post("/api/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Connexion utilisateur"""
    
    user = db.query(User).filter(User.email == user_data.email).first()
    
    if not user or not bcrypt.checkpw(user_data.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Créer token
    access_token = create_access_token({"user_id": user.id})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user.to_dict()
    }


@app.get("/api/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Info utilisateur connecté"""
    return current_user.to_dict()


# ============================================
# ROUTES COURS
# ============================================

@app.get("/api/courses")
async def get_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Liste des cours de l'utilisateur"""
    courses = db.query(Course).filter(Course.user_id == current_user.id).all()
    return [course.to_dict() for course in courses]


@app.get("/api/courses/{course_id}")
async def get_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Détails d'un cours"""
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    course_dict = course.to_dict()
    course_dict['files'] = [f.to_dict() for f in course.files]
    
    return course_dict


@app.post("/api/courses")
async def create_course(
    course_data: CourseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Créer un nouveau cours"""
    
    # ============================================
    # LIMITES PAR PLAN - COURS
    # ============================================
    PLAN_LIMITS = {
        "free": 1,
        "basic": 3,
        "pro": 10,
        "premium": 50
    }
    
    plan = current_user.subscription_type
    max_courses = PLAN_LIMITS.get(plan, 1)
    
    existing_courses = db.query(Course).filter(Course.user_id == current_user.id).count()
    
    if existing_courses >= max_courses:
        upgrade_msg = {
            "free": "Free plan limited to 1 course. Upgrade to Basic ($9.99/month) for 3 courses.",
            "basic": "Basic plan limited to 3 courses. Upgrade to Pro ($24.99/month) for 10 courses.",
            "pro": "Pro plan limited to 10 courses. Upgrade to Premium ($49.99/month) for 50 courses.",
            "premium": "Premium plan limited to 50 courses. Contact support for custom plan."
        }
        raise HTTPException(
            status_code=403,
            detail=upgrade_msg.get(plan, "Course limit reached. Please upgrade your plan.")
        )
    
    course = Course(
        user_id=current_user.id,
        name=course_data.name,
        description=course_data.description
    )
    
    db.add(course)
    db.commit()
    db.refresh(course)
    
    return course.to_dict()


@app.post("/api/courses/{course_id}/upload")
async def upload_files(
    course_id: int,
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload fichiers pour un cours"""
    
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Créer dossier utilisateur
    user_upload_dir = UPLOAD_DIR / str(current_user.id) / str(course_id)
    user_upload_dir.mkdir(parents=True, exist_ok=True)
    
    uploaded_files = []
    
    for file in files:
        # Sauvegarder fichier
        file_path = user_upload_dir / file.filename
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Déterminer type
        file_ext = file.filename.split('.')[-1].lower()
        file_type = {
    		'pdf': 'pdf',
   		'jpg': 'image',
    		'jpeg': 'image',
   		'png': 'image',
    		'pptx': 'pptx',
   		'docx': 'docx',
   		'mp4': 'video',      # NOUVEAU
   		'avi': 'video',      # NOUVEAU
    		'mov': 'video',      # NOUVEAU
   		'mp3': 'audio',      # NOUVEAU
   		'wav': 'audio',      # NOUVEAU
   		'm4a': 'audio',      # NOUVEAU
	}.get(file_ext, 'unknown')
        
        # Créer enregistrement
        course_file = CourseFile(
            course_id=course.id,
            filename=file.filename,
            file_type=file_type,
            file_size=len(content),
            file_path=str(file_path)
        )
        
        db.add(course_file)
        uploaded_files.append(course_file)
    
    db.commit()
    
    # ============================================
    # LANCER INDEXATION RAG
    # ============================================
    
    try:
        print(f"\n🚀 Début indexation cours {course_id}")
        
        # Mettre à jour statut
        course.indexing_status = "processing"
        course.indexing_progress = 0
        db.commit()
        
        # Préparer liste fichiers
        files_info = [
            {
                'file_path': str(cf.file_path),
                'file_type': cf.file_type
            }
            for cf in uploaded_files
        ]
        
        # ============================================
        # TRAITEMENT AUDIO/VIDÉO (AVANT INDEXATION)
        # ============================================
        import tempfile
        audio_video_texts = {}  # Stocker les transcriptions
        
        for file_info in files_info:
            if file_info['file_type'] in ['audio', 'video']:
                try:
                    print(f"\n🎬 Traitement média : {file_info['file_path']}")
                    
                    media_result = process_media_file(
                        file_path=file_info['file_path'],
                        language="fr",
                        method="whisper"
                    )
                    
                    # Récupérer le texte transcrit
                    transcribed_text = (media_result.get('text') or '').strip()

                    if not transcribed_text or len(transcribed_text) < 10:
                        print("   ⚠️ Transcription vide/trop courte -> skip indexation")
                        file_info['file_type'] = 'skip'
                        continue

                    print(f"   ✅ Transcription réussie")
                    print(f"   📝 {len(transcribed_text)} caractères transcrits")
                    print(f"   📊 {media_result.get('segments_count', 0)} segments")
                    print(f"   ⏱️ Durée : {media_result.get('duration', 0):.1f}s")

                    # Créer un fichier texte temporaire avec la transcription
                    temp_txt = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
                    temp_txt.write(transcribed_text)
                    temp_txt.close()
                    
                    # ============================================
                    # SAUVEGARDER MÉTADONNÉES AUDIO DANS DB
                    # ============================================
                    original_file_path = file_info['file_path']
                    course_file = db.query(CourseFile).filter(
                        CourseFile.course_id == course.id,
                        CourseFile.file_path == original_file_path
                    ).first()
                    
                    if course_file:
                        course_file.original_media_path = original_file_path
                        course_file.transcription_path = temp_txt.name
                        course_file.media_duration = media_result.get('duration', 0)
                        db.commit()
                        print(f"   💾 Métadonnées audio sauvegardées dans DB")
                    
                    # Modifier file_info pour pointer vers le texte transcrit
                    file_info['original_path'] = file_info['file_path']
                    file_info['file_path'] = temp_txt.name
                    file_info['file_type'] = 'txt'  # Traiter comme TXT
                    audio_video_texts[file_info['original_path']] = temp_txt.name
                    
                    print(f"   📝 Fichier texte créé pour indexation : {temp_txt.name}")
                        
                except Exception as media_error:
                    print(f"   ⚠️ Erreur traitement audio/vidéo (non bloquant) : {media_error}")
                    file_info['file_type'] = 'skip'
        
        # Filtrer les fichiers à indexer (enlever ceux marqués 'skip')
        files_to_index = [f for f in files_info if f.get('file_type') != 'skip']
        
        # Si rien à indexer, renvoyer une erreur claire
        if not files_to_index:
            course.indexing_status = "failed"
            db.commit()
            raise HTTPException(
                status_code=400,
                detail="Indexation impossible: aucun contenu exploitable (transcription vide/trop courte ou type non supporté)."
            )

        # Indexer avec RAG (inclut maintenant les transcriptions)
        # On prend le premier fichier à indexer
        if not files_to_index:
            raise HTTPException(status_code=400, detail="Aucun fichier à indexer")
        
        first_file = files_to_index[0]
        metadata = index_course(
            user_id=current_user.id,
            course_id=course.id,
            file_path=first_file['file_path'],
            course_name=course.name
        )


        # ============================
        # NORMALISATION METADATA (évite KeyError)
        # ============================
        chunks_count = metadata.get("chunks_count", 0)
        total_pages = (
            metadata.get("total_pages")
            or metadata.get("page_count")
            or metadata.get("pages_count")
            or 0
        )
        # Nettoyer les fichiers temporaires
        for temp_file in audio_video_texts.values():
            try:
                os.unlink(temp_file)
            except:
                pass
        
        # Mettre à jour cours
        course.indexed = True
        course.indexing_status = "completed"
        course.indexing_progress = 100
        course.chunks_count = chunks_count
        course.pages_count = total_pages
        db.commit()
        
        print(f"✅ Indexation réussie : {chunks_count} chunks, {total_pages} pages")
        
        # ============================================
        # EXTRACTION AUTOMATIQUE DES IMAGES
        # ============================================
        # ⚠️ EXTRACTION IMAGES DÉSACTIVÉE - Module image_extractor manquant
        # L'extraction d'images n'est pas essentielle pour l'indexation
        images_extracted = []
        print("⚠️ Extraction images désactivée (module image_extractor manquant)")
        
    except HTTPException as he:
        # Propager les erreurs HTTP (ex: 400) sans les transformer en 500
        raise he

    except Exception as e:
        print(f"❌ Erreur indexation : {e}")
        import traceback
        traceback.print_exc()
        
        course.indexing_status = "failed"
        db.commit()
        
        raise HTTPException(status_code=500, detail=f"Indexation failed: {str(e)}")
    
    return {
        "message": f"{len(files)} files uploaded and indexed successfully",
        "files": [f.to_dict() for f in uploaded_files],
        "indexed": True,
        "chunks_count": chunks_count,
        "pages_count": total_pages
    }


@app.delete("/api/courses/{course_id}")
async def delete_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Supprimer un cours"""
    
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Supprimer fichiers
    user_upload_dir = UPLOAD_DIR / str(current_user.id) / str(course_id)
    if user_upload_dir.exists():
        import shutil
        shutil.rmtree(user_upload_dir)
    
    # Supprimer données RAG
    user_data_dir = DATA_DIR / "users" / str(current_user.id) / "courses" / str(course_id)
    if user_data_dir.exists():
        import shutil
        shutil.rmtree(user_data_dir)
    
    # Supprimer de DB (cascade delete files et queries)
    db.delete(course)
    db.commit()
    
    return {"message": "Course deleted successfully"}


@app.get("/api/courses/{course_id}/files/{file_id}/download")
async def download_course_file(
    course_id: int,
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Télécharger un fichier (audio/vidéo original)"""
    
    # Vérifier cours appartient à l'utilisateur
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Récupérer le fichier
    course_file = db.query(CourseFile).filter(
        CourseFile.id == file_id,
        CourseFile.course_id == course_id
    ).first()
    
    if not course_file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Déterminer quel fichier renvoyer (priorité : original media > file_path)
    file_to_download = course_file.original_media_path or course_file.file_path
    
    if not Path(file_to_download).exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Renvoyer le fichier
    return FileResponse(
        path=file_to_download,
        filename=course_file.filename,
        media_type='application/octet-stream'
    )


# ============================================
# ROUTES QUESTIONS
# ============================================

@app.post("/api/ask")
async def ask_question(
    request: QuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Poser une question sur un cours"""
    
    # Vérifier que cours appartient à user
    course = db.query(Course).filter(
        Course.id == request.course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    if not course.indexed:
        raise HTTPException(status_code=400, detail="Course not indexed yet")
    
    # ============================================
    # LIMITES PAR PLAN - QUESTIONS/MOIS
    # ============================================
    QUESTION_LIMITS = {
        "free": 20,
        "basic": 250,
        "pro": 1000,
        "premium": 3000
    }
    
    plan = current_user.subscription_type
    max_questions = QUESTION_LIMITS.get(plan, 20)
    
    # Compter questions ce mois-ci
    from sqlalchemy import func, extract
    now = datetime.utcnow()
    questions_this_month = db.query(func.count(Query.id)).filter(
        Query.user_id == current_user.id,
        extract('year', Query.created_at) == now.year,
        extract('month', Query.created_at) == now.month
    ).scalar()
    
    if questions_this_month >= max_questions:
        upgrade_msg = {
            "free": f"Free plan limited to {max_questions} questions/month. Upgrade to Basic ($9.99/month) for 250 questions.",
            "basic": f"Basic plan limited to {max_questions} questions/month. Upgrade to Pro ($24.99/month) for 1000 questions.",
            "pro": f"Pro plan limited to {max_questions} questions/month. Upgrade to Premium ($49.99/month) for 3000 questions.",
            "premium": f"Premium plan limited to {max_questions} questions/month. Contact support for custom plan."
        }
        raise HTTPException(
            status_code=403,
            detail=upgrade_msg.get(plan, "Question limit reached. Please upgrade your plan.")
        )
    
    # ============================================
    # APPELER RAG POUR GÉNÉRER LA RÉPONSE
    # ============================================
    
    import time
    start_time = time.time()
    
    try:
        # Recherche et génération avec RAG AMÉLIORÉ
        result = search_and_answer_improved(
            user_id=current_user.id,
            course_id=course.id,
            question=request.question
        )
        
        answer_text = result['answer']
        sources = result['sources']
        confidence = result['confidence']
        response_time = result['response_time']
        
        # Nouveaux champs de validation
        validation = result.get('validation', {
            'score': 100,
            'is_complete': True,
            'issues': []
        })
        exercise_type = result.get('exercise_type', 'general')
        has_methodology = result.get('has_methodology', False)
        
        print(f"✅ RAG réponse générée en {response_time:.1f}s")
        print(f"📊 Score validation : {validation['score']}/100")
        print(f"📚 Type exercice : {exercise_type}")
        print(f"📖 Méthodologie détectée : {has_methodology}")
        
    except Exception as e:
        print(f"❌ Erreur RAG : {e}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(status_code=500, detail=f"Question processing failed: {str(e)}")
    
    # Sauvegarder dans historique
    query = Query(
        user_id=current_user.id,
        course_id=course.id,
        question=request.question,
        answer=answer_text,
        sources=json.dumps(sources),
        confidence=confidence,
        response_time=response_time
    )
    
    db.add(query)
    db.commit()
    
    return {
        "question": request.question,
        "answer": answer_text,
        "sources": sources,
        "confidence": confidence,
        "response_time": response_time,
        
        # ============================================
        # NOUVEAUX CHAMPS - VALIDATION & MÉTADONNÉES
        # ============================================
        "validation": {
            "score": validation.get('score', 100),
            "is_complete": validation.get('is_complete', True),
            "issues_count": validation.get('issues_count', 0),
            "issues": validation.get('issues', [])
        },
        "exercise_type": exercise_type,
        "has_methodology": has_methodology
    }


@app.get("/api/history")
async def get_history(
    course_id: Optional[int] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Historique des questions"""
    
    query = db.query(Query).filter(Query.user_id == current_user.id)
    
    if course_id:
        query = query.filter(Query.course_id == course_id)
    
    queries = query.order_by(Query.created_at.desc()).limit(limit).all()
    
    return [q.to_dict() for q in queries]


# ============================================
# ROUTES ADMIN / STATS
# ============================================

@app.get("/api/stats")
async def get_user_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Statistiques utilisateur"""
    
    total_courses = db.query(Course).filter(Course.user_id == current_user.id).count()
    total_questions = db.query(Query).filter(Query.user_id == current_user.id).count()
    
    # Questions ce mois
    from sqlalchemy import func, extract
    now = datetime.utcnow()
    questions_this_month = db.query(func.count(Query.id)).filter(
        Query.user_id == current_user.id,
        extract('year', Query.created_at) == now.year,
        extract('month', Query.created_at) == now.month
    ).scalar()
    
    # Limites par plan
    PLAN_DETAILS = {
        "free": {"courses": 1, "questions": 20, "audio_hours": 0},
        "basic": {"courses": 3, "questions": 250, "audio_hours": 0.5},
        "pro": {"courses": 10, "questions": 1000, "audio_hours": 3},
        "premium": {"courses": 50, "questions": 3000, "audio_hours": 10}
    }
    
    plan = current_user.subscription_type
    limits = PLAN_DETAILS.get(plan, PLAN_DETAILS["free"])
    
    return {
        "total_courses": total_courses,
        "total_questions": total_questions,
        "questions_this_month": questions_this_month,
        "subscription_type": current_user.subscription_type,
        "is_admin": is_admin(current_user),
        "limits": {
            "courses": limits["courses"],
            "questions_per_month": limits["questions"],
            "audio_hours_per_month": limits["audio_hours"]
        }
    }



# ============================================
# NOUVEAUX ENDPOINTS - FONCTIONNALITÉS AVANCÉES
# ============================================

@app.post("/api/ask-with-explanation")
async def ask_with_explanation(
    request: QuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint amélioré : génère réponse stricte + explication pédagogique + images
    ⚠️ DÉSACTIVÉ TEMPORAIREMENT - Module generate_explanation manquant
    """
    raise HTTPException(
        status_code=501,
        detail="Ask with explanation feature temporarily disabled. Use /api/ask instead."
    )


@app.post("/api/export-answer")
async def export_answer(
    format_type: str = Form(...),
    question: str = Form(...),
    strict_answer: str = Form(...),
    explanation: Optional[str] = Form(None),
    sources: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """
    Exporte une réponse en format TXT ou PDF
    ⚠️ DÉSACTIVÉ TEMPORAIREMENT - Module export_service manquant
    """
    raise HTTPException(
        status_code=501,
        detail="Export feature temporarily disabled"
    )


@app.get("/api/export-course/{course_id}")
async def export_course_pdf(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Télécharge le PDF original du cours
    """
    
    # Vérifier que le cours appartient à l'utilisateur
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    print(f"\n📚 Export cours PDF (ID: {course_id}, user: {current_user.email})")
    
    # Chercher le premier PDF dans les fichiers du cours
    course_file = db.query(CourseFile).filter(
        CourseFile.course_id == course_id,
        CourseFile.file_type == 'pdf'
    ).first()
    
    if not course_file:
        raise HTTPException(status_code=404, detail="Aucun PDF trouvé pour ce cours")
    
    pdf_path = course_file.file_path
    
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Fichier PDF introuvable sur le serveur")
    
    print(f"   ✅ PDF trouvé : {pdf_path}")
    
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=course_file.filename
    )


@app.get("/api/images/{course_id}/{filename}")
async def get_course_image(
    course_id: int,
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère une image extraite d'un cours
    
    Args:
        course_id: ID du cours
        filename: Nom du fichier image (ex: page_5_img_1.png)
    
    Returns:
        L'image demandée
    """
    
    # Vérifier que le cours appartient à l'utilisateur
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    print(f"\n🖼️ Récupération image (cours: {course_id}, fichier: {filename})")
    
    # Chemin de l'image
    image_path = Path(f"data/images/course_{course_id}/{filename}")
    
    if not image_path.exists():
        print(f"   ❌ Image introuvable : {image_path}")
        raise HTTPException(status_code=404, detail="Image not found")
    
    print(f"   ✅ Image trouvée : {image_path}")
    
    # Déterminer le type MIME selon l'extension
    ext = filename.split('.')[-1].lower()
    media_types = {
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'webp': 'image/webp'
    }
    media_type = media_types.get(ext, 'image/png')
    
    return FileResponse(
        image_path,
        media_type=media_type,
        filename=filename
    )


@app.get("/api/images-metadata/{course_id}")
async def get_course_images_metadata(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère toutes les métadonnées des images d'un cours
    
    Args:
        course_id: ID du cours
        
    Returns:
        Liste des métadonnées de toutes les images
    """
    
    # Vérifier que le cours appartient à l'utilisateur
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    print(f"\n📋 Récupération métadonnées images (cours: {course_id})")
    
    # Chemin du fichier de métadonnées
    metadata_path = Path(f"data/images/course_{course_id}/images_metadata.json")
    
    if not metadata_path.exists():
        print(f"   ⚠️ Aucune métadonnée trouvée")
        return {"images": [], "total": 0}
    
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            images_metadata = json.load(f)
        
        print(f"   ✅ {len(images_metadata)} image(s) trouvée(s)")
        
        return {
            "images": images_metadata,
            "total": len(images_metadata),
            "course_id": course_id
        }
        
    except Exception as e:
        print(f"   ❌ Erreur lecture métadonnées : {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# STUDY TOOLS - Flashcards, Quiz, Résumés (BILINGUE)
# ============================================

@app.post("/api/generate-flashcards")
async def api_generate_flashcards(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Génère des flashcards dans la langue choisie par l'utilisateur"""
    if not STUDY_TOOLS_AVAILABLE:
        raise HTTPException(status_code=501, detail="Feature not available")
    
    course_id = data.get('course_id')
    num_cards = data.get('num_cards', 10)
    language = data.get('language', 'fr')
    
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id required")
    
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Limites flashcards par plan
    FLASHCARD_LIMITS = {
        "free": 5,
        "basic": 10,
        "pro": 20,
        "premium": 20
    }
    max_cards = FLASHCARD_LIMITS.get(current_user.subscription_type, 5)
    if num_cards > max_cards:
        num_cards = max_cards
    
    user_plan = "pro" if is_admin(current_user) else current_user.subscription_type
    
    print(f"\n🎴 API Flashcards - Langue: {language.upper()}")
    
    # ✅ RÉCUPÉRER LE CONTENU DU COURS
    course_content = ""
    try:
        # ✅ CORRECTION : Ordre correct des paramètres (user_id, course_id)
        # ✅ AUGMENTATION : top_k=30 pour récupérer plus de contenu
        result = search_and_answer_improved(
            user_id=current_user.id,      # ✅ user_id en premier
            course_id=course_id,           # ✅ course_id en second
            question="Donne-moi le contenu principal du cours pour générer des flashcards",
            user_plan=user_plan,
            language=language,
            top_k=30  # ✅ Récupérer 30 chunks au lieu de 5 par défaut
        )
        
        # ✅ CORRECTION : Utiliser 'sources' au lieu de 'retrieved_chunks'
        if isinstance(result, dict) and 'sources' in result:
            chunks = result['sources']  # ✅ Prendre TOUS les chunks retournés (pas [:15])
            course_content = "\n\n".join([chunk.get('text', '') for chunk in chunks if chunk.get('text')])
        
        if not course_content or len(course_content) < 50:
            course_content = f"Cours: {course.name}\nDescription: {course.description or 'Contenu du cours'}"
    except Exception as e:
        print(f"⚠️ Erreur récupération contenu: {e}")
        import traceback
        traceback.print_exc()
        course_content = f"Cours: {course.name}\nGénérer des flashcards sur les concepts principaux"
    
    print(f"📊 Contenu récupéré: {len(course_content)} caractères")
    
    # ✅ APPELER generate_flashcards
    flashcards = generate_flashcards(
        course_content=course_content,
        num_cards=num_cards,
        language=language
    )
    
    return {"flashcards": flashcards}


@app.post("/api/generate-quiz")
async def api_generate_quiz(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Génère un quiz QCM dans la langue choisie par l'utilisateur"""
    if not STUDY_TOOLS_AVAILABLE:
        raise HTTPException(status_code=501, detail="Feature not available")
    
    course_id = data.get('course_id')
    num_questions = data.get('num_questions', 5)
    language = data.get('language', 'fr')
    
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id required")
    
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Limites quiz par plan
    QUIZ_LIMITS = {
        "free": 3,
        "basic": 5,
        "pro": 10,
        "premium": 10
    }
    max_quiz = QUIZ_LIMITS.get(current_user.subscription_type, 3)
    if num_questions > max_quiz:
        num_questions = max_quiz
    
    user_plan = "pro" if is_admin(current_user) else current_user.subscription_type
    
    print(f"\n📝 API Quiz - Langue: {language.upper()}")
    
    # ✅ RÉCUPÉRER LE CONTENU DU COURS
    course_content = ""
    try:
        # ✅ CORRECTION : Ordre correct des paramètres
        # ✅ AUGMENTATION : top_k=30 pour récupérer plus de contenu
        result_search = search_and_answer_improved(
            user_id=current_user.id,      # ✅ user_id en premier
            course_id=course_id,           # ✅ course_id en second
            question="Donne-moi le contenu du cours pour générer un quiz",
            user_plan=user_plan,
            language=language,
            top_k=30  # ✅ Récupérer 30 chunks
        )
        
        # ✅ CORRECTION : Utiliser 'sources' au lieu de 'retrieved_chunks'
        if isinstance(result_search, dict) and 'sources' in result_search:
            chunks = result_search['sources']  # ✅ Prendre TOUS les chunks
            course_content = "\n\n".join([chunk.get('text', '') for chunk in chunks if chunk.get('text')])
        
        if not course_content or len(course_content) < 50:
            course_content = f"Cours: {course.name}\nDescription: {course.description or 'Contenu du cours'}"
    except Exception as e:
        print(f"⚠️ Erreur récupération contenu: {e}")
        import traceback
        traceback.print_exc()
        course_content = f"Cours: {course.name}\nGénérer un quiz sur les concepts principaux"
    
    print(f"📊 Contenu récupéré: {len(course_content)} caractères")
    
    # ✅ APPELER generate_quiz
    questions = generate_quiz(
        course_content=course_content,
        num_questions=num_questions,
        language=language
    )
    
    return {"questions": questions}


@app.post("/api/generate-summary")
async def api_generate_summary(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Génère un résumé dans la langue choisie par l'utilisateur"""
    if not STUDY_TOOLS_AVAILABLE:
        raise HTTPException(status_code=501, detail="Feature not available")
    
    course_id = data.get('course_id')
    length = data.get('length', 'medium')
    language = data.get('language', 'fr')
    num_pages = int(data.get('num_pages', 5) or 5)
    
    if not course_id:
        raise HTTPException(status_code=400, detail="course_id required")
    
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    # Limites résumés par plan
    SUMMARY_LIMITS = {
        "free": ["short"],
        "basic": ["short"],
        "pro": ["short", "medium"],
        "premium": ["short", "medium", "long"]
    }
    allowed_lengths = SUMMARY_LIMITS.get(current_user.subscription_type, ["short"])
    if length not in allowed_lengths:
        length = "short"
    
    user_plan = "pro" if is_admin(current_user) else current_user.subscription_type
    
    print(f"\n📋 API Summary - Langue: {language.upper()}")
    
    # ✅ RÉCUPÉRER LE CONTENU DU COURS
    course_content = ""
    try:
        # ✅ CORRECTION : Ordre correct des paramètres
        # ✅ AUGMENTATION : top_k=40 pour résumé (plus complet)
        result = search_and_answer_improved(
            user_id=current_user.id,      # ✅ user_id en premier
            course_id=course_id,           # ✅ course_id en second
            question="Donne-moi un aperçu général du contenu de ce cours",
            user_plan=user_plan,
            language=language,
            top_k=40  # ✅ Résumé = plus de contenu
        )
        
        # ✅ CORRECTION : Utiliser 'sources' au lieu de 'retrieved_chunks'
        if isinstance(result, dict) and 'sources' in result:
            chunks = result['sources']  # ✅ Prendre TOUS les chunks
            course_content = "\n\n".join([chunk.get('text', '') for chunk in chunks if chunk.get('text')])
        
        if not course_content or len(course_content) < 100:
            course_content = f"Cours: {course.name}\nDescription: {course.description or 'Aucune description'}"
            
    except Exception as e:
        print(f"⚠️ Erreur récupération contenu: {e}")
        import traceback
        traceback.print_exc()
        course_content = f"Cours: {course.name}. Contenu partiel disponible."
    
    print(f"📊 Contenu récupéré: {len(course_content)} caractères")
    
    # Limiter la longueur
    if len(course_content) > 15000:
        course_content = course_content[:15000]
    
    # ✅ APPELER generate_summary
    result = generate_summary(
        course_content=course_content,
        length=length,
        language=language,
        num_pages=num_pages
    )
    
    return {"summary": result if isinstance(result, str) else (result.get("summary","") if isinstance(result, dict) else str(result))}


# ============================================
# ============================================
# STRIPE - CHECKOUT & WEBHOOKS
# ============================================

try:
    from stripe_integration import (
        create_checkout_session,
        verify_webhook_signature,
        process_webhook_event,
        STRIPE_PRICES
    )
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    print("⚠️ stripe_integration.py non trouvé - Paiements désactivés")


class CheckoutRequest(BaseModel):
    plan: str
    success_url: str
    cancel_url: str


@app.post("/api/create-checkout-session")
async def api_create_checkout_session(
    request: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crée une session de paiement Stripe"""
    
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe non configuré")
    
    if request.plan not in STRIPE_PRICES:
        raise HTTPException(status_code=400, detail=f"Plan {request.plan} invalide")
    
    try:
        checkout_url = create_checkout_session(
            user_id=current_user.id,
            email=current_user.email,
            plan=request.plan,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            customer_id=current_user.stripe_customer_id
        )
        
        return {"checkout_url": checkout_url}
    
    except Exception as e:
        print(f"❌ Erreur checkout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Endpoint pour les webhooks Stripe"""
    
    if not STRIPE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Stripe non configuré")
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")
    
    try:
        event = verify_webhook_signature(payload, sig_header)
        result = process_webhook_event(event, db)
        return result
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# HEALTH CHECK
# ============================================

@app.get("/")
async def root():
    return {
        "message": "StudyGenie API",
        "version": "2.0.0",
        "status": "running",
        "features": ["Q&A", "Flashcards", "Quiz", "Summary"],
        "stripe": STRIPE_AVAILABLE
    }


# ============================================
# EXPORT PDF - Q&A, Flashcards, Quiz, Résumé
# ============================================

@app.post("/api/export-qa-pdf")
async def export_qa_pdf(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Exporte Q&A en PDF"""
    if not PDF_EXPORT_ENABLED:
        raise HTTPException(status_code=501, detail="PDF export not available. Install reportlab.")
    
    question = data.get('question', '')
    answer = data.get('answer', '')
    sources = data.get('sources', [])
    course_id = data.get('course_id')
    
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    try:
        pdf_buffer = export_qa_to_pdf(question, answer, sources, course.name)
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=qa_{course.name}.pdf"}
        )
    except Exception as e:
        print(f"❌ Erreur export PDF Q&A: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")


@app.post("/api/export-flashcards-pdf")
async def api_export_flashcards_pdf(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Exporte Flashcards en PDF"""
    if not PDF_EXPORT_ENABLED:
        raise HTTPException(status_code=501, detail="PDF export not available")
    
    flashcards = data.get('flashcards', [])
    course_id = data.get('course_id')
    
    if not flashcards:
        raise HTTPException(status_code=400, detail="No flashcards provided")
    
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    try:
        pdf_buffer = export_flashcards_to_pdf(flashcards, course.name)
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=flashcards_{course.name}.pdf"}
        )
    except Exception as e:
        print(f"❌ Erreur export PDF Flashcards: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")


@app.post("/api/export-quiz-pdf")
async def api_export_quiz_pdf(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Exporte Quiz en PDF"""
    if not PDF_EXPORT_ENABLED:
        raise HTTPException(status_code=501, detail="PDF export not available")
    
    questions = data.get('questions', [])
    course_id = data.get('course_id')
    
    if not questions:
        raise HTTPException(status_code=400, detail="No questions provided")
    
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    try:
        pdf_buffer = export_quiz_to_pdf(questions, course.name)
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=quiz_{course.name}.pdf"}
        )
    except Exception as e:
        print(f"❌ Erreur export PDF Quiz: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")


@app.post("/api/export-summary-pdf")
async def api_export_summary_pdf(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Exporte Résumé en PDF"""
    if not PDF_EXPORT_ENABLED:
        raise HTTPException(status_code=501, detail="PDF export not available")
    
    summary = data.get('summary', '')
    course_id = data.get('course_id')
    
    if not summary:
        raise HTTPException(status_code=400, detail="No summary provided")
    
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    try:
        pdf_buffer = export_summary_to_pdf(summary, course.name)
        
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=resume_{course.name}.pdf"}
        )
    except Exception as e:
        print(f"❌ Erreur export PDF Résumé: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "study_tools": STUDY_TOOLS_AVAILABLE, "stripe": STRIPE_AVAILABLE, "pdf_export": PDF_EXPORT_ENABLED}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
