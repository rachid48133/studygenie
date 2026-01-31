from dotenv import load_dotenv
load_dotenv()

import os
import json
import bcrypt
import jwt
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, EmailStr
from fastapi.responses import JSONResponse, StreamingResponse

# ============================================
# IMPORT DES MOTEURS (RAG & TOOLS)
# ============================================
from rag_engine import index_course, search_and_answer_improved
from study_tools import generate_summary, generate_flashcards, generate_quiz

# ============================================
# CONFIGURATION BASE DE DONNÉES
# ============================================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./studygenie.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key-pour-la-beta")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# ============================================
# MODÈLES SQLALCHEMY
# ============================================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    full_name = Column(String)
    subscription_type = Column(String, default="pro") # Forcé en PRO pour tes testeurs
    courses = relationship("Course", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id, 
            "email": self.email, 
            "full_name": self.full_name, 
            "subscription_type": self.subscription_type
        }

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    indexed = Column(Boolean, default=False)
    user = relationship("User", back_populates="courses")
    files = relationship("CourseFile", back_populates="course", cascade="all, delete-orphan")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "indexed": self.indexed, "files_count": len(self.files)}

class CourseFile(Base):
    __tablename__ = "course_files"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    course = relationship("Course", back_populates="files")

Base.metadata.create_all(bind=engine)

# ============================================
# SCHÉMAS PYDANTIC (CORRECTION ERREUR 422)
# ============================================
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class CourseCreate(BaseModel):
    name: str
    description: Optional[str] = None

# ============================================
# DÉPENDANCES & SÉCURITÉ
# ============================================
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        user = db.query(User).filter(User.id == user_id).first()
        if not user: raise Exception()
        return user
    except:
        raise HTTPException(status_code=401, detail="Session invalide ou expirée")

# ============================================
# INITIALISATION FASTAPI
# ============================================
app = FastAPI(title="StudyGenie API - Version Complète")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ============================================
# ROUTES AUTHENTIFICATION
# ============================================

@app.post("/api/register")
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email déjà enregistré")
    hashed_pw = bcrypt.hashpw(user_data.password.encode(), bcrypt.gensalt()).decode()
    user = User(email=user_data.email, password_hash=hashed_pw, full_name=user_data.full_name, subscription_type="pro")
    db.add(user)
    db.commit()
    db.refresh(user)
    token = jwt.encode({"user_id": user.id, "exp": datetime.utcnow() + timedelta(days=7)}, SECRET_KEY)
    return {"access_token": token, "token_type": "bearer", "user": user.to_dict()}

@app.post("/api/login")
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not bcrypt.checkpw(user_data.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    token = jwt.encode({"user_id": user.id, "exp": datetime.utcnow() + timedelta(days=7)}, SECRET_KEY)
    return {"access_token": token, "token_type": "bearer", "user": user.to_dict()}

# ============================================
# ROUTES COURS ET STATS (CORRECTION ERREUR 404)
# ============================================

@app.get("/api/stats")
async def get_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "total_courses": len(current_user.courses),
        "total_questions": 0,
        "questions_this_month": 0,
        "subscription_type": current_user.subscription_type
    }

@app.get("/api/courses")
async def list_courses(current_user: User = Depends(get_current_user)):
    return [c.to_dict() for c in current_user.courses]

@app.post("/api/courses")
async def create_course(data: CourseCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course = Course(user_id=current_user.id, name=data.name, description=data.description)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course.to_dict()

@app.post("/api/courses/{course_id}/upload")
async def upload_file(course_id: int, file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == current_user.id).first()
    if not course: raise HTTPException(status_code=404)
    
    file_path = UPLOAD_DIR / f"{course_id}_{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    new_file = CourseFile(course_id=course.id, filename=file.filename, file_path=str(file_path))
    db.add(new_file)
    
    # Indexation RAG immédiate
    metadata = index_course(user_id=current_user.id, course_id=course.id, file_path=str(file_path), course_name=course.name)
    course.indexed = True
    db.commit()
    return {"status": "indexed", "metadata": metadata}

# ============================================
# ROUTE RÉSUMÉ DYNAMIQUE AGRESSIF
# ============================================

@app.post("/api/generate-summary")
async def api_generate_summary(data: dict, current_user: User = Depends(get_current_user)):
    course_id = data.get('course_id')
    num_pages = int(data.get('num_pages', 5) or 5)
    
    # On force l'extraction massive (Top_k élevé)
    dynamic_top_k = min(20 + (num_pages * 5), 100)
    
    # Consigne de rédaction forcée
    target_mode = f"SUPPORT DE COURS EXHAUSTIF DE {num_pages} PAGES. DÉVELOPPE CHAQUE CONCEPT."

    try:
        # 1. Récupération du contenu via le moteur RAG amélioré
        result_rag = search_and_answer_improved(
            user_id=current_user.id, 
            course_id=course_id, 
            question="Donne-moi tous les détails techniques et explicatifs de ce cours.", 
            top_k=dynamic_top_k
        )
        
        content = "\n\n".join([c.get('text', '') for c in result_rag['sources']])
        
        # 2. Génération du résumé volumineux
        summary = generate_summary(
            course_content=content, 
            length=target_mode, 
            language=data.get('language', 'fr'), 
            num_pages=num_pages
        )
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur génération: {str(e)}")

# ============================================
# LANCEMENT
# ============================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
