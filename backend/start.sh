#!/bin/bash

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Starting FastAPI server..."
uvicorn api.main:app --host 0.0.0.0 --port $PORT