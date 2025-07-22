from fastapi import FastAPI
from app.routes import router

app = FastAPI(title="Agente WhatsApp - Chokodelícia")

app.include_router(router)
