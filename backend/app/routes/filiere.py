from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session, selectinload
from app.db.database import get_db
from app.db.models import Cours, Filiere
from app.utils.auth import get_current_user
from app.utils.minio  import  initialize_minio
from minio.error import S3Error
from fastapi import HTTPException
from datetime import datetime , timedelta
router = APIRouter()
minio_client = initialize_minio()

@router.get("/filieres")
def get_all_filieres_with_courses(db: Session = Depends(get_db)):
    filieres = db.query(Filiere).options(selectinload(Filiere.courses)).all()
    return jsonable_encoder(filieres)



@router.get("/{file_id}")
def get_file_by_id(file_id: int, user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    file = db.query(Cours).filter(Cours.id == file_id).first()
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Check if the file path starts with /minio/ indicating it's stored in MinIO
    if file.url :
        parts = file.url.strip('/').split('/')
        print(parts)

        if len(parts) < 3 or parts[0] != 'minio':
            raise HTTPException(status_code=400, detail="Invalid MinIO file path format")

        bucket_name = parts[1]
        object_name = '/'.join(parts[2:])
        
  


        
        try:
            # Get presigned URL for the object that will be valid for 1 hour (3600 seconds)
            url = minio_client.presigned_get_object(
                bucket_name,
                object_name,
                expires=timedelta(hours=1)
            )
            file.url = url
            
        except S3Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate presigned URL: {str(e)}"
            )
    
    file.processed = bool(file.embedding_path)
    
    return file