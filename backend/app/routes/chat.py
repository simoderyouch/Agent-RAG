from fastapi import APIRouter
from fastapi.security import OAuth2PasswordBearer
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import asc
from datetime import datetime
from app.db.models import Chat, UploadedFile
from app.utils.auth import get_current_user
from app.db.database import get_db
from app.services.chat_service import generate_response
from app.services.document_service import retrieved_docs

router = APIRouter()



@router.post("/{file_id}")
async def chat_with_file( question: str = Body(...), document :int = Body(...), model :str = Body(...), language :str = Body(...),  file_id: int = None, user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    print(question,document)
    
    question_time = datetime.now()
    file = db.query(UploadedFile).filter(UploadedFile.owner_id == user_id, UploadedFile.id == file_id).first()
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    if file.embedding_path is None:
        raise HTTPException(status_code=404, detail="Processed document not found")
    
    try:
        context = retrieved_docs(question , file.embedding_path)
        response  = await generate_response(file.file_name.split('.')[0][:15] , question, context, language=language )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate response: {str(e)}")
    
    
    
    response_time = datetime.now()
    chat = Chat(
        question=question,
        response=response,
        user_id=user_id,
        uploaded_file_id=file_id,
        source='source',
        created_at_question=question_time,
        created_at_response=response_time 
    )
    
    db.add(chat)
    db.commit()




    
    return {"message": response , 'create_at': response_time}
    
    
@router.get("/messages/{file_id}")
async def messages_of_file( file_id: int , user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    
    file = db.query(UploadedFile).filter(UploadedFile.owner_id == user_id, UploadedFile.id == file_id).first()
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    chats = db.query(Chat).filter(Chat.uploaded_file_id == file.id).order_by(asc(Chat.created_at_question)).all()
    if chats is None:
        raise HTTPException(status_code=404, detail="Chats not found")
     
    transformed_chats = []
    for chat in chats:
       
        if chat.question and chat.response:
            
            if chat.created_at_question < chat.created_at_response:
                transformed_chats.append({"message": chat.question, "is_user_message": True, "create_at": chat.created_at_question})
                transformed_chats.append({"message": chat.response, "is_user_message": False, "create_at": chat.created_at_response, "source": chat.source})
            else:
                transformed_chats.append({"message": chat.response, "is_user_message": False, "create_at": chat.created_at_response, "source": chat.source})
                transformed_chats.append({"message": chat.question, "is_user_message": True, "create_at": chat.created_at_question})
        # If only response exists
        elif chat.response:
            transformed_chats.append({"message": chat.response, "is_user_message": False, "create_at": chat.created_at_response, "source": chat.source})
    
    return transformed_chats
     

    






