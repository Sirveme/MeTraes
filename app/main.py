"""
Metraes.com — FastAPI Application
POS Restaurantes + KDS + Carta Virtual
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
import app.models  # Cargar TODOS los modelos antes que los routers
from app.routers import auth, tables, orders, kitchen, menu, seed, seed_charapoint, dashboard, cocina_1, cocina_movil, pedido_1, carta_virtual, demo_hub, caja, attendance, delivery, push, alerts


# --- Crear tablas faltantes al importar (antes de que arranque el server) ---
from app.core.database import engine, Base

print("=== CREATING TABLES (if missing) ===")
try:
    Base.metadata.create_all(bind=engine)
    print("=== TABLES OK ===")
except Exception as e:
    print(f"=== TABLE CREATION ERROR: {e} ===")


# --- Leer Service Worker al inicio — funciona en cualquier entorno ---
_SW_CONTENT = ""
for _sw_path in ["static/service-worker.js", "/app/static/service-worker.js"]:
    try:
        with open(_sw_path, "r") as f:
            _SW_CONTENT = f.read()
        print(f"=== SW loaded from {_sw_path} ({len(_SW_CONTENT)} bytes) ===")
        break
    except FileNotFoundError:
        continue
if not _SW_CONTENT:
    print("=== SW NOT FOUND in any path ===")


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


# --- Health check ---
@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


# --- Landing page ---
@app.get("/")
async def landing_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


# --- Service Worker (contenido pre-cargado, BEFORE static mount) ---
@app.get("/service-worker.js")
async def service_worker():
    return Response(_SW_CONTENT or "// SW empty", media_type="application/javascript")


# --- Static + Templates (AFTER explicit routes so they don't shadow /service-worker.js) ---
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


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