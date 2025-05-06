import os
import warnings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain.schema import Document
from langdetect import detect
from typing import List

from langchain_qdrant import QdrantVectorStore

from app.utils.prompt import custom_prompt_template , custom_summary_prompt_template ,custom_question_extraction_prompt_template
from app.utils.CustomEmbedding import CustomEmbedding
from app.config import encoder , llm , qdrant_client
import re
warnings.filterwarnings("ignore", message="langchain is deprecated.", category=DeprecationWarning)

from app.services.document_service import retrieved_docs




async def generate_response(
    index: str,
    question : str,
    context: list,
    memory: list = None,
    personalInfo : list = None,
    language: str = "Auto-detect",
    
):
    try:
        
        
        
        # Detect language
        language_names = {"en": "English", "fr": "French", "ar": "Arabic"}
        try:
            detected_lang = detect(context[0].page_content)
        except Exception:
            detected_lang = "en"

        selected_language = language if language != "Auto-detect" else language_names.get(detected_lang, "English")

       
        prompt_template = custom_prompt_template(selected_language)
        rag_prompt = ChatPromptTemplate.from_template(prompt_template)

        # Chain: Input → Prompt → LLM → Output
        rag_chain = (
              {
                "context": lambda _: context,
                "personalInfo": lambda _: personalInfo or [],
                "memory": lambda _: memory or [],
                "question": RunnablePassthrough(),
            }
            | rag_prompt
            | llm
            | StrOutputParser()
        )

        response = rag_chain.invoke(question)
        think_match = re.search(r"<think>(.*?)</think>", response, flags=re.DOTALL)
        think_content = think_match.group(1).strip() if think_match else ""

        response_clean = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()

        
        

        return response_clean

    except Exception as e:
        return f"Error: {str(e)}"




async def generate_summary(
    index: str,
    context: List[Document],
    language: str = "Auto-detect",
):
    try:
        language_names = {"en": "English", "fr": "French", "ar": "Arabic"}
        try:
            detected_lang = detect(context[0].page_content)
        except Exception:
            detected_lang = "en"

        selected_language = language if language != "Auto-detect" else language_names.get(detected_lang, "English")

        prompt_template = custom_summary_prompt_template(selected_language)
        rag_prompt = ChatPromptTemplate.from_template(prompt_template)

        rag_chain = (
            {"context": lambda _: context, "question": lambda _: ""}
            | rag_prompt
            | llm
            | StrOutputParser()
        )

        summary = rag_chain.invoke("")
        return summary.strip()

    except Exception as e:
        return f"Error generating summary: {str(e)}"


import json

async def generate_questions(
    index: str,
    context: List[Document],
    language: str = "Auto-detect",
    
):
    try:
        language_names = {"en": "English", "fr": "French", "ar": "Arabic"}
        try:
            detected_lang = detect(context[0].page_content)
        except Exception:
            detected_lang = "en"

        selected_language = language if language != "Auto-detect" else language_names.get(detected_lang, "English")

        prompt_template = custom_question_extraction_prompt_template(selected_language)
        rag_prompt = ChatPromptTemplate.from_template(prompt_template)

        rag_chain = (
            {"context": lambda _: context, "question": lambda _: ""}
            | rag_prompt
            | llm
            | StrOutputParser()
        )

        result = rag_chain.invoke("")
        print(result)
        match = re.search(r"\[\s*\".*?\"\s*(?:,\s*\".*?\"\s*)*\]", result, re.DOTALL)
        if match:
            questions = json.loads(match.group(0))
        else:
            questions = result

        return questions
       
    except Exception as e:
        return f"Error extracting questions: {str(e)}"