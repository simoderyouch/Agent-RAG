from fastapi import APIRouter
from fastapi.security import OAuth2PasswordBearer
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import asc
from datetime import datetime
from app.db.models import Chat, UploadedFile , Chat_Cour , Cours, User
from app.utils.auth import get_current_user
from app.db.database import get_db
from app.services.chat_service import generate_response
from app.services.document_service import retrieved_docs
import json
router = APIRouter()


def get_file_messages(file_id: int,user_id: int, db: Session) -> list:
    file = db.query(UploadedFile).filter(UploadedFile.owner_id == user_id, UploadedFile.id == file_id).first()
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    chats = db.query(Chat).filter(Chat.uploaded_file_id == file.id).order_by(asc(Chat.created_at_question)).all()
    if not chats:
        return []
    
    messages = []
    for chat in chats:
        if chat.question:
            messages.append({"role": "user", "content": chat.question})
        if chat.response:
            messages.append({"role": "assistant", "content": chat.response})
    return messages

@router.post("/{file_id}")
async def chat_with_file( question: str = Body(...), document :int = Body(...), model :str = Body(...), language :str = Body(...),  file_id: int = None, user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    
    
    question_time = datetime.now()
    file = db.query(UploadedFile).filter(UploadedFile.owner_id == user_id, UploadedFile.id == file_id).first()
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    if file.embedding_path is None:
        raise HTTPException(status_code=404, detail="Processed document not found")
    
    message_history = get_file_messages(file_id,user_id,  db)
    personalInfo = user.exam_result
 
    if personalInfo is None:
        personalInfo = []
    personalInfo.append({"role": "user", "content": f"Je suis {user.first_name} {user.last_name}"})
    try:
        context = retrieved_docs(question , file.embedding_path)
        response  = await generate_response(file.title , question, context,  memory=message_history,personalInfo=personalInfo,language=language )
        
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
    
def get_file_cour_messages(file_id: int,user_id: int, db: Session) -> list:
    chats = db.query(Chat_Cour).filter(Chat_Cour.user_id == user_id,Chat_Cour.cours_id == file_id).order_by(asc(Chat_Cour.created_at_question)).all()
    if not chats:
        return []
    
    messages = []
    for chat in chats:
        if chat.question:
            messages.append({"role": "user", "content": chat.question})
        if chat.response:
            messages.append({"role": "assistant", "content": chat.response})
    return messages

@router.post("/filiere/{file_id}")
async def chat_with_file_cour( question: str = Body(...), document :int = Body(...), model :str = Body(...), language :str = Body(...),  file_id: int = None, user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    print(file_id)
    
    question_time = datetime.now()
    file = db.query(Cours).filter(Cours.id == file_id).first()
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    print(file)
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    if file.embedding_path is None:
        raise HTTPException(status_code=404, detail="Processed document not found")

    message_history = get_file_cour_messages(file_id,user_id, db)
    personalInfo = user.exam_result
 
    if personalInfo is None:
        personalInfo = []
    personalInfo.append({"role": "user", "content": f"Je suis {user.first_name} {user.last_name}"})
    try:
        context = retrieved_docs(question , file.embedding_path)
        response  = await generate_response(file.title , question, context,  memory=message_history, personalInfo=personalInfo,language=language )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate response: {str(e)}")
    
    
    
    response_time = datetime.now()
    chat = Chat_Cour(
        question=question,
        response=response,
        user_id=user_id,
        cours_id=file_id,
        source='source',
        created_at_question=question_time,
        created_at_response=response_time 
    )
    
    db.add(chat)
    db.commit()
    return {"message": response , 'create_at': response_time}
    
@router.get("/filiere/messages/{file_id}")
async def messages_of_file_cour( file_id: int , user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    file = db.query(Cours).filter(Cours.id == file_id).first()
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    
    chats = db.query(Chat_Cour).filter(Chat_Cour.user_id == user_id,Chat_Cour.cours_id == file.id).order_by(asc(Chat_Cour.created_at_question)).all()
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
    transformed_chats.sort(key=lambda x: x["create_at"])
    return transformed_chats
     

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
    transformed_chats.sort(key=lambda x: x["create_at"])
    return transformed_chats
     

    






