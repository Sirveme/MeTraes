"""
Tables Router — CRUD de mesas + mapa + estados.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.table import Table
from app.models.zone import Zone
from app.schemas import TableCreate, TableStatusUpdate, TableTransfer

router = APIRouter()


@router.get("/")
async def list_tables(
    zone_id: int = None,
    branch_id: int = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lista mesas del restaurante con estado actual."""
    query = db.query(Table).options(
        joinedload(Table.zone),
        joinedload(Table.assigned_waiter),
    ).filter(
        Table.restaurant_id == user.restaurant_id,
        Table.is_active == True,
    )
    
    if zone_id:
        query = query.filter(Table.zone_id == zone_id)
    if branch_id:
        query = query.filter(Table.branch_id == branch_id)
    
    tables = query.order_by(Table.zone_id, Table.sort_order, Table.number).all()
    
    return [_table_to_dict(t) for t in tables]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_table(
    data: TableCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Crea una mesa nueva."""
    table = Table(
        restaurant_id=user.restaurant_id,
        branch_id=user.branch_id,
        zone_id=data.zone_id,
        number=data.number,
        label=data.label,
        capacity=data.capacity,
        pos_x=data.pos_x,
        pos_y=data.pos_y,
        shape=data.shape,
    )
    db.add(table)
    db.commit()
    db.refresh(table)
    return _table_to_dict(table)


@router.put("/{table_id}/status")
async def update_table_status(
    table_id: int,
    data: TableStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cambia estado de una mesa."""
    table = _get_table(db, table_id, user.restaurant_id)
    table.status = data.status
    
    if data.status == "free":
        table.current_order_id = None
        table.assigned_waiter_id = None
    
    db.commit()
    db.refresh(table)
    return _table_to_dict(table)


@router.put("/{table_id}/transfer")
async def transfer_table(
    table_id: int,
    data: TableTransfer,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Transfiere mesa a otro mesero."""
    table = _get_table(db, table_id, user.restaurant_id)
    table.assigned_waiter_id = data.new_waiter_id
    db.commit()
    db.refresh(table)
    return _table_to_dict(table)


# --- Helpers ---

def _get_table(db: Session, table_id: int, restaurant_id: int) -> Table:
    table = db.query(Table).filter(
        Table.id == table_id,
        Table.restaurant_id == restaurant_id,
    ).first()
    if not table:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mesa no encontrada")
    return table


def _table_to_dict(table: Table) -> dict:
    return {
        "id": table.id,
        "number": table.number,
        "label": table.label,
        "capacity": table.capacity,
        "status": table.status,
        "zone_id": table.zone_id,
        "zone_name": table.zone.short_name or table.zone.name if table.zone else None,
        "floor_number": table.zone.floor_number if table.zone else 1,
        "assigned_waiter_id": table.assigned_waiter_id,
        "assigned_waiter_name": table.assigned_waiter.short_name if table.assigned_waiter else None,
        "current_order_id": table.current_order_id,
        "display_name": table.display_name,
        "pos_x": table.pos_x,
        "pos_y": table.pos_y,
        "shape": table.shape,
    }