# FastAPI CRUD endpoints — production pattern
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from src.shared.database import get_db

router = APIRouter()

@router.get("/", response_model=List[dict])
async def list_items(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    offset = (page - 1) * limit
    # items = db.query(ItemModel).offset(offset).limit(limit).all()
    return []

@router.get("/{item_id}")
async def get_item(item_id: str, db: Session = Depends(get_db)):
    # item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
    # if not item:
    #     raise HTTPException(status_code=404, detail="Item not found")
    return {"id": item_id}

@router.post("/", status_code=201)
async def create_item(data: dict, db: Session = Depends(get_db)):
    # item = ItemModel(**data.model_dump())
    # db.add(item); db.commit(); db.refresh(item)
    return data

@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: str, db: Session = Depends(get_db)):
    # item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
    # if not item: raise HTTPException(404, "Not found")
    # db.delete(item); db.commit()
    return None
