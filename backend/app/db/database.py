from sqlalchemy import create_engine , asc
from sqlalchemy.orm import sessionmaker, Session
from .models import User, UploadedFile, Base, Chat, Classeur, File as Classeurfile


DATABASE_URL = "postgresql://postgres:admin@localhost/hcp"
engine = create_engine(DATABASE_URL)



Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()