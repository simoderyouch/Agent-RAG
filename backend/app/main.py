# New Dependency 
from langchain_community.embeddings import HuggingFaceEmbeddings

from transformers import AutoTokenizer
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from app.db.models import User, Base
from app.db.database import SessionLocal, engine

from app.routes.auth import router as auth_router
from app.routes.document import router as document_router
from app.routes.chat import router as chat_router
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os


app = FastAPI()





#app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")



origins = [
    "http://localhost:3000",
     "http://localhost:3001"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
    

)


app.include_router(auth_router, prefix="/api/auth")
app.include_router(document_router, prefix="/api/document")
app.include_router(chat_router, prefix="/api/chat")

from app.routes.filiere import router as filiere_router
from app.routes.quiz import router as quiz_router
app.include_router(quiz_router, prefix="/api/quiz")
app.include_router(filiere_router, prefix="/api/filiere", tags=["filiere"])
#############################################################################

from app.db.database import get_db
from app.db.models import Cours , Filiere
from app.utils.file_utils import sanitize_filename
from app.utils.minio import initialize_minio
from app.utils.MinIOPyMuPDFLoader import MinIOPyMuPDFLoader
from app.services.document_service import process_document_qdrant
import os 
from fastapi import HTTPException, status
from minio.error import S3Error
import io
import asyncio
from sqlalchemy.orm import Session
from datetime import datetime



minio_client = initialize_minio()


async def process_and_store_course(title, file_path, filiere_name, db: Session):
    print(file_path)
    

    # 1. Get or create the filiere
    filiere = db.query(Filiere).filter_by(name=filiere_name).first()
    if not filiere:
        print(filiere_name, " created")
        filiere = Filiere(name=filiere_name)
        db.add(filiere)
        db.commit()
        db.refresh(filiere)

    existing_course = db.query(Cours).filter_by(title=title, filiere_id=filiere.id).first()
    if existing_course:
        print(f"Course '{title}' already exists in the filiere '{filiere_name}'. Skipping.")
        return  

    try:
        with open(file_path, "rb") as file:
            file_content = file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file {file_path}: {str(e)}"
        )
    
    file_name = os.path.basename(file_path).lower()

    sanitized_filename = sanitize_filename(file_name)
    object_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sanitized_filename}"
    BUCKET_NAME = "documents"
    try:
        minio_client.put_object(
                BUCKET_NAME,
                object_name,
                io.BytesIO(file_content),
                length=len(file_content)
            )
        print("Store to minio Done  : ", object_name)

    except S3Error as e:
        raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload to MinIO: {str(e)}"
            )

        # Generate file URL
    url = f"/minio/{BUCKET_NAME}/{object_name}"

    try:
        loader = MinIOPyMuPDFLoader(minio_client, BUCKET_NAME, object_name)
        documents = loader.load()

    except Exception as e:
            raise HTTPException(status_code=422, detail=f"Failed to load PDF: {str(e)}")

    try:
        result = await process_document_qdrant(documents, db_path=None) 
        embedding_path = result["collection"]  
        print("embedding Done  : ", object_name)
      
    except Exception as e:
            raise HTTPException(status_code=422, detail=f"Failed to process document: {str(e)}")
    



    # 4. Store in the DB
    cours = Cours(
        title=title,
        url=url,
        embedding_path=embedding_path,
        filiere_id=filiere.id,
        file_type="PDF",
        
    )
    db.add(cours)
    db.commit()
    db.close()


    
filieres_and_courses = {
        "Data Science": [
            {"title": "Introduction to Data Science", "file_name": "Docker network TP.pdf"},
            {"title": "Advanced Data Analytics", "file_name": "Docker network TP.pdf"},
        ],
        "Machine Learning": [
            {"title": "Supervised Learning", "file_name": "Docker network TP.pdf"},
            {"title": "Unsupervised Learning", "file_name": "Docker network TP.pdf"},
        ]
    }

    # Static folder path
static_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static_files")

    # Process each filiere and its associated courses
async def process_all_courses(db: Session):
    for filiere_name, courses in filieres_and_courses.items():
        for course in courses:
            file_path = os.path.join(static_folder, course["file_name"])
            if os.path.exists(file_path):
                await process_and_store_course(course["title"], file_path, filiere_name, db)  # Pass db directly
            else:
                print(f"File {file_path} does not exist!")

# Correcting the startup_event to ensure db is passed correctly
@app.on_event("startup")
async def startup_event():
    # Create a session instance for the db
    db = SessionLocal()  # Using SessionLocal() to get a database session
    try:
        await process_all_courses(db)  # Pass the session to the function
    finally:
        db.close()  # Ensure the session is closed after the operation
