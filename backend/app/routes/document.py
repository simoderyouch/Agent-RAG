from fastapi import APIRouter
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from bs4 import BeautifulSoup
import aiohttp
import os
import shutil
import pandas as pd
from datetime import datetime , timedelta
import tempfile
import requests
from typing import Dict, List
from docx2pdf import convert
from pptxtopdf import convert as convertPPTX
from app.db.database import get_db
from app.db.models import UploadedFile, User, Chat, Classeur, File as Classeurfile
from app.utils.file_utils import sanitize_filename
from app.utils.converters import  PPTtoPDF
from app.utils.auth import get_current_user
from app.config  import UPLOAD_FOLDER, ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB
from app.services.document_service import process_document_qdrant  
from app.utils.minio import initialize_minio , BUCKET_NAME
from minio import Minio
from minio.error import S3Error
import io
from app.utils.MinIOPyMuPDFLoader import MinIOPyMuPDFLoader
import json 
from app.utils.parse_minio_path import parse_minio_path

from app.services.chat_service import generate_response  , generate_summary , generate_questions
from app.services.document_service import retrieved_docs

minio_client = initialize_minio()
router = APIRouter()






@router.get("/process/{file_id}")
async def process_file(file_id: int, user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        uploaded_file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if not uploaded_file:
            raise HTTPException(status_code=404, detail="File not found")
        
        if uploaded_file.file_type.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=415, detail="Unsupported file type")
        
        if not uploaded_file.file_path or not uploaded_file.file_path.startswith('/minio/'):
            raise HTTPException(status_code=400, detail="Invalid file path format")
        
        
        bucket_name, object_name = parse_minio_path(uploaded_file.file_path)


        # Verify object exists in MinIO before downloading
        try:
            minio_client.stat_object(bucket_name, object_name)
        except S3Error as e:
            raise HTTPException(status_code=404, detail=f"File not found in storage: {str(e)}")

        # Load the document
        try:
            loader = MinIOPyMuPDFLoader(minio_client, bucket_name, object_name)
            documents = loader.load()
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Failed to load PDF: {str(e)}")

        # Process document with Qdrant
        try:
            result = await process_document_qdrant(documents, db_path=None) 
            uploaded_file.embedding_path = result["collection"]  
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Failed to process document: {str(e)}")



        try: 
            short_name = uploaded_file.file_name.split('.')[0][:15]
            context = retrieved_docs("give me please summary for the document", uploaded_file.embedding_path)

            summary = await generate_summary(short_name, context)
            questions = await generate_questions(short_name, context)
        
        except Exception as e:
            
            raise HTTPException(status_code=500, detail=f"Failed to generate response: {str(e)}")

        print("Summuary : " , summary )
        print("Questions : ", questions)
        
      
        db.add( Chat(
            response=summary,
     
            user_id=user_id,
            uploaded_file_id=file_id,
            created_at_response=datetime.now() 
        ))

      
        db.add(Chat(
            response=json.dumps(questions),  
         
            user_id=user_id,
            uploaded_file_id=file_id,
            created_at_response=datetime.now() 
        ))

        db.commit()
        return {"message": "File processed and stored in Qdrant successfully" , "summary": summary, "questions": questions}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")













