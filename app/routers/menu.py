"""
Menu Router — Categorías y productos.
Usado por POS mesero y Carta Virtual.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.category import Category
from app.models.product import Product

router = APIRouter()


@router.get("/categories")
async def list_categories(
    restaurant_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Categorías activas del restaurante."""
    cats = db.query(Category).filter(
        Category.restaurant_id == restaurant_id,
        Category.is_active == True,
    ).order_by(Category.sort_order).all()

    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "icon": c.icon,
            "image_url": c.image_url,
            "color": c.color,
            "parent_id": c.parent_id,
        }
        for c in cats
    ]


@router.get("/products")
async def list_products(
    restaurant_id: int = Query(...),
    category_id: int = None,
    db: Session = Depends(get_db),
):
    """Productos activos. Filtrar por categoría opcionalmente."""
    query = db.query(Product).filter(
        Product.restaurant_id == restaurant_id,
        Product.is_active == True,
    )

    if category_id:
        query = query.filter(Product.category_id == category_id)

    prods = query.order_by(Product.sort_order).all()

    return [
        {
            "id": p.id,
            "category_id": p.category_id,
            "station_id": p.station_id,
            "name": p.name,
            "short_name": p.short_name,
            "description": p.description,
            "sale_price": float(p.sale_price),
            "sizes": p.sizes or [],
            "modifiers": p.modifiers or [],
            "image_url": p.image_url,
            "thumbnail_url": p.thumbnail_url,
            "is_available": p.is_available,
            "is_featured": p.is_featured,
            "is_new": p.is_new,
            "is_bestseller": p.is_bestseller,
            "is_spicy": p.is_spicy,
            "allergens": p.allergens or [],
            "dietary_tags": p.dietary_tags or [],
            "prep_time_minutes": p.prep_time_minutes,
            "is_instant": p.is_instant,
        }
        for p in prods
    ]


@router.get("/full")
async def full_menu(
    restaurant_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Menú completo: categorías + productos. Para carga inicial del POS."""
    cats = db.query(Category).filter(
        Category.restaurant_id == restaurant_id,
        Category.is_active == True,
    ).order_by(Category.sort_order).all()

    prods = db.query(Product).filter(
        Product.restaurant_id == restaurant_id,
        Product.is_active == True,
    ).order_by(Product.sort_order).all()

    return {
        "categories": [
            {"id": c.id, "name": c.name, "icon": c.icon, "color": c.color, "parent_id": c.parent_id}
            for c in cats
        ],
        "products": [
            {
                "id": p.id, "category_id": p.category_id, "station_id": p.station_id,
                "name": p.name, "short_name": p.short_name, "sale_price": float(p.sale_price),
                "sizes": p.sizes or [], "modifiers": p.modifiers or [],
                "is_available": p.is_available, "is_new": p.is_new,
                "is_bestseller": p.is_bestseller, "is_spicy": p.is_spicy,
                "image_url": p.image_url,
            }
            for p in prods
        ],
    }