# api/test_main.py
from fastapi import FastAPI

app = FastAPI(title="Render Test API")

@app.get("/")
def health_check():
    return {
        "status": "success",
        "message": "Render port binding is working perfectly!",
        "version": "test-1.0"
    }