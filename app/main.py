"""
Metraes.com — FastAPI Application
POS Restaurantes + KDS + Carta Virtual
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
import app.models  # Cargar TODOS los modelos antes que los routers
from app.routers import auth, tables, orders, kitchen, menu, seed, cocina_1, cocina_movil, pedido_1, carta_virtual

# --- App ---
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url=None,
    redirect_slashes=False,  # Evita 307 redirects en Railway HTTPS
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Static + Templates ---
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# --- Health check ---
@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


# --- Routers ---
app.include_router(auth.router,    prefix="/api/v1/auth",    tags=["Auth"])
app.include_router(tables.router,  prefix="/api/v1/tables",  tags=["Tables"])
app.include_router(orders.router,  prefix="/api/v1/orders",  tags=["Orders"])
app.include_router(kitchen.router, prefix="/api/v1/kitchen", tags=["Kitchen/KDS"])
app.include_router(seed.router,    prefix="/api/v1/seed",    tags=["Seed (dev)"])
app.include_router(menu.router,    prefix="/api/v1/menu",    tags=["Menu"])
app.include_router(cocina_1.router, tags=["KDS Screen"])
app.include_router(cocina_movil.router, tags=["KDS Mobile"])
app.include_router(carta_virtual.router, tags=["Carta Virtual"])
app.include_router(pedido_1.router, tags=["POS Mesero"])