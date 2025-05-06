from langchain_community.embeddings import HuggingFaceEmbeddings
from transformers import AutoTokenizer

from sentence_transformers import SentenceTransformer
from app.utils.CustomEmbedding import CustomEmbedding
from langchain_groq import ChatGroq
from dotenv import load_dotenv

from qdrant_client import QdrantClient
import os
from langchain.chat_models import ChatOpenAI
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent / ".env")


qdrant_client = QdrantClient(host='localhost', port=6333)


model = SentenceTransformer('multi-qa-MiniLM-L6-cos-v1')

encoder = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L12-v2", model_kwargs={"device": "cpu"}
)

#encoder = CustomEmbedding(model)

tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L12-v2")


model_name = "deepseek-r1-distill-llama-70b"


class Settings(BaseSettings):
    app_name: str = "RAG API"
    admin_email: str = "default@example.com"
    items_per_user: int = 50
    
    class Config:
        env_file = ".env"
    

settings = Settings()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")




""" llm = ChatGroq(
    groq_api_key="",
    model_name='meta-llama/llama-4-scout-17b-16e-instruct',
    temperature=0.6
)
 """

llm = ChatOpenAI(
    model="deepseek-chat",  
    temperature=0.6,
    openai_api_key=OPENAI_API_KEY,
    openai_api_base="https://api.deepseek.com"
)

UPLOAD_FOLDER = "uploads/"
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "txt", "csv", "xls", "xlsx"}
MAX_FILE_SIZE_MB = 200