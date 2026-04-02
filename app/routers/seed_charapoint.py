"""
Seed Charapoint — Datos de prueba para Charapoint Cevichería.
2 locales, 3 zonas por local, estaciones de cocina, usuarios y productos reales.
Solo para desarrollo/demo.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import hashlib

from app.core.database import get_db
from app.core.auth import hash_password
from app.models.restaurant import Restaurant
from app.models.branch import Branch
from app.models.zone import Zone
from app.models.table import Table
from app.models.kitchen_station import KitchenStation
from app.models.user import User
from app.models.category import Category
from app.models.product import Product
from app.models.cash_register import CashRegister
from app.models.order import Order

router = APIRouter()

RUC = "20600000001"


@router.post("/charapoint")
async def seed_charapoint(reset: bool = False, db: Session = Depends(get_db)):
    """Crea datos completos de Charapoint Cevichería para demo."""

    # Verificar si ya existe
    existing = db.query(Restaurant).filter(Restaurant.ruc == RUC).first()
    if existing:
        if not reset:
            return {"message": "Charapoint ya existe. Usa ?reset=true para recrear.", "restaurant_id": existing.id}
        # Romper referencias circulares Table <-> Order antes de borrar
        db.query(Table).filter(Table.restaurant_id == existing.id).update(
            {"current_order_id": None}, synchronize_session=False
        )
        db.query(Order).filter(Order.restaurant_id == existing.id).update(
            {"table_id": None}, synchronize_session=False
        )
        db.commit()
        db.delete(existing)
        db.commit()

    # --- 1. Restaurant ---
    restaurant = Restaurant(
        name="Charapoint Cevichería",
        trade_name="Charapoint",
        ruc=RUC,
        address="Iquitos, Loreto",
        district="Iquitos",
        phone="065-000001",
        whatsapp="900000001",
        email="admin@charapoint.pe",
        floor_count=1,
        yape_phone="900000001",
        plin_phone="900000001",
    )
    db.add(restaurant)
    db.flush()

    # --- 2. Branches (2 locales) ---
    branch_centro = Branch(
        restaurant_id=restaurant.id,
        name="Charapoint Centro",
        code="CEN",
        address="Jr. Próspero 100, Iquitos",
        is_main=True,
        floor_count=1,
    )
    branch_boulevard = Branch(
        restaurant_id=restaurant.id,
        name="Charapoint Boulevard",
        code="BLV",
        address="Av. La Marina 500, Iquitos",
        is_main=False,
        floor_count=1,
    )
    db.add_all([branch_centro, branch_boulevard])
    db.flush()

    branches = [branch_centro, branch_boulevard]

    # --- 3. Zones (3 por local) ---
    zone_defs = [
        {"name": "Salón", "short_name": "SAL", "zone_type": "salon", "capacity": 40, "color": "#3b82f6"},
        {"name": "Terraza", "short_name": "TRZ", "zone_type": "terraza", "capacity": 30, "color": "#22c55e"},
        {"name": "Barra", "short_name": "BAR", "zone_type": "barra", "capacity": 12, "color": "#8b5cf6"},
    ]
    tables_per_zone_type = {"salon": 12, "terraza": 10, "barra": 8}

    all_zones = {}  # branch_id -> [zones]
    mesa_num = 1

    for branch in branches:
        branch_zones = []
        for i, zd in enumerate(zone_defs):
            z = Zone(
                restaurant_id=restaurant.id,
                branch_id=branch.id,
                name=f"{zd['name']} - {branch.name}",
                short_name=zd["short_name"],
                floor_number=1,
                zone_type=zd["zone_type"],
                capacity=zd["capacity"],
                color=zd["color"],
                sort_order=i,
            )
            db.add(z)
            branch_zones.append((z, zd["zone_type"]))
        all_zones[branch.id] = branch_zones
    db.flush()

    # --- 4. Tables ---
    for branch in branches:
        for zone, zone_type in all_zones[branch.id]:
            count = tables_per_zone_type[zone_type]
            for j in range(count):
                raw = f"{restaurant.id}-{zone.id}-{mesa_num}"
                qr = hashlib.md5(raw.encode()).hexdigest()[:12]
                t = Table(
                    restaurant_id=restaurant.id,
                    branch_id=branch.id,
                    zone_id=zone.id,
                    number=mesa_num,
                    capacity=2 if zone_type == "barra" else 4,
                    shape="round" if zone_type == "barra" else "square",
                    pos_x=(j % 4) * 2,
                    pos_y=(j // 4) * 2,
                    sort_order=mesa_num,
                    qr_code=qr,
                )
                db.add(t)
                mesa_num += 1
    db.flush()

    total_mesas = mesa_num - 1
    restaurant.table_count = total_mesas

    # --- 5. Kitchen Stations ---
    stations = []
    station_data = [
        {"name": "Fríos", "short_name": "FRI", "display_name": "Fríos", "color": "#3b82f6", "icon": "🐟", "target_time_minutes": 8},
        {"name": "Calientes", "short_name": "CAL", "display_name": "Calientes", "color": "#ef4444", "icon": "🔥", "target_time_minutes": 15},
        {"name": "Frituras", "short_name": "FRT", "display_name": "Frituras", "color": "#f97316", "icon": "🍳", "target_time_minutes": 12},
        {"name": "Bebidas", "short_name": "BEB", "display_name": "Bebidas", "color": "#06b6d4", "icon": "🥤", "target_time_minutes": 3},
    ]
    for i, sd in enumerate(station_data):
        s = KitchenStation(restaurant_id=restaurant.id, sort_order=i, **sd)
        db.add(s)
        stations.append(s)
    db.flush()

    station_map = {s.name: s for s in stations}

    # --- 6. Cash Registers (1 por local) ---
    caja_centro = CashRegister(
        branch_id=branch_centro.id,
        restaurant_id=restaurant.id,
        name="Caja Centro",
        code="CC",
    )
    caja_boulevard = CashRegister(
        branch_id=branch_boulevard.id,
        restaurant_id=restaurant.id,
        name="Caja Boulevard",
        code="CB",
    )
    db.add_all([caja_centro, caja_boulevard])
    db.flush()

    # --- 7. Users ---
    # Zones para asignación de meseros
    centro_zones = all_zones[branch_centro.id]
    boulevard_zones = all_zones[branch_boulevard.id]

    users_data = [
        {"name": "Gerente General", "short_name": "Gerente", "pin": "1111", "role": "owner",
         "email": "gerente@charapoint.pe", "branch_id": branch_centro.id},
        {"name": "Admin Centro", "short_name": "Admin C.", "pin": "2222", "role": "manager",
         "branch_id": branch_centro.id},
        {"name": "Admin Boulevard", "short_name": "Admin B.", "pin": "3333", "role": "manager",
         "branch_id": branch_boulevard.id},
        {"name": "María", "short_name": "María", "pin": "4444", "role": "cashier",
         "branch_id": branch_centro.id},
        {"name": "Rosa", "short_name": "Rosa", "pin": "5555", "role": "cashier",
         "branch_id": branch_boulevard.id},
        {"name": "Carlos", "short_name": "Carlos", "pin": "6666", "role": "waiter",
         "branch_id": branch_centro.id, "zone_idx": (centro_zones, 0)},
        {"name": "José", "short_name": "José", "pin": "7777", "role": "waiter",
         "branch_id": branch_boulevard.id, "zone_idx": (boulevard_zones, 0)},
        {"name": "Chef Pedro", "short_name": "Pedro", "pin": "8888", "role": "kitchen",
         "branch_id": branch_centro.id},
    ]

    for ud in users_data:
        email = ud.pop("email", None)
        bid = ud.pop("branch_id")
        zone_idx = ud.pop("zone_idx", None)
        u = User(
            restaurant_id=restaurant.id,
            branch_id=bid,
            email=email,
            password_hash=hash_password("admin123") if email else None,
            assigned_zone_id=zone_idx[0][zone_idx[1]][0].id if zone_idx else None,
            assigned_station_id=station_map["Fríos"].id if ud["role"] == "kitchen" else None,
            **ud,
        )
        db.add(u)
    db.flush()

    # --- 8. Categories (8 categorías, sin "Menú del día") ---
    cats = {}
    cat_data = [
        {"name": "Ceviches", "icon": "🐟", "color": "#3b82f6"},
        {"name": "Tiraditos", "icon": "🍣", "color": "#06b6d4"},
        {"name": "Chicharrones", "icon": "🍳", "color": "#f97316"},
        {"name": "Arroces", "icon": "🍚", "color": "#22c55e"},
        {"name": "Sopas", "icon": "🍜", "color": "#ef4444"},
        {"name": "Especiales", "icon": "⭐", "color": "#f59e0b"},
        {"name": "Bebidas", "icon": "🥤", "color": "#06b6d4"},
        {"name": "Postres", "icon": "🍮", "color": "#ec4899"},
    ]
    for i, cd in enumerate(cat_data):
        c = Category(restaurant_id=restaurant.id, sort_order=i, **cd)
        db.add(c)
        cats[cd["name"]] = c
    db.flush()

    # --- 9. Products ---
    products_data = [
        # Ceviches -> Fríos
        {"name": "Ceviche Mixto", "short_name": "Cev. Mixto", "category": "Ceviches", "station": "Fríos",
         "price": 28.00, "cost": 11.00},
        {"name": "Ceviche de Pescado", "short_name": "Cev. Pescado", "category": "Ceviches", "station": "Fríos",
         "price": 22.00, "cost": 8.00},
        {"name": "Ceviche de Conchas Negras", "short_name": "Cev. Conchas", "category": "Ceviches", "station": "Fríos",
         "price": 35.00, "cost": 15.00},
        # Tiraditos -> Fríos
        {"name": "Tiradito Nikkei", "short_name": "Tirad. Nikkei", "category": "Tiraditos", "station": "Fríos",
         "price": 25.00, "cost": 9.00},
        {"name": "Tiradito al Rocoto", "short_name": "Tirad. Rocoto", "category": "Tiraditos", "station": "Fríos",
         "price": 22.00, "cost": 8.00, "is_spicy": True, "spicy_level": 2},
        {"name": "Tiradito Clásico", "short_name": "Tirad. Clásico", "category": "Tiraditos", "station": "Fríos",
         "price": 20.00, "cost": 7.00},
        # Chicharrones -> Frituras
        {"name": "Chicharrón de Pescado", "short_name": "Chich. Pescado", "category": "Chicharrones", "station": "Frituras",
         "price": 20.00, "cost": 7.00},
        {"name": "Chicharrón Mixto", "short_name": "Chich. Mixto", "category": "Chicharrones", "station": "Frituras",
         "price": 28.00, "cost": 10.00},
        {"name": "Chicharrón de Calamar", "short_name": "Chich. Calamar", "category": "Chicharrones", "station": "Frituras",
         "price": 22.00, "cost": 8.00},
        # Arroces -> Calientes
        {"name": "Arroz con Mariscos", "short_name": "Arroz Marisc.", "category": "Arroces", "station": "Calientes",
         "price": 30.00, "cost": 12.00},
        {"name": "Chaufa Marino", "short_name": "Chaufa Mar.", "category": "Arroces", "station": "Calientes",
         "price": 25.00, "cost": 10.00},
        {"name": "Arroz con Conchas", "short_name": "Arroz Conchas", "category": "Arroces", "station": "Calientes",
         "price": 32.00, "cost": 14.00},
        # Sopas -> Calientes
        {"name": "Chupe de Camarones", "short_name": "Chupe Cam.", "category": "Sopas", "station": "Calientes",
         "price": 30.00, "cost": 12.00},
        {"name": "Parihuela", "short_name": "Parihuela", "category": "Sopas", "station": "Calientes",
         "price": 35.00, "cost": 14.00},
        {"name": "Chilcano", "short_name": "Chilcano", "category": "Sopas", "station": "Calientes",
         "price": 15.00, "cost": 5.00},
        # Especiales -> Frituras (jalea) / Fríos (leche de tigre, causa)
        {"name": "Jalea Mixta", "short_name": "Jalea Mixta", "category": "Especiales", "station": "Frituras",
         "price": 35.00, "cost": 14.00},
        {"name": "Leche de Tigre", "short_name": "Leche Tigre", "category": "Especiales", "station": "Fríos",
         "price": 15.00, "cost": 5.00},
        {"name": "Causa Limeña", "short_name": "Causa", "category": "Especiales", "station": "Fríos",
         "price": 18.00, "cost": 6.00},
        # Bebidas -> Bebidas
        {"name": "Chicha Morada", "short_name": "Chicha", "category": "Bebidas", "station": "Bebidas",
         "price": 6.00, "cost": 1.50},
        {"name": "Inca Kola 500ml", "short_name": "Inca Kola", "category": "Bebidas", "station": "Bebidas",
         "price": 5.00, "cost": 2.00, "instant": True},
        {"name": "Cerveza Pilsen 620ml", "short_name": "Pilsen", "category": "Bebidas", "station": "Bebidas",
         "price": 10.00, "cost": 5.00, "instant": True},
        {"name": "Limonada", "short_name": "Limonada", "category": "Bebidas", "station": "Bebidas",
         "price": 7.00, "cost": 1.50},
        {"name": "Agua 500ml", "short_name": "Agua", "category": "Bebidas", "station": "Bebidas",
         "price": 3.00, "cost": 0.80, "instant": True},
        # Postres -> Bebidas (misma estación, no requiere cocina caliente)
        {"name": "Suspiro Limeño", "short_name": "Suspiro", "category": "Postres", "station": "Bebidas",
         "price": 10.00, "cost": 3.00},
        {"name": "Arroz con Leche", "short_name": "Arroz c/Leche", "category": "Postres", "station": "Bebidas",
         "price": 8.00, "cost": 2.50},
    ]

    for i, pd in enumerate(products_data):
        cat = cats[pd["category"]]
        station = station_map[pd["station"]]
        p = Product(
            restaurant_id=restaurant.id,
            category_id=cat.id,
            station_id=station.id,
            name=pd["name"],
            short_name=pd["short_name"],
            sale_price=pd["price"],
            cost_price=pd["cost"],
            modifiers=pd.get("modifiers", []),
            sizes=pd.get("sizes", []),
            is_instant=pd.get("instant", False),
            is_spicy=pd.get("is_spicy", False),
            spicy_level=pd.get("spicy_level", 0),
            prep_time_minutes=station.target_time_minutes,
            sort_order=i,
        )
        db.add(p)

    db.commit()

    return {
        "message": "Charapoint Cevichería creada exitosamente",
        "restaurant_id": restaurant.id,
        "branches": {
            "centro": branch_centro.id,
            "boulevard": branch_boulevard.id,
        },
        "data": {
            "zonas": 6,
            "mesas": total_mesas,
            "estaciones": len(stations),
            "usuarios": len(users_data),
            "categorias": len(cat_data),
            "productos": len(products_data),
            "cajas": 2,
        },
        "login_test": {
            "owner": {"pin": "1111", "restaurant_id": restaurant.id},
            "manager_centro": {"pin": "2222", "restaurant_id": restaurant.id},
            "manager_boulevard": {"pin": "3333", "restaurant_id": restaurant.id},
            "cajera_centro": {"pin": "4444", "restaurant_id": restaurant.id},
            "cajera_boulevard": {"pin": "5555", "restaurant_id": restaurant.id},
            "mesero_carlos": {"pin": "6666", "restaurant_id": restaurant.id},
            "mesero_jose": {"pin": "7777", "restaurant_id": restaurant.id},
            "cocina": {"pin": "8888", "restaurant_id": restaurant.id},
        },
    }
