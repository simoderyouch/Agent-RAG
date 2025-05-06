from typing import List
from io import BytesIO
import fitz  
from langchain.document_loaders.base import BaseLoader
from langchain.schema import Document
from minio import Minio

class MinIOPyMuPDFLoader(BaseLoader):
    def __init__(self, minio_client: Minio, bucket_name: str, object_name: str):
        self.minio_client = minio_client
        self.bucket_name = bucket_name
        self.object_name = object_name

    def load(self) -> List[Document]:
        response = self.minio_client.get_object(self.bucket_name, self.object_name)
        pdf_bytes = response.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        documents = []
        for i, page in enumerate(doc):
            text = page.get_text()
            metadata = {
                "source": self.object_name,
                "page": i + 1
            }
            documents.append(Document(page_content=text, metadata=metadata))
        return documents