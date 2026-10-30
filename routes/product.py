from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from database.connection import get_db
from schemas.product import (
    Category, MessageResponse, ProductCreate, ProductListResponse, ProductResponse,
    ProductUpdate, SortField, SortOrder, StatisticsResponse, StockUpdate,
)
from services import product as service

router = APIRouter(prefix="/products", tags=["Products"])

ProductId = Path(..., gt=0, description="Product ID (positive integer)")


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(data: ProductCreate, db: Session = Depends(get_db)):
    return service.create_product(db, data)


@router.get("", response_model=ProductListResponse)
def get_products(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    category: Optional[Category] = None,
    is_active: Optional[bool] = None,
    min_price: Optional[Decimal] = Query(None, ge=0),
    max_price: Optional[Decimal] = Query(None, ge=0),
    in_stock: Optional[bool] = None,
    sort_by: SortField = SortField.created_at,
    sort_order: SortOrder = SortOrder.desc,
    db: Session = Depends(get_db),
):
    return service.list_products(
        db, category=category, is_active=is_active, min_price=min_price,
        max_price=max_price, in_stock=in_stock, sort_by=sort_by,
        sort_order=sort_order, page=page, limit=limit)


# NOTE: static paths (/search, /statistics, /low-stock) MUST be declared before /{product_id}
@router.get("/search", response_model=ProductListResponse)
def search_products(
    keyword: str = Query(..., min_length=1, max_length=100),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    sort_by: SortField = SortField.product_name,
    sort_order: SortOrder = SortOrder.asc,
    db: Session = Depends(get_db),
):
    return service.search_products(db, keyword, sort_by, sort_order, page, limit)


@router.get("/statistics", response_model=StatisticsResponse)
def get_statistics(db: Session = Depends(get_db)):
    return service.get_statistics(db)


@router.get("/low-stock", response_model=ProductListResponse)
def low_stock(
    threshold: int = Query(10, ge=0),
    active_only: bool = True,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return service.low_stock_products(db, threshold, active_only, page, limit)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int = ProductId, db: Session = Depends(get_db)):
    return service.get_product(db, product_id)


@router.put("/{product_id}", response_model=ProductResponse)
def replace_product(data: ProductCreate, product_id: int = ProductId, db: Session = Depends(get_db)):
    return service.replace_product(db, product_id, data)


@router.patch("/{product_id}", response_model=ProductResponse)
def patch_product(data: ProductUpdate, product_id: int = ProductId, db: Session = Depends(get_db)):
    return service.patch_product(db, product_id, data)


@router.patch("/{product_id}/stock", response_model=ProductResponse)
def update_stock(data: StockUpdate, product_id: int = ProductId, db: Session = Depends(get_db)):
    return service.update_stock(db, product_id, data)


@router.delete("/{product_id}", response_model=MessageResponse)
def delete_product(product_id: int = ProductId, db: Session = Depends(get_db)):
    product = service.soft_delete_product(db, product_id)
    return {"message": "Product deactivated (soft deleted)", "product": product}
