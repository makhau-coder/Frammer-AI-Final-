from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"status": "success", "message": "Port binding is working!"}