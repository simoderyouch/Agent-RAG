from fastapi import APIRouter, Depends, HTTPException, status, Body, Response, Request, Cookie
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import timedelta
from jose import jwt

from app.db.database import get_db

from app.services.email_service import send_verification_email
from app.db.models import User
from app.utils.auth import (
    pwd_context,
    create_access_token,
    create_refresh_token,
    authenticate_user,
    
    SECRET_KEY,
    REFRESH_SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS
)



router = APIRouter()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")



@router.post("/register")
def register( first_name: str = Body(...),
    last_name: str = Body(...),
    email: str = Body(...),
    password: str = Body(...),
    db: Session = Depends(get_db) ):
    print(first_name)
    username = f"{first_name}.{last_name[0]}"
    db_user = db.query(User).filter(User.email == email).first()
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    db_user = db.query(User).filter(User.user_name == username).first()
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    
    
    
    hashed_password = pwd_context.hash(password)
    verification_token = create_access_token(data={"user": username}, expires_delta=timedelta(minutes=5))
    new_user = User(first_name=first_name, last_name=last_name, user_name=username, email=email, hashed_password=hashed_password, email_verification_token=verification_token , exam_result=None)
    db.add(new_user)
    db.commit()  # Commit the transaction to ensure new_user gets an ID assigned

# Now you can access the new_user's ID
    user_id = new_user.id
    


    db.commit()
    send_verification_email(new_user.email, new_user.email_verification_token)

    return {"message": "User registered successfully"}



@router.get("/verify-email/{verification_token}")
def verify_email(verification_token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email_verification_token == verification_token).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token")

    # Mark the user's email as verified
    user.email_verified = True
    db.commit()

    # Generate and store refresh token
    refresh_token = create_refresh_token({"user": user.user_name, "user_id": user.id})
    user.refresh_token = refresh_token
    db.commit()

    return  RedirectResponse(url=os.getenv("FRONTEND_URL"))



@router.post("/login")
def login(username_or_email: str = Body(...), password: str = Body(...), quizAnswers : list = Body(...) , db: Session = Depends(get_db)):
    auth_result = authenticate_user(db, username_or_email, password)
    
    if not auth_result["bool"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=auth_result["msg"])
    
    user = auth_result["user"]
    print(quizAnswers)
    if quizAnswers:
        user.exam_result = quizAnswers
        db.commit()

    
    access_token = create_access_token(data={"user": user.user_name , "user_id": user.id}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    
    refresh_token = user.refresh_token
    public_user_info = {
        'first_name' : user.first_name , 
        'last_name' : user.last_name ,
        'email' : user.email,
        'user_name' : user.user_name,
        'id' : user.id,
        'exam_result' : user.exam_result
    }
    
    content = {'user': public_user_info, "access_token": access_token,  "token_type": "bearer"}
    response = JSONResponse(content=content)

    response.set_cookie(
        key="jwt",
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        expires=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=True,
        samesite='none',
       
    )
    response.headers["Access-Control-Allow-Origin"]="*"
    return response



@router.post("/logout")
def logout(response: Response, refresh_token: str = Cookie(None)):
    response.delete_cookie("jwt")
    return {"message": "Logout successful"}


@router.get("/token_refresh")
def refresh_token(request: Request, db: Session = Depends(get_db)):
    try:
        cookies = request.cookies
        print(cookies)
    
        refresh_token  = cookies.get('jwt')
        if not refresh_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is missing")
        payload = jwt.decode(refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
       
        user_id = payload.get("user_id")
        print(payload)
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        
        
        
            
        access_token = create_access_token(data={"user": db_user.user_name , "user_id": db_user.id}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        
        return {"access_token": access_token, "token_type": "bearer"}
    except jwt.ExpiredSignatureError:
        try:
            db_user = db.query(User).filter(User.refresh_token == refresh_token).first()
            if db_user:
                new_refresh_token = create_refresh_token({"user": db_user.user_name , "user_id": db_user.id})
                db_user.refresh_token = new_refresh_token
                db.commit() 

                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired")
            
            else:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not associated with any user")
            
        except:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not associated with any user")
    
    except jwt.JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    
    
@router.get("/protected")
def protected_route(token: str = Depends(oauth2_scheme)):
    try:
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return {"message": "You are authorized!"}

