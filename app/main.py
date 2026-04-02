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
from app.routers import auth, tables, orders, kitchen, menu, seed, seed_charapoint, dashboard, cocina_1, cocina_movil, pedido_1, carta_virtual, demo_hub, caja, attendance, delivery, push, alerts

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


# --- Landing page ---
from fastapi import Request

@app.get("/")
async def landing_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


# --- Service Worker (must be served from root scope) ---
from fastapi.responses import FileResponse
import os

_SW_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "service-worker.js")

@app.get("/service-worker.js")
async def service_worker():
    if not os.path.isfile(_SW_PATH):
        # Fallback: intenta path relativo al cwd
        fallback = os.path.join(os.getcwd(), "static", "service-worker.js")
        if os.path.isfile(fallback):
            return FileResponse(fallback, media_type="application/javascript")
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="service-worker.js not found")
    return FileResponse(_SW_PATH, media_type="application/javascript")


# --- Routers ---
app.include_router(auth.router,    prefix="/api/v1/auth",    tags=["Auth"])
app.include_router(tables.router,  prefix="/api/v1/tables",  tags=["Tables"])
app.include_router(orders.router,  prefix="/api/v1/orders",  tags=["Orders"])
app.include_router(kitchen.router, prefix="/api/v1/kitchen", tags=["Kitchen/KDS"])
app.include_router(seed.router,    prefix="/api/v1/seed",    tags=["Seed (dev)"])
app.include_router(seed_charapoint.router, prefix="/api/v1/seed", tags=["Seed (dev)"])
app.include_router(menu.router,    prefix="/api/v1/menu",    tags=["Menu"])
app.include_router(dashboard.router, tags=["Dashboard"])
app.include_router(cocina_1.router, tags=["KDS Screen"])
app.include_router(cocina_movil.router, tags=["KDS Mobile"])
app.include_router(carta_virtual.router, tags=["Carta Virtual"])
app.include_router(demo_hub.router, tags=["Demo Hub"])
app.include_router(caja.router, tags=["Caja"])
app.include_router(pedido_1.router, tags=["POS Mesero"])
app.include_router(attendance.router, tags=["Attendance"])
app.include_router(delivery.router, tags=["Delivery"])
app.include_router(push.router, tags=["Push Notifications"])
app.include_router(alerts.router, tags=["Alerts"])