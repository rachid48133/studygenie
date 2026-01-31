from dotenv import load_dotenv
load_dotenv()

# backend/main.py - API FastAPI pour StudyGenie v2.0
"""
VERSION CORRIGÉE :
- Support JSON pour Login/Register (Correction Erreur 422)
- Résumé dynamique "Agressif" (Slider num_pages)
- Accès Bêta débloqué pour les testeurs
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordBearer
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
# IMPORT RAG ENGINE & TOOLS
# ============================================
from rag_engine import index_course, search_and_answer_improved

try:
    from study_tools import generate_flashcards, generate_quiz, generate_summary
    STUDY_TOOLS_AVAILABLE = True
except ImportError:
    STUDY_TOOLS_AVAILABLE = False

try:
    from pdf_export import export_summary_to_pdf
    PDF_EXPORT_ENABLED = True
except ImportError:
    PDF_EXPORT_ENABLED = False

# ============================================
# CONFIGURATION DB
# ============================================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./studygenie.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

UPLOAD_DIR = Path("uploads")
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# ============================================
# MODELS
# ============================================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String)
    subscription_type = Column(String, default="free")
    
    def to_dict(self):
        return {"id": self.id, "email": self.email, "full_name": self.full_name, "subscription_type": self.subscription_type}

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    indexed = Column(Boolean, default=False)
    user = relationship("User", back_populates="courses")
    files = relationship("CourseFile", back_populates="course", cascade="all, delete-orphan")

class CourseFile(Base):
    __tablename__ = "course_files"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    course = relationship("Course", back_populates="files")

User.courses = relationship("Course", back_populates="user", cascade="all, delete-orphan")
Base.metadata.create_all(bind=engine)

# ============================================
# SCHEMAS (INDISPENSABLE POUR JSON)
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
        user = db.query(User).filter(User.id == user_id).first()
        if not user: raise Exception()
        return user
    except: raise HTTPException(status_code=401, detail="Session expirée")

# ============================================
# APP & ROUTES
# ============================================
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
async def root(): return {"status": "StudyGenie Beta Online"}

# --- AUTH CORRIGÉE (FORMAT JSON) ---
@app.post("/api/register", response_model=Token)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    pw_hash = bcrypt.hashpw(user_data.password.encode(), bcrypt.gensalt()).decode()
    user = User(email=user_data.email, password_hash=pw_hash, full_name=user_data.full_name, subscription_type="pro")
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_access_token({"user_id": user.id}), "token_type": "bearer", "user": user.to_dict()}

@app.post("/api/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not bcrypt.checkpw(user_data.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    return {"access_token": create_access_token({"user_id": user.id}), "token_type": "bearer", "user": user.to_dict()}

# --- RÉSUMÉ DYNAMIQUE AGRESSIF ---
@app.post("/api/generate-summary")
async def api_generate_summary(data: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course_id = data.get('course_id')
    num_pages = int(data.get('num_pages', 5) or 5)
    
    # Extraction profonde (Top_k élevé)
    dynamic_top_k = min(20 + (num_pages * 5), 100) 
    
    # Prompt forcé pour la longueur
    mode = f"SUPPORT DE COURS COMPLET DE {num_pages} PAGES. NE SOIS PAS CONCIS." if num_pages > 8 else "SYNTHÈSE"

    try:
        result_rag = search_and_answer_improved(
            user_id=current_user.id, course_id=course_id, 
            question="Détaille chaque concept du cours de manière exhaustive.", 
            top_k=dynamic_top_k
        )
        content = "\n\n".join([c.get('text', '') for c in result_rag['sources']])
        summary = generate_summary(course_content=content, length=mode, language=data.get('language', 'fr'), num_pages=num_pages)
        return {"summary": summary}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
