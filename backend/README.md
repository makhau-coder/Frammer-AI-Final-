# Frammer Analytics Dashboard

Product Usage Analytics System for Media Operations.

## Architecture

CSV Data → ETL → DuckDB → FastAPI → React Dashboard → NLQ Query System

## Project Structure
frammer-analytics/
data/
etl/
models/
api/
nlq/
dashboard/
database/
notebooks/

## Setup

Install dependencies
pip install -r requirements.txt

Run API
uvicorn api.main:app --reload

## Features

- Scalable star schema data model
- KPI engine for media analytics
- Natural language queries
- Multi-dimensional analytics

