from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User
from app.utils.auth import get_current_user
router = APIRouter()

@router.post("/exam_result")
def update_exam_result(exam_result: dict, user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.exam_result = exam_result
    db.commit()
    db.refresh(user)
    return {"message": "Exam result updated successfully", "exam_result": user.exam_result}