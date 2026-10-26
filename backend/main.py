from fastapi import FastAPI

app = FastAPI(title="AgriLink API")

@app.get("/")
def home():
    return {"message": "AgriLink API is running"}
