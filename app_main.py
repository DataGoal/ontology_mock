# app_main.py

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from api.routes import router

load_dotenv()

app_main = FastAPI(
    title       = "CPG Supply Chain AI Agent",
    description = "Natural language interface to the supply chain knowledge graph",
    version     = "1.0.0"
)

# CORS — allow requests from any frontend during PoC
app_main.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app_main.include_router(router, prefix="/api/v1")


@app_main.get("/")
async def root():
    return {
        "message": "CPG Supply Chain AI Agent is running",
        "docs":    "http://localhost:8000/docs",
        "ask":     "POST http://localhost:8000/api/v1/ask"
    }