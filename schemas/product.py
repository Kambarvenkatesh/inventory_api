from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Category(str, Enum):
    electronics = "Electronics"
    furniture = "Furniture"
    clothing = "Clothing"
    grocery = "Grocery"
    stationery = "Stationery"
    appliances = "Appliances"
    accessories = "Accessories"
    other = "Other"


class SortField(str, Enum):
    product_name = "product_name"
    price = "price"
    quantity = "quantity"
    created_at = "created_at"


class SortOrder(str, Enum):
    asc = "asc"
    desc = "desc"


class StockOperation(str, Enum):
    add = "add"
    remove = "remove"


class ProductCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    product_code: str = Field(..., min_length=1, max_length=50, examples=["LAP-001"])
    product_name: str = Field(..., min_length=1, max_length=150, examples=["Laptop"])
    description: Optional[str] = Field(None, examples=["Business laptop"])
    category: Category
    price: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2, examples=[65000])
    quantity: int = Field(..., ge=0, examples=[10])
    supplier_name: str = Field(..., min_length=1, max_length=150, examples=["ABC Technologies"])
    is_active: bool = True


class ProductUpdate(BaseModel):
    """PATCH body: every field optional; only sent fields are changed."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    product_code: Optional[str] = Field(None, min_length=1, max_length=50)
    product_name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = None
    category: Optional[Category] = None
    price: Optional[Decimal] = Field(None, gt=0, max_digits=12, decimal_places=2)
    quantity: Optional[int] = Field(None, ge=0)
    supplier_name: Optional[str] = Field(None, min_length=1, max_length=150)
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def no_null_for_required_fields(self):
        required = {"product_code", "product_name", "category", "price",
                    "quantity", "supplier_name", "is_active"}
        for name in self.model_fields_set & required:
            if getattr(self, name) is None:
                raise ValueError(f"'{name}' cannot be null")
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class StockUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: int = Field(..., gt=0, examples=[20])
    operation: StockOperation


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_code: str
    product_name: str
    description: Optional[str]
    category: str
    price: float
    quantity: int
    supplier_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    products: List[ProductResponse]
    page: int
    limit: int
    total: int


class StatisticsResponse(BaseModel):
    total_products: int
    active_products: int
    inactive_products: int
    total_stock: int
    total_inventory_value: float


class MessageResponse(BaseModel):
    message: str
    product: ProductResponse
