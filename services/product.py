"""Business logic + database access. Routes never touch the session directly."""
from typing import Optional

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from database.models import Product
from exceptions.handlers import (
    DatabaseOperationError, DuplicateProductCodeError, InsufficientStockError,
    InvalidRequestError, ProductNotFoundError,
)
from schemas.product import (
    ProductCreate, ProductUpdate, SortField, SortOrder, StockOperation, StockUpdate,
)

SORT_COLUMNS = {
    SortField.product_name: Product.product_name,
    SortField.price: Product.price,
    SortField.quantity: Product.quantity,
    SortField.created_at: Product.created_at,
}


# ---------- helpers ----------
def _commit(db: Session, action: str, duplicate_code: Optional[str] = None) -> None:
    """commit(); on ANY failure rollback() so the session is never left in a failed state."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if duplicate_code is not None:
            raise DuplicateProductCodeError(
                f"Product code '{duplicate_code}' already exists") from exc
        raise DatabaseOperationError(f"{action} failed: constraint violation") from exc
    except OperationalError:
        db.rollback()
        raise  # handled globally -> 503 "Database connection failure"
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseOperationError(f"{action} failed") from exc


def _get_or_404(db: Session, product_id: int, lock: bool = False) -> Product:
    stmt = select(Product).where(Product.product_id == product_id)
    if lock:
        stmt = stmt.with_for_update()  # row lock => safe concurrent stock updates
    product = db.execute(stmt).scalar_one_or_none()
    if product is None:
        raise ProductNotFoundError(f"Product with id {product_id} not found")
    return product


def _code_exists(db: Session, code: str, exclude_id: Optional[int] = None) -> bool:
    stmt = select(Product.product_id).where(Product.product_code == code)
    if exclude_id is not None:
        stmt = stmt.where(Product.product_id != exclude_id)
    return db.execute(stmt).first() is not None


def _paginated(db: Session, conditions: list, sort_by: SortField, sort_order: SortOrder,
               page: int, limit: int) -> dict:
    total = db.execute(
        select(func.count(Product.product_id)).where(*conditions)
    ).scalar_one()
    column = SORT_COLUMNS[sort_by]
    order = column.asc() if sort_order == SortOrder.asc else column.desc()
    rows = db.execute(
        select(Product).where(*conditions)
        .order_by(order, Product.product_id)      # tie-breaker => stable pages
        .offset((page - 1) * limit).limit(limit)
    ).scalars().all()
    return {"products": rows, "page": page, "limit": limit, "total": total}


# ---------- CRUD ----------
def create_product(db: Session, data: ProductCreate) -> Product:
    if _code_exists(db, data.product_code):
        raise DuplicateProductCodeError(f"Product code '{data.product_code}' already exists")
    values = data.model_dump()
    values["category"] = data.category.value
    product = Product(**values)
    db.add(product)
    _commit(db, "Insert", duplicate_code=data.product_code)  # also catches race conditions
    db.refresh(product)  # load DB-generated id / timestamps
    return product


def get_product(db: Session, product_id: int) -> Product:
    return _get_or_404(db, product_id)


def list_products(db: Session, *, category, is_active, min_price, max_price, in_stock,
                  sort_by, sort_order, page, limit) -> dict:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise InvalidRequestError("min_price cannot be greater than max_price")
    conditions = []
    if category is not None:
        conditions.append(Product.category == category.value)
    if is_active is not None:
        conditions.append(Product.is_active.is_(is_active))
    if min_price is not None:
        conditions.append(Product.price >= min_price)
    if max_price is not None:
        conditions.append(Product.price <= max_price)
    if in_stock is not None:
        conditions.append(Product.quantity > 0 if in_stock else Product.quantity == 0)
    return _paginated(db, conditions, sort_by, sort_order, page, limit)


def search_products(db: Session, keyword: str, sort_by, sort_order, page, limit) -> dict:
    escaped = keyword.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    fields = (Product.product_name, Product.product_code, Product.category, Product.supplier_name)
    condition = or_(*[func.lower(f).like(pattern, escape="\\") for f in fields])
    return _paginated(db, [condition], sort_by, sort_order, page, limit)


def replace_product(db: Session, product_id: int, data: ProductCreate) -> Product:
    """PUT: full replacement — every field is overwritten."""
    product = _get_or_404(db, product_id)
    if _code_exists(db, data.product_code, exclude_id=product_id):
        raise DuplicateProductCodeError(f"Product code '{data.product_code}' already exists")
    for field, value in data.model_dump().items():
        setattr(product, field, value)
    product.category = data.category.value
    _commit(db, "Update", duplicate_code=data.product_code)
    db.refresh(product)
    return product


def patch_product(db: Session, product_id: int, data: ProductUpdate) -> Product:
    """PATCH: only the fields the client actually sent are changed."""
    product = _get_or_404(db, product_id)
    changes = data.model_dump(exclude_unset=True)
    new_code = changes.get("product_code")
    if new_code and _code_exists(db, new_code, exclude_id=product_id):
        raise DuplicateProductCodeError(f"Product code '{new_code}' already exists")
    if "category" in changes:
        changes["category"] = changes["category"].value
    for field, value in changes.items():
        setattr(product, field, value)
    _commit(db, "Update", duplicate_code=new_code)
    db.refresh(product)
    return product


def soft_delete_product(db: Session, product_id: int) -> Product:
    product = _get_or_404(db, product_id)
    product.is_active = False
    _commit(db, "Delete")
    db.refresh(product)
    return product


# ---------- stock (business logic) ----------
def update_stock(db: Session, product_id: int, data: StockUpdate) -> Product:
    product = _get_or_404(db, product_id, lock=True)
    if data.operation == StockOperation.add:
        product.quantity += data.quantity
    else:
        if data.quantity > product.quantity:
            db.rollback()  # release the row lock
            raise InsufficientStockError(
                f"Cannot remove {data.quantity}: only {product.quantity} in stock")
        product.quantity -= data.quantity
    _commit(db, "Stock update")
    db.refresh(product)
    return product


# ---------- reports ----------
def get_statistics(db: Session) -> dict:
    """Everything computed in SQL with aggregates (one query)."""
    active = Product.is_active.is_(True)
    row = db.execute(select(
        func.count(Product.product_id),
        func.coalesce(func.sum(case((active, 1), else_=0)), 0),
        func.coalesce(func.sum(case((active, Product.quantity), else_=0)), 0),
        func.coalesce(func.sum(case((active, Product.price * Product.quantity), else_=0)), 0),
    )).one()
    total, active_count = int(row[0]), int(row[1])
    return {
        "total_products": total,
        "active_products": active_count,
        "inactive_products": total - active_count,
        "total_stock": int(row[2]),
        "total_inventory_value": float(row[3]),
    }


def low_stock_products(db: Session, threshold: int, active_only: bool, page: int, limit: int) -> dict:
    conditions = [Product.quantity <= threshold]
    if active_only:
        conditions.append(Product.is_active.is_(True))
    return _paginated(db, conditions, SortField.quantity, SortOrder.asc, page, limit)
