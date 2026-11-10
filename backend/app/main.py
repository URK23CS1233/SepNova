from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import get_settings
from .routers import patients, predictions, alerts, model, chat, admin, insights, ml

settings = get_settings()

app = FastAPI(
    title="SepNova API",
    description="Early Sepsis Prediction & ICU Monitoring — AI-powered clinical decision support",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response

app.include_router(patients.router)
app.include_router(predictions.router)
app.include_router(alerts.router)
app.include_router(model.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(insights.router)
app.include_router(ml.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "SepNova API", "version": "2.0.0"}
