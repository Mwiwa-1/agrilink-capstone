from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import engine, Base, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AgriLink API")


@app.get("/")
def home():
    return {"message": "AgriLink API is running"}


@app.post("/auth/register", response_model=schemas.UserOut, status_code=201)
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(models.User).filter(models.User.phone == data.phone).first():
        raise HTTPException(status_code=400, detail="Phone already registered")
    if data.role == "farmer" and data.farmer_type is None:
        raise HTTPException(status_code=400, detail="Farmers must choose a farmer type")
    if data.role == "buyer" and data.buyer_type is None:
        raise HTTPException(status_code=400, detail="Buyers must choose a buyer type")

    user = models.User(
        full_name=data.full_name,
        phone=data.phone,
        email=email,
        password_hash=auth.hash_password(data.password),
        role=data.role,
        farmer_type=data.farmer_type,
        buyer_type=data.buyer_type,
        district=data.district,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=schemas.Token)
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email.lower()).first()
    if user is None or not auth.verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    return {"access_token": auth.create_token(user), "token_type": "bearer", "user": user}


@app.get("/users/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user
