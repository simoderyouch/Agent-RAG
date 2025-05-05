from langchain_community.embeddings import HuggingFaceEmbeddings
from transformers import AutoTokenizer

from sentence_transformers import SentenceTransformer
from app.utils.CustomEmbedding import CustomEmbedding
from langchain_groq import ChatGroq
from dotenv import load_dotenv

from qdrant_client import QdrantClient
import os

qdrant_client = QdrantClient(host='localhost', port=6333)


model = SentenceTransformer('multi-qa-MiniLM-L6-cos-v1')

encoder = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L12-v2", model_kwargs={"device": "cpu"}
)

#encoder = CustomEmbedding(model)

tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L12-v2")


model_name = "deepseek-r1-distill-llama-70b"
groq_api_key = os.getenv("GROQ_API_KEY")

llm = ChatGroq(
    groq_api_key="",
    model_name='meta-llama/llama-4-scout-17b-16e-instruct',
    temperature=0.6
)



UPLOAD_FOLDER = "uploads/"
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "txt", "csv", "xls", "xlsx"}
MAX_FILE_SIZE_MB = 200