@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...), 
    user_id: int = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    try:
        # Validate file extension
        file_extension = file.filename.split(".")[-1].lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Read and validate file size
        file_content = await file.read()
        file_size_mb = len(file_content) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE_MB}MB"
            )

        # Generate unique object name
        sanitized_filename = sanitize_filename(file.filename)
        object_name = f"{user_id}/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sanitized_filename}"

        # Handle file conversion if needed
        if file_extension == 'docx':
            # Convert DOCX to PDF
            pdf_content = io.BytesIO()
            with io.BytesIO(file_content) as docx_file:
                convert(docx_file, pdf_content)
            file_content = pdf_content.getvalue()
            object_name = f"{object_name.rsplit('.', 1)[0]}.pdf"
            file_extension = 'pdf'

        elif file_extension in ['xlsx', 'xls']:
            # Convert Excel to CSV
            excel_file = io.BytesIO(file_content)
            df = pd.read_excel(excel_file)
            csv_content = io.StringIO()
            df.to_csv(csv_content, index=False)
            file_content = csv_content.getvalue().encode('utf-8')
            object_name = f"{object_name.rsplit('.', 1)[0]}.csv"
            file_extension = 'csv'

        # Upload to MinIO
        try:
            minio_client.put_object(
                BUCKET_NAME,
                object_name,
                io.BytesIO(file_content),
                length=len(file_content)
            )
        except S3Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload to MinIO: {str(e)}"
            )

        # Generate file URL
        file_url = f"/minio/{BUCKET_NAME}/{object_name}"

        # Save to database
        db_file = UploadedFile(
            file_name=sanitized_filename,
            file_type=file_extension.upper(),
            file_path=file_url,
            embedding_path=None,
            owner_id=user_id
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)

        return {
            "message": "File uploaded successfully",
            "file": {
                "id": db_file.id,
                "name": db_file.file_name,
                "type": db_file.file_type,
                "url": file_url
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )





@router.get("/files", response_model=Dict[str, List[Dict]])
def get_files_for_user(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Initialize dictionaries to store files by type
    files_by_type = {ext: [] for ext in ALLOWED_EXTENSIONS}
    
    # Categorize files by type
    for file in user.uploaded_files:
        file_ext = file.file_name.split(".")[-1].lower()
        if file_ext in ALLOWED_EXTENSIONS:
            files_by_type[file_ext].append({'id': file.id,'extention': file.file_type , 'file_name': file.file_name, 'processed': (True if file.embedding_path else False)})
    
    return files_by_type






@router.get("/file/{file_id}")
def get_file_by_id(file_id: int, user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    file = db.query(UploadedFile).filter(UploadedFile.owner_id == user_id, UploadedFile.id == file_id).first()
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Check if the file path starts with /minio/ indicating it's stored in MinIO
    if file.file_path :
        bucket_name, object_name = parse_minio_path(file.file_path)


        
        try:
            # Get presigned URL for the object that will be valid for 1 hour (3600 seconds)
            url = minio_client.presigned_get_object(
                bucket_name,
                object_name,
                expires=timedelta(hours=1)
            )
            file.file_path = url
            
        except S3Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate presigned URL: {str(e)}"
            )
    
    file.processed = bool(file.embedding_path)
    
    return file






@router.delete("/file/{file_id}")
def delete_file(file_id: int, user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        file = db.query(UploadedFile).filter(
            UploadedFile.owner_id == user_id,
            UploadedFile.id == file_id
        ).first()
        
        if file is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Delete from MinIO if file path exists and is a MinIO path
        if file.file_path and file.file_path.startswith('/minio/'):
            bucket_name, object_name = parse_minio_path(file.file_path)
            try:
                minio_client.remove_object(bucket_name, object_name)
            except S3Error as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete file from MinIO: {str(e)}"
                )
                
        
        # Delete related messages
        db.query(Chat).filter(Chat.uploaded_file_id == file_id).delete(synchronize_session=False)
        
        # Delete the file record from database
        db.delete(file)
        db.commit()
        
        return {"message": "File deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )
















@router.post("/get_pdf")
async def fetch_pdf(
    url: str,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):  
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, 
                        detail="PDF not found or URL is invalid"
                    )
                pdf_data = await response.read()
                content_disposition = response.headers.get('Content-Disposition')
                filename = None
                if content_disposition:
                    filename_start = content_disposition.find('filename=') + len('filename=')
                    filename_end = content_disposition.find(';', filename_start)
                    if filename_end == -1:
                        filename_end = len(content_disposition)
                    filename = content_disposition[filename_start:filename_end].strip('"')
                    print(filename)
                    file_extension = filename.split('.')[-1]
                
                
                # If filename not found in Content-Disposition header, use the last part of the URL
                if not filename:
                    filename = url.rsplit('/', 1)[-1]
                    file_extension = 'pdf'
                
                if file_extension.lower() not in ['pdf', "doc", "docx"]:
                    raise HTTPException(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        detail="Unsupported file type. Only PDF, DOC and DOCX are allowed"
                    )
                    
                
                file_type = file_extension.upper()
                sanitized_filename = sanitize_filename(filename)
                print(sanitized_filename)
            
                
                file_folder = os.path.join(UPLOAD_FOLDER, file_type, str(user_id), sanitized_filename.split('.')[0])
                os.makedirs(file_folder, exist_ok=True)
                
                file_path = os.path.join(file_folder, sanitized_filename)
                print(file_path)
                if os.path.exists(file_path):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="File with the same name already exists"
                    )

                with open(file_path, "wb") as f:
                    f.write(pdf_data)
                
                
                    
                if(file_extension in ['docx', 'doc']):
                    file_path_pdf = os.path.join(file_folder, str(sanitized_filename.split('.')[0]) +'.pdf')
                    print(file_path_pdf)
                    convert(file_path,file_path_pdf)
                    os.remove(file_path)
                    file_path = file_path_pdf
            
                    
                db_file = UploadedFile(file_name=sanitized_filename, file_type=file_type, file_path=file_path,embedding_path=None, owner_id=user_id)
                db.add(db_file)
                db.commit()
                db.refresh(db_file)
            
        return {"message": "File uploaded successfully" , 'file': db_file}
    except aiohttp.ClientError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch file from remote server"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/hcp_files")
async def return_hcp_files(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    classeurs = db.query(Classeur).all()
    classeur_data = []
    for classeur in classeurs:
        file_data = [{'id': file.id,  'url': file.url, 'text': file.text} for file in classeur.files]
        classeur_data.append({'text': classeur.text, 'files': file_data})

    json_file_path = os.path.join(os.path.dirname(__file__), 'classeur_data.json')
    with open(json_file_path, 'w', encoding='utf-8') as f:
        json.dump(classeur_data, f, ensure_ascii=False, indent=4)

    return classeur_data



@router.get("/extract_urls")
async def extract_urls(user_id: int = Depends(get_current_user),db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    url = "https://www.hcp.ma/downloads/"
    response = requests.get(url)
    
    if response.status_code == 200:
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract URLs and text from <div class="classeur">
        classeur_tags = soup.find_all('div', class_='classeur')
        for tag in classeur_tags:
            a_tags = tag.find_all('a')
            for a_tag in a_tags:
                url = a_tag['href']
                text = a_tag.text.strip()
                file_data = await extract_files_data(url)
                
                # Save data to the database
                classeur = Classeur(text=text)
                db.add(classeur)
                db.commit()
                
                for file_info in file_data:
                    file = Classeurfile(classeur_id=classeur.id, url=file_info['url'], text=file_info['text'])
                    db.add(file)
                    db.commit()
        
        return {"message": "Data extracted and saved to the database successfully."}
    else:
        raise HTTPException(status_code=500, detail="Failed to fetch data from the website")

async def extract_files_data(url):
    file_response = requests.get("https://www.hcp.ma" + url)
    if file_response.status_code == 200:
        file_soup = BeautifulSoup(file_response.text, 'html.parser')
        file_tags = file_soup.find_all('div', class_='titre_fichier')
        file_data = []
        for file_tag in file_tags:
            file_url = file_tag.find('a')['href']
            file_text = file_tag.find('a').text.strip()
            file_data.append({'url': file_url, 'text': file_text})
        return file_data
    else:
        return []
    
    