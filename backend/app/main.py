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


load_dotenv(dotenv_path="\.env")




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










    
    
    
    





    

