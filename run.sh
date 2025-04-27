#!/bin/bash
# Backend'i başlat
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 &

# Frontend'i başlat
cd ../frontend
streamlit run app.py