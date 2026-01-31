from dotenv import load_dotenv
load_dotenv()

# backend/main.py - API FastAPI pour StudyGenie v2.0 (MODE BÊTA AGRESSIF)
"""
Backend optimisé pour tests :
- Résumé dynamique forcé (Verbosité augmentée)
- Top_k RAG jusqu'à 100 pour extraction profonde
- Accès Premium débloqué pour les testeurs
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
from fastapi.responses import FileResponse, StreamingResponse

# ============================================
# IMPORT RAG ENGINE
# ============================================
from rag_engine import index_course, search_and_answer_improved

# ✅ IMPORT AUDIO/VIDÉO PROCESSOR
try:
    from audio_video_processor import process_media_file, is_media_file
    MEDIA_PROCESSING_ENABLED = True
except ImportError:
    MEDIA_PROCESSING_ENABLED = False

# ✅ IMPORT STUDY TOOLS
try:
    from study_tools import generate_flashcards, generate_quiz, generate_summary
    STUDY_TOOLS_AVAILABLE = True
except ImportError:
    STUDY_TOOLS_AVAILABLE = False

# ✅ IMPORT PDF EXPORT
try:
    from pdf_export import export_summary_to_pdf
    PDF_EXPORT_ENABLED = True
except ImportError:
    PDF_EXPORT_ENABLED = False

# ============================================
# CONFIGURATION
# ============================================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./studygenie.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

UPLOAD_DIR = Path("uploads")
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

ADMIN_EMAILS = {"rachidocp2000@hotmail.com"}

def is_admin(user) -> bool:
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
    subscription_type = Column(String, default="free")
    created_at = Column(DateTime, default=datetime.utcnow)
    courses = relationship("Course", back_populates="user", cascade="all, delete-orphan")
    queries = relationship("Query", back_populates="user", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {"id": self.id, "email": self.email, "full_name": self.full_name, "subscription_type": self.subscription_type}

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    indexed = Column(Boolean, default=False)
    chunks_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="courses")
    files = relationship("CourseFile", back_populates="course", cascade="all, delete-orphan")
    queries = relationship("Query", back_populates="course", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {"id": self.id, "name": self.name, "indexed": self.indexed, "files_count": len(self.files)}

class CourseFile(Base):
    __tablename__ = "course_files"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    course = relationship("Course", back_populates="files")

class Query(Base):
    __tablename__ = "queries"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text)
    sources = Column(Text)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="queries")
    course = relationship("Course", back_populates="queries")

Base.metadata.create_all(bind=engine)

# ============================================
# DEPENDENCIES
# ============================================
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(OAuth2PasswordBearer(tokenUrl="token")), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None: raise HTTPException(status_code=401)
    except: raise HTTPException(status_code=401)
    user = db.query(User).filter(User.id == user_id).first()
    return user

# ============================================
# API APP SETUP
# ============================================
app = FastAPI(title="StudyGenie API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ============================================
# ROUTES
# ============================================

@app.get("/")
async def root():
    return {"status": "online", "version": "2.0.0-Beta"}

@app.post("/api/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not bcrypt.checkpw(form_data.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    return {"access_token": create_access_token({"user_id": user.id}), "token_type": "bearer", "user": user.to_dict()}

@app.post("/api/generate-summary")
async def api_generate_summary(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    GÉNÉRATION DE RÉSUMÉ AGRESSIVE :
    Force l'IA à utiliser tout le contenu pour un résultat long.
    """
    if not STUDY_TOOLS_AVAILABLE:
        raise HTTPException(status_code=501, detail="Moteur de résumé non disponible")
    
    course_id = data.get('course_id')
    language = data.get('language', 'fr')
    num_pages = int(data.get('num_pages', 5) or 5)
    
    # 1. Extraction massive (Top_k jusqu'à 100)
    # Plus l'utilisateur demande de pages, plus on donne de données brutes à l'IA
    dynamic_top_k = min(20 + (num_pages * 5), 100) 

    try:
        # Recherche RAG
        result_rag = search_and_answer_improved(
            user_id=current_user.id,
            course_id=course_id,
            question=f"Rédige un support de cours complet et extrêmement détaillé couvrant tous les points du document.",
            top_k=dynamic_top_k
        )
        
        course_content = ""
        if isinstance(result_rag, dict) and 'sources' in result_rag:
            course_content = "\n\n".join([c.get('text', '') for c in result_rag['sources']])

        # 2. DEFINITION DU MODE (FORCER LA LONGUEUR)
        # On change radicalement la consigne envoyée à l'IA
        if num_pages > 8:
            target_mode = f"SUPPORT DE COURS EXHAUSTIF DE {num_pages} PAGES. NE SOIS PAS CONCIS. DÉVELOPPE CHAQUE POINT."
        else:
            target_mode = "SYNTHÈSE PÉDAGOGIQUE"

        # 3. GÉNÉRATION VIA STUDY_TOOLS
        # On injecte la consigne de longueur dans le paramètre 'length'
        result_summary = generate_summary(
            course_content=course_content,
            length=target_mode,
            language=language,
            num_pages=num_pages
        )
        
        return {"summary": result_summary if isinstance(result_summary, str) else result_summary.get("summary", "")}
        
    except Exception as e:
        print(f"❌ Erreur Résumé: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/courses")
async def list_courses(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    courses = db.query(Course).filter(Course.user_id == current_user.id).all()
    return [c.to_dict() for c in courses]

# (Autres routes : Ask, Export PDF, etc. restent identiques à votre version actuelle)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
