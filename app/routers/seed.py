"""
Seed Router — Datos de prueba para demo del KDS.
Crea un restaurant, branch, zonas, mesas, estaciones, usuarios y productos.
Solo para desarrollo. Desactivar en producción.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

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


@router.post("/demo")
async def seed_demo_data(reset: bool = False, db: Session = Depends(get_db)):
    """Crea datos completos de un chifa para demo del KDS."""
    
    # Verificar si ya existe
    existing = db.query(Restaurant).filter(Restaurant.ruc == "20000000001").first()
    if existing:
        if not reset:
            return {"message": "Demo ya existe. Usa ?reset=true para recrear.", "restaurant_id": existing.id}
        # Romper referencias circulares Table ↔ Order antes de borrar
        db.query(Table).filter(Table.restaurant_id == existing.id).update(
            {"current_order_id": None}, synchronize_session=False
        )
        db.query(Order).filter(Order.restaurant_id == existing.id).update(
            {"table_id": None}, synchronize_session=False
        )
        db.commit()
        # Ahora sí borrar (cascade elimina zonas, mesas, productos, etc.)
        db.delete(existing)
        db.commit()
    
    # --- 1. Restaurant ---
    restaurant = Restaurant(
        name="Chifa Fénix Dorado",
        trade_name="Fénix Dorado",
        ruc="20000000001",
        address="Jr. Próspero 456, Iquitos",
        district="Iquitos",
        phone="065-123456",
        whatsapp="965123456",
        email="admin@fenixdorado.pe",
        floor_count=2,
        yape_phone="965123456",
        plin_phone="965123456",
    )
    db.add(restaurant)
    db.flush()
    
    # --- 2. Branch ---
    branch = Branch(
        restaurant_id=restaurant.id,
        name="Local Principal",
        code="LP",
        address="Jr. Próspero 456",
        is_main=True,
        floor_count=2,
    )
    db.add(branch)
    db.flush()
    
    # --- 3. Zones ---
    zones = []
    zone_data = [
        {"name": "Piso 1 - Salón", "short_name": "P1", "floor_number": 1, "zone_type": "salon", "capacity": 60, "color": "#3b82f6"},
        {"name": "Piso 1 - Barra", "short_name": "BAR", "floor_number": 1, "zone_type": "barra", "capacity": 10, "color": "#8b5cf6"},
        {"name": "Piso 2 - Salón VIP", "short_name": "VIP", "floor_number": 2, "zone_type": "salon", "capacity": 30, "color": "#f59e0b"},
        {"name": "Piso 2 - Terraza", "short_name": "TRZ", "floor_number": 2, "zone_type": "terraza", "capacity": 20, "color": "#22c55e"},
    ]
    for i, zd in enumerate(zone_data):
        z = Zone(restaurant_id=restaurant.id, branch_id=branch.id, sort_order=i, **zd)
        db.add(z)
        zones.append(z)
    db.flush()
    
    # --- 4. Tables ---
    import hashlib
    mesa_num = 1
    tables_per_zone = [12, 4, 8, 5]  # Total: 29 mesas
    for zone, count in zip(zones, tables_per_zone):
        for j in range(count):
            # QR code: hash corto único por mesa
            raw = f"{restaurant.id}-{zone.id}-{mesa_num}"
            qr = hashlib.md5(raw.encode()).hexdigest()[:12]
            t = Table(
                restaurant_id=restaurant.id,
                branch_id=branch.id,
                zone_id=zone.id,
                number=mesa_num,
                capacity=4 if zone.zone_type != "barra" else 2,
                shape="round" if zone.zone_type == "barra" else "square",
                pos_x=(j % 4) * 2,
                pos_y=(j // 4) * 2,
                sort_order=mesa_num,
                qr_code=qr,
            )
            db.add(t)
            mesa_num += 1
    db.flush()
    
    restaurant.table_count = mesa_num - 1
    
    # --- 5. Kitchen Stations ---
    stations = []
    station_data = [
        {"name": "Wok", "short_name": "WOK", "display_name": "🔥 Wok", "color": "#ef4444", "icon": "🔥", "target_time_minutes": 12},
        {"name": "Freidora", "short_name": "FRI", "display_name": "🍳 Freidora", "color": "#f97316", "icon": "🍳", "target_time_minutes": 10},
        {"name": "Parrilla", "short_name": "PAR", "display_name": "🥩 Parrilla", "color": "#a855f7", "icon": "🥩", "target_time_minutes": 18},
        {"name": "Bebidas", "short_name": "BEB", "display_name": "🥤 Bebidas", "color": "#3b82f6", "icon": "🥤", "target_time_minutes": 3},
        {"name": "Postres", "short_name": "POS", "display_name": "🍨 Postres", "color": "#ec4899", "icon": "🍨", "target_time_minutes": 5},
    ]
    for i, sd in enumerate(station_data):
        s = KitchenStation(restaurant_id=restaurant.id, sort_order=i, **sd)
        db.add(s)
        stations.append(s)
    db.flush()
    
    # --- 6. Cash Register ---
    caja = CashRegister(
        branch_id=branch.id,
        restaurant_id=restaurant.id,
        name="Caja 1",
        code="C1",
    )
    db.add(caja)
    db.flush()
    
    # --- 7. Users ---
    users_data = [
        {"name": "Duil Admin", "short_name": "Duil", "pin": "1234", "role": "owner", "email": "duil@fenixdorado.pe"},
        {"name": "Carlos Gerente", "short_name": "Carlos", "pin": "2345", "role": "manager"},
        {"name": "María Cajera", "short_name": "María", "pin": "3456", "role": "cashier"},
        {"name": "Pedro Mesero", "short_name": "Pedro", "pin": "4567", "role": "waiter"},
        {"name": "Ana Mesera", "short_name": "Ana", "pin": "5678", "role": "waiter"},
        {"name": "Luis Mesero", "short_name": "Luis", "pin": "6789", "role": "waiter"},
        {"name": "Chef Wang", "short_name": "Wang", "pin": "7890", "role": "kitchen"},
        {"name": "Cocinero Julio", "short_name": "Julio", "pin": "8901", "role": "kitchen"},
    ]
    for i, ud in enumerate(users_data):
        email = ud.pop("email", None)
        u = User(
            restaurant_id=restaurant.id,
            branch_id=branch.id,
            email=email,
            password_hash=hash_password("admin123") if email else None,
            assigned_zone_id=zones[i % len(zones)].id if ud["role"] == "waiter" else None,
            assigned_station_id=stations[0].id if ud["role"] == "kitchen" else None,
            **ud,
        )
        db.add(u)
    db.flush()
    
    # --- 8. Categories ---
    cats = {}
    cat_data = [
        {"name": "Entradas", "icon": "🥟", "color": "#f59e0b"},
        {"name": "Sopas", "icon": "🍜", "color": "#ef4444"},
        {"name": "Arroces", "icon": "🍚", "color": "#22c55e"},
        {"name": "Tallarines", "icon": "🍝", "color": "#f97316"},
        {"name": "Carnes", "icon": "🥩", "color": "#a855f7"},
        {"name": "Pollos", "icon": "🍗", "color": "#eab308"},
        {"name": "Mariscos", "icon": "🦐", "color": "#3b82f6"},
        {"name": "Bebidas", "icon": "🥤", "color": "#06b6d4"},
        {"name": "Postres", "icon": "🍨", "color": "#ec4899"},
    ]
    for i, cd in enumerate(cat_data):
        c = Category(restaurant_id=restaurant.id, sort_order=i, **cd)
        db.add(c)
        cats[cd["name"]] = c
    db.flush()
    
    # --- 9. Products ---
    products_data = [
        # Entradas → Freidora
        {"name": "Wantán Frito", "short_name": "Wantán F.", "category": "Entradas", "station": "Freidora", "price": 15.00},
        {"name": "Wantán al Vapor", "short_name": "Wantán V.", "category": "Entradas", "station": "Wok", "price": 15.00},
        {"name": "Siu Mai (6 und)", "short_name": "Siu Mai", "category": "Entradas", "station": "Wok", "price": 18.00},
        # Sopas → Wok
        {"name": "Sopa Wantán", "short_name": "Sopa Wantán", "category": "Sopas", "station": "Wok", "price": 18.00},
        {"name": "Sopa de Pollo", "short_name": "Sopa Pollo", "category": "Sopas", "station": "Wok", "price": 16.00},
        # Arroces → Wok
        {"name": "Arroz Chaufa Especial", "short_name": "Chaufa Esp.", "category": "Arroces", "station": "Wok", "price": 22.00,
         "modifiers": [
             {"group": "Proteína", "required": True, "max": 1, "options": [
                 {"name": "Pollo", "price": 0}, {"name": "Chancho", "price": 0},
                 {"name": "Mixto", "price": 5}, {"name": "Mariscos", "price": 8}
             ]},
             {"group": "Extras", "required": False, "max": 3, "options": [
                 {"name": "Extra huevo", "price": 2}, {"name": "Sin cebollita china", "price": 0},
                 {"name": "Extra picante", "price": 0}
             ]}
         ],
         "sizes": [{"name": "Personal", "price": 22.00}, {"name": "Familiar", "price": 42.00}],
        },
        {"name": "Arroz Chaufa de Pollo", "short_name": "Chaufa Pollo", "category": "Arroces", "station": "Wok", "price": 18.00},
        {"name": "Arroz Chijaukay", "short_name": "Chijaukay", "category": "Arroces", "station": "Wok", "price": 25.00},
        # Tallarines → Wok
        {"name": "Tallarín Saltado", "short_name": "Tall. Saltado", "category": "Tallarines", "station": "Wok", "price": 20.00,
         "modifiers": [
             {"group": "Proteína", "required": True, "max": 1, "options": [
                 {"name": "Pollo", "price": 0}, {"name": "Res", "price": 3}, {"name": "Mixto", "price": 5}
             ]}
         ]
        },
        {"name": "Tallarín con Pollo", "short_name": "Tall. Pollo", "category": "Tallarines", "station": "Wok", "price": 18.00},
        # Carnes → Parrilla
        {"name": "Lomo Saltado", "short_name": "Lomo Salt.", "category": "Carnes", "station": "Parrilla", "price": 28.00},
        {"name": "Costillas BBQ", "short_name": "Costillas", "category": "Carnes", "station": "Parrilla", "price": 35.00},
        # Pollos → Freidora/Parrilla
        {"name": "Pollo Tipakay", "short_name": "Tipakay", "category": "Pollos", "station": "Freidora", "price": 25.00},
        {"name": "Alitas Fritas (8 und)", "short_name": "Alitas", "category": "Pollos", "station": "Freidora", "price": 22.00},
        # Mariscos → Wok
        {"name": "Arroz con Mariscos", "short_name": "Arroz Marisc.", "category": "Mariscos", "station": "Wok", "price": 30.00},
        # Bebidas → Bebidas (instant)
        {"name": "Inca Kola 500ml", "short_name": "Inca Kola", "category": "Bebidas", "station": "Bebidas", "price": 5.00, "instant": True},
        {"name": "Coca Cola 500ml", "short_name": "Coca Cola", "category": "Bebidas", "station": "Bebidas", "price": 5.00, "instant": True},
        {"name": "Chicha Morada", "short_name": "Chicha", "category": "Bebidas", "station": "Bebidas", "price": 6.00},
        {"name": "Cerveza Pilsen 620ml", "short_name": "Pilsen", "category": "Bebidas", "station": "Bebidas", "price": 10.00, "instant": True},
        # Postres → Postres
        {"name": "Helado Mixto", "short_name": "Helado", "category": "Postres", "station": "Postres", "price": 8.00},
        {"name": "Gelatina", "short_name": "Gelatina", "category": "Postres", "station": "Postres", "price": 5.00},
    ]
    
    # Map station names to objects
    station_map = {s.name: s for s in stations}
    
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
            cost_price=pd.get("cost", round(pd["price"] * 0.38, 2)),
            modifiers=pd.get("modifiers", []),
            sizes=pd.get("sizes", []),
            is_instant=pd.get("instant", False),
            prep_time_minutes=station.target_time_minutes,
            sort_order=i,
        )
        db.add(p)
    
    db.commit()
    
    return {
        "message": "Demo creada exitosamente",
        "restaurant_id": restaurant.id,
        "branch_id": branch.id,
        "data": {
            "zonas": len(zones),
            "mesas": mesa_num - 1,
            "estaciones": len(stations),
            "usuarios": len(users_data),
            "categorias": len(cat_data),
            "productos": len(products_data),
        },
        "login_test": {
            "owner": {"pin": "1234", "restaurant_id": restaurant.id},
            "mesero": {"pin": "4567", "restaurant_id": restaurant.id},
            "cocina": {"pin": "7890", "restaurant_id": restaurant.id},
        }
    }