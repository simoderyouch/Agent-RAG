import warnings
import aiohttp
warnings.filterwarnings(
    "ignore", message="langchain is deprecated.", category=DeprecationWarning
)
import os
from fastapi import HTTPException

from langchain_community.document_loaders.csv_loader import CSVLoader
from typing import List
from langchain.document_loaders import (
    PyPDFLoader,
    UnstructuredHTMLLoader,
    UnstructuredFileLoader,
)
from uuid import uuid4
from langchain.schema import Document

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from fastapi import HTTPException
import tempfile
from langchain_community.document_loaders import PyMuPDFLoader
from app.config import (tokenizer, encoder)
from langchain_community.vectorstores import Chroma

from langchain_qdrant import QdrantVectorStore

from pptxtopdf import convert as convertPPTX

from qdrant_client.http import models
from app.config import encoder , qdrant_client

import numpy as np
# Load the Sentence-BERT model




async def get_document(documents):
    text_splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        tokenizer=tokenizer,
        chunk_size=512,
        chunk_overlap=50,
        strip_whitespace=True,
    )
    docs = text_splitter.split_documents(documents)
    return docs







def create_qdrant_collection(collection_name: str, vector_dim: int):
    try:
        
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=vector_dim,
                distance=models.Distance.COSINE  
            )
        )
        print(f"Collection '{collection_name}' created.")
    except Exception as e:
      
        if 'already exists' in str(e).lower():
            print(f"Collection '{collection_name}' already exists.")
        else:
            
            raise


async def process_document_qdrant(documents, db_path):
    # Step 1: Chunk the documents
    docs = await get_document(documents)

    # Step 2: Extract text from each document chunk
    texts = [doc.page_content for doc in docs]
   

    # Step 3: Generate embeddings
    embeddings = encoder.embed_documents(texts)
    embeddings = np.array(embeddings)
    

    # Step 4: Get or generate a collection name
    file_name = "default_collection"
    if docs and "source" in docs[0].metadata:
        file_name = docs[0].metadata["source"].split("/")[-1].split(".")[0]

    # Step 5: Create or validate collection in Qdrant
    create_qdrant_collection(collection_name=file_name, vector_dim=embeddings.shape[1])

    # Step 6: Upload documents and embeddings to Qdrant
    payloads = []
    for text, doc in zip(texts, docs):
        metadata = doc.metadata.copy()
        page_number = metadata.get("page", 0)
        payload = {
            "text": text,
            "page": page_number,
            **metadata
        }
        payloads.append(payload)
    points = [
        models.PointStruct(
            id=str(uuid4()),
            vector=vector.tolist(),
            payload=payload
        )
        for vector, payload in zip(embeddings, payloads)
    ]

    try:
        qdrant_client.upsert(
            collection_name=file_name,
            points=points
        )
        print(f"Inserted {len(points)} vectors into Qdrant collection '{file_name}'")
        return {"collection": file_name, "points_inserted": len(points)}
    except Exception as e:
        print(f"An error occurred while uploading to Qdrant: {e}")
        raise e




def retrieved_docs(question, embedding_url, similarity_threshold=0.2): 
    qdrant_store = QdrantVectorStore(
        client=qdrant_client,
        collection_name=embedding_url,
        embedding=encoder,
        content_payload_key="text"
    )

    # Step 1: Embed the question manually
    question_vector = encoder.embed_query(question)

    try:
        # Step 2: Search manually to access similarity scores
        results = qdrant_client.search(
            collection_name=embedding_url,
            query_vector=question_vector,
            limit=5,
            with_payload=True,
            with_vectors=False,
            score_threshold=None  
        )

        # Step 3: Check top score (smaller distance = better match)
        if results and results[0].score < similarity_threshold:
            print("Similarity too low, fetching all documents, score:", results[0].score)
            
            retrieved_docs = []
            scroll_offset = None

            while True:
                scroll_result, scroll_offset = qdrant_client.scroll(
                    collection_name=embedding_url,
                    limit=1000,
                    with_payload=True,
                    offset=scroll_offset
                )

                batch = [
                    Document(
                        page_content=doc.payload.get("text", ""),
                        metadata=doc.payload or {}
                    )
                    for doc in scroll_result
                    if hasattr(doc, "payload") and doc.payload and "text" in doc.payload
                ]
                retrieved_docs.extend(batch)

                if scroll_offset is None:
                    break
        else:
            # Convert result to langchain.Document
            retrieved_docs = [
                Document(
                    page_content=doc.payload.get("text", ""),
                    metadata=doc.payload or {}
                )
                for doc in results
                if doc.payload.get("text", "").strip()
            ]
            print(retrieved_docs)

    except Exception as e:
        return f"Error retrieving documents: {str(e)}"

    if not retrieved_docs:
        return "No relevant documents found in the database."

    # Sort by page number if present
    retrieved_docs = sorted(
        retrieved_docs,
        key=lambda doc: int(doc.metadata.get("page", 0)) if str(doc.metadata.get("page", "0")).isdigit() else 0
    )
    for doc in retrieved_docs:
            page_number = doc.metadata.get("page", "Unknown")  # Replace "Unknown" with a default if no page is found
            print(f"Document on page: {page_number}")
    return retrieved_docs
