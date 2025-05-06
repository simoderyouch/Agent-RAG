from passlib.context import CryptContext
from jose import jwt
from typing import Optional 
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import or_
import re
from passlib.context import CryptContext
from jose import jwt


from app.db.models import User , Base


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

REFRESH_SECRET_KEY = "hcp-refresh-secret-key"
SECRET_KEY = "hcp-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return int(user_id)  # Convert user_id to int
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.JWTError :
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")




def authenticate_user(db: Session, username_or_email: str, password: str):
    user = db.query(User).filter(or_(User.user_name == username_or_email, User.email == username_or_email)).first()
    if not user:
        return {"bool": False, "msg": "Incorrect user info"}
    if not verify_password(password, user.hashed_password):
        return {"bool": False, "msg": "Incorrect password"}
    if not user.email_verified:
        return {"bool": False, "msg": "Email not verified"}
    return {"bool": True, "user": user}




def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict):
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    data.update({"exp": expire})
    encoded_jwt = jwt.encode(data, REFRESH_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt  



def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


   





