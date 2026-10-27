from fastapi import FastAPI
from database import engine, Base
import models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AgriLink API")

app = FastAPI(title="AgriLink API")

@app.get("/")
def home():
    return {"message": "AgriLink API is running"}