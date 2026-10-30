# Product Inventory Management API

FastAPI + SQLAlchemy 2.0 + MySQL. All data is persisted in MySQL (`inventory_db.products`).

## Project structure
```
inventory_api/
├── main.py                  # app, lifespan (creates DB/table), router + handler registration
├── database/
│   ├── connection.py        # DATABASE_URL, engine, SessionLocal, Base, get_db()
│   └── models.py            # SQLAlchemy Product model (table definition)
├── schemas/product.py       # Pydantic: ProductCreate / ProductUpdate / ProductResponse / ...
├── routes/product.py        # HTTP layer only (Depends(get_db) -> service)
├── services/product.py      # business logic + queries + commit/rollback/refresh
├── exceptions/handlers.py   # custom exceptions + global handlers
├── schema.sql               # manual SQL script (database + table)
├── test_api.py              # runs all endpoints + 15 error scenarios
├── requirements.txt / .env.example / README.md
```

## Setup
```bash
python -m venv venv
venv\Scripts\activate            # Windows   (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # then put your MySQL password in DATABASE_URL
uvicorn main:app --reload
```
Open **http://127.0.0.1:8000/docs** (Swagger UI).

`DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/inventory_db`

On startup the app creates `inventory_db` and the `products` table if missing.
Or run `schema.sql` manually in MySQL Workbench / CLI: `mysql -u root -p < schema.sql`.
If your password has special characters (`@`, `#`...), URL-encode them (`@` -> `%40`).

Run the test script (server does not need to be running): `python test_api.py`

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | /products | Create (409 on duplicate code) |
| GET | /products | List: page, limit, category, is_active, min_price, max_price, in_stock, sort_by, sort_order |
| GET | /products/search?keyword= | Case-insensitive search in name, code, category, supplier |
| GET | /products/statistics | SQL aggregates |
| GET | /products/low-stock?threshold= | quantity <= threshold (paginated) |
| GET | /products/{id} | One product (404) |
| PUT | /products/{id} | Full replacement |
| PATCH | /products/{id} | Partial update |
| PATCH | /products/{id}/stock | `{"quantity":20,"operation":"add"|"remove"}` |
| DELETE | /products/{id} | Soft delete (`is_active=false`) |

## Database structure (`products`)
| Column | Type | Constraint | Why |
|---|---|---|---|
| product_id | INT | PK, AUTO_INCREMENT | unique row identity |
| product_code | VARCHAR(50) | UNIQUE, NOT NULL | business key; unique index also blocks duplicates under race conditions |
| product_name | VARCHAR(150) | NOT NULL | required, indexed for sort/search |
| description | TEXT | NULL | optional long text |
| category | VARCHAR(100) | NOT NULL, indexed | filtered often |
| price | DECIMAL(12,2) | NOT NULL, CHECK > 0 | exact money arithmetic (FLOAT gives rounding errors) |
| quantity | INT | NOT NULL, DEFAULT 0, CHECK >= 0 | DB-level guard against negative stock |
| supplier_name | VARCHAR(150) | NOT NULL | |
| is_active | BOOLEAN | NOT NULL, DEFAULT 1 | soft-delete flag |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | automatic |
| updated_at | DATETIME | ON UPDATE CURRENT_TIMESTAMP | automatic |

(CHECK constraints are enforced on MySQL 8.0.16+.)

## Architecture
```
Client -> Route -> Pydantic validation -> Service -> SQLAlchemy Session -> MySQL -> Response schema -> Client
```
* **Route**: receives request, declares params, calls service. No SQL, no business rules.
* **Schema (Pydantic)**: validates input (price > 0, enums, page >= 1) and shapes output. Bad input never reaches the DB.
* **Service**: business rules (duplicate code, stock can't go negative), queries, `commit()` / `rollback()` / `refresh()`.
* **SQLAlchemy model vs Pydantic schema**: the model maps to the *table* (storage); the schema describes the *API contract* (what clients send/receive). They are separate so DB internals aren't leaked and validation is independent of storage.
* **Session**: `get_db()` opens one session per request and always closes it (`Depends(get_db)`).
* **Transactions**: success -> `commit()`; any DB error -> `rollback()` so the session isn't left broken; `refresh()` reloads DB-generated values (id, timestamps). Stock updates use `SELECT ... FOR UPDATE` so two simultaneous requests can't corrupt quantity.

## Concept notes
* **Filtering vs searching**: filtering narrows by exact conditions on specific fields (category, price range); searching does fuzzy keyword matching across several text fields.
* **PUT vs PATCH**: PUT replaces the entire resource (all required fields needed); PATCH changes only the fields sent (`exclude_unset=True`).
* **Soft delete**: keeps history/audit trail, avoids breaking future references (orders, invoices), and allows recovery.
* **sort_by safety**: `sort_by` is an Enum; anything else -> 422. Never build `ORDER BY` from raw user text.
* **Statistics** use one SQL aggregate query (COUNT/SUM/CASE); stock and inventory value count **active** products only.
* **Low-stock** returns active products by default; pass `active_only=false` to include inactive.

## Error responses
```json
{"error": "DuplicateProductCode", "message": "Product code 'LAP-001' already exists"}
```
| Status | When |
|---|---|
| 400 | not enough stock, min_price > max_price |
| 404 | product not found |
| 409 | duplicate product code |
| 422 | validation: price/quantity, category, page/limit, sort field/order, stock operation, invalid id |
| 500 | insert/update/delete failure (after rollback) |
| 503 | database connection failure |
