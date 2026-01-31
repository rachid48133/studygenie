from dotenv import load_dotenv
load_dotenv()

# backend/main.py - API FastAPI pour StudyGenie v2.0
"""
Backend complet optimisé pour tests Bêta :
- Résumé dynamique basé sur le nombre de pages (slider)
- Accès Premium débloqué pour les testeurs de confiance
- Moteur RAG avec extraction de contenu intelligente
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
# IMPORT RAG ENGINE
# ============================================
from rag_engine import index_course, search_and_answer_improved

# ✅ IMPORT AUDIO/VIDÉO PROCESSOR
try:
    from audio_video_processor import process_media_file, is_media_file
    MEDIA_PROCESSING_ENABLED = True
    print("✅ Traitement audio/vidéo activé")
except ImportError as e:
    MEDIA_PROCESSING_ENABLED = False
    print(f"⚠️ Traitement média désactivé: {e}")

from fastapi.responses import FileResponse

# ✅ IMPORT STUDY TOOLS
try:
    from study_tools import generate_flashcards, generate_quiz, generate_summary
    STUDY_TOOLS_AVAILABLE = True
except ImportError:
    STUDY_TOOLS_AVAILABLE = False
    print("⚠️ study_tools.py non trouvé - Fonctionnalités désactivées")

# ✅ IMPORT PDF EXPORT
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
    last_login = Column(DateTime)
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    courses = relationship("Course", back_populates="user", cascade="all, delete-orphan")
    queries = relationship("Query", back_populates="user", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id, "email": self.email, "full_name": self.full_name,
            "subscription_type": self.subscription_type, "is_admin": is_admin(self),
            "created_at": str(self.created_at)
        }

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    indexed = Column(Boolean, default=False)
    indexing_status = Column(String, default="pending")
    indexing_progress = Column(Integer, default=0)
    chunks_count = Column(Integer, default=0)
    pages_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="courses")
    files = relationship("CourseFile", back_populates="course", cascade="all, delete-orphan")
    queries = relationship("Query", back_populates="course", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "indexed": self.indexed, "indexing_status": self.indexing_status,
            "chunks_count": self.chunks_count, "pages_count": self.pages_count,
            "files_count": len(self.files), "created_at": str(self.created_at)
        }

class CourseFile(Base):
    __tablename__ = "course_files"
    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_type = Column(String)
    file_size = Column(Integer)
    file_path = Column(String, nullable=False)
    pages_count = Column(Integer, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    original_media_path = Column(String, nullable=True)
    transcription_path = Column(String, nullable=True)
    media_duration = Column(Float, nullable=True)
    course = relationship("Course", back_populates="files")
    
    def to_dict(self):
        return {
            "id": self.id, "filename": self.filename, "file_type": self.file_type,
            "file_size": self.file_size, "pages_count": self.pages_count,
            "uploaded_at": str(self.uploaded_at), "media_duration": self.media_duration
        }

class Query(Base):
    __tablename__ = "queries"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text)
    sources = Column(Text)
    confidence = Column(Float)
    response_time = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="queries")
    course = relationship("Course", back_populates="queries")
    
    def to_dict(self):
        return {
            "id": self.id, "course_id": self.course_id, "question": self.question,
            "answer": self.answer, "sources": json.loads(self.sources) if self.sources else [],
            "confidence": self.confidence, "created_at": str(self.created_at)
        }

Base.metadata.create_all(bind=engine)

# ============================================
# SCHEMAS & DEPENDENCIES
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
    language: Optional[str] = "fr"

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
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(OAuth2PasswordBearer(tokenUrl="token")), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None: raise HTTPException(status_code=401)
    except: raise HTTPException(status_code=401)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None: raise HTTPException(status_code=401)
    return user

app = FastAPI(title="StudyGenie API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ============================================
# ROUTES
# ============================================

@app.get("/")
async def root():
    return {"app": "StudyGenie", "status": "running", "version": "2.0.0"}

@app.post("/api/register", response_model=Token)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email exists")
    password_hash = bcrypt.hashpw(user_data.password.encode(), bcrypt.gensalt()).decode()
    user = User(email=user_data.email, password_hash=password_hash, full_name=user_data.full_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_access_token({"user_id": user.id}), "token_type": "bearer", "user": user.to_dict()}

@app.post("/api/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not bcrypt.checkpw(user_data.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_access_token({"user_id": user.id}), "token_type": "bearer", "user": user.to_dict()}

@app.get("/api/courses")
async def get_courses(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    courses = db.query(Course).filter(Course.user_id == current_user.id).all()
    return [c.to_dict() for c in courses]

@app.post("/api/courses")
async def create_course(course_data: CourseCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course = Course(user_id=current_user.id, name=course_data.name, description=course_data.description)
    db.add(course)
    db.commit()
    db.refresh(course)
    return course.to_dict()

@app.post("/api/courses/{course_id}/upload")
async def upload_files(course_id: int, files: List[UploadFile] = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == current_user.id).first()
    if not course: raise HTTPException(status_code=404)
    
    user_upload_dir = UPLOAD_DIR / str(current_user.id) / str(course_id)
    user_upload_dir.mkdir(parents=True, exist_ok=True)
    
    for file in files:
        file_path = user_upload_dir / file.filename
        content = await file.read()
        with open(file_path, "wb") as f: f.write(content)
        db.add(CourseFile(course_id=course.id, filename=file.filename, file_type=file.filename.split('.')[-1], file_size=len(content), file_path=str(file_path)))
    db.commit()

    # Indexation RAG simplifiée pour la démo
    metadata = index_course(user_id=current_user.id, course_id=course.id, file_path=str(user_upload_dir / files[0].filename), course_name=course.name)
    course.indexed = True
    course.chunks_count = metadata.get("chunks_count", 0)
    db.commit()
    return {"message": "Files indexed"}

@app.post("/api/ask")
async def ask_question(request: QuestionRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == request.course_id, Course.user_id == current_user.id).first()
    if not course or not course.indexed: raise HTTPException(status_code=400)
    
    result = search_and_answer_improved(user_id=current_user.id, course_id=course.id, question=request.question)
    query = Query(user_id=current_user.id, course_id=course.id, question=request.question, answer=result['answer'], sources=json.dumps(result['sources']), confidence=result['confidence'])
    db.add(query)
    db.commit()
    return result

# ============================================
# DYNAMIC SUMMARY (CORE FEATURE) 
# ============================================

@app.post("/api/generate-summary")
async def api_generate_summary(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Génère un résumé dynamique. En mode Bêta, on ignore les restrictions FREE."""
    if not STUDY_TOOLS_AVAILABLE:
        raise HTTPException(status_code=501, detail="Summary not available")
    
    course_id = data.get('course_id')
    language = data.get('language', 'fr')
    num_pages = int(data.get('num_pages', 5) or 5)  # Slider du frontend 
    
    if not course_id: raise HTTPException(status_code=400)

    # Logique de top_k dynamique pour voir plus de contenu du cours 
    dynamic_top_k = min(15 + (num_pages * 4), 100) 
    
    target_length = "long" if num_pages > 8 else ("medium" if num_pages > 3 else "short")

    try:
        # On passe le dynamic_top_k au moteur RAG 
        result = search_and_answer_improved(
            user_id=current_user.id,
            course_id=course_id,
            question=f"Extraire tout le contenu pour un résumé exhaustif de {num_pages} pages.",
            top_k=dynamic_top_k 
        )
        
        course_content = ""
        if isinstance(result, dict) and 'sources' in result:
            course_content = "\n\n".join([c.get('text', '') for c in result['sources']])

        result_summary = generate_summary(
            course_content=course_content,
            length=target_length,
            language=language,
            num_pages=num_pages
        )
        
        return {"summary": result_summary if isinstance(result_summary, str) else result_summary.get("summary","")}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# EXPORT PDF
# ============================================

@app.post("/api/export-summary-pdf")
async def api_export_summary_pdf(data: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    summary = data.get('summary', '')
    course_id = data.get('course_id')
    course = db.query(Course).filter(Course.id == course_id, Course.user_id == current_user.id).first()
    if not course or not summary: raise HTTPException(status_code=400)
    
    pdf_buffer = export_summary_to_pdf(summary, course.name)
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=resume_{course.name}.pdf"})

@app.get("/api/stats")
async def get_user_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_courses = db.query(Course).filter(Course.user_id == current_user.id).count()
    total_questions = db.query(Query).filter(Query.user_id == current_user.id).count()
    return {"total_courses": total_courses, "total_questions": total_questions, "subscription_type": current_user.subscription_type}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
