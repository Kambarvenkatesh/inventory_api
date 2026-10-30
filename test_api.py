"""Smoke test: runs every endpoint + 10 error scenarios. Usage: python test_api.py"""
from fastapi.testclient import TestClient
from main import app

def show(title, r, expect):
    ok = "PASS" if r.status_code == expect else "FAIL"
    print(f"[{ok}] {title:<45} -> {r.status_code} (expected {expect})")
    return r

BASE = {"product_code": "LAP-001", "product_name": "Laptop", "description": "Business laptop",
        "category": "Electronics", "price": 65000, "quantity": 10, "supplier_name": "ABC Technologies"}

with TestClient(app) as c:
    print("== SUCCESS TESTS ==")
    r = show("Create LAP-001", c.post("/products", json=BASE), 201); pid = r.json()["product_id"]
    show("Create MOU-001", c.post("/products", json={**BASE, "product_code": "MOU-001", "product_name": "Wireless Mouse",
         "category": "Accessories", "price": 800, "quantity": 5, "supplier_name": "XYZ Suppliers"}), 201)
    show("Create CHR-001", c.post("/products", json={**BASE, "product_code": "CHR-001", "product_name": "Office Chair",
         "category": "Furniture", "price": 7500, "quantity": 30, "supplier_name": "Comfort Co"}), 201)
    r = show("Get all (page=1&limit=2)", c.get("/products?page=1&limit=2"), 200); print("   total =", r.json()["total"], "returned =", len(r.json()["products"]))
    r = show("Filter combo", c.get("/products?category=Electronics&is_active=true&min_price=10000&max_price=80000&in_stock=true"), 200); print("   total =", r.json()["total"])
    r = show("Sort price asc", c.get("/products?sort_by=price&sort_order=asc"), 200); print("   prices =", [p["price"] for p in r.json()["products"]])
    r = show("Search 'laptop' (case-insens.)", c.get("/products/search?keyword=LaPtOp"), 200); print("   total =", r.json()["total"])
    r = show("Search by supplier 'xyz'", c.get("/products/search?keyword=xyz"), 200); print("   total =", r.json()["total"])
    show("Get by id", c.get(f"/products/{pid}"), 200)
    show("PUT full update", c.put(f"/products/{pid}", json={**BASE, "price": 64000}), 200)
    r = show("PATCH price only", c.patch(f"/products/{pid}", json={"price": 62000}), 200); print("   price =", r.json()["price"], "| supplier unchanged =", r.json()["supplier_name"])
    r = show("PATCH supplier+quantity", c.patch(f"/products/{pid}", json={"supplier_name": "XYZ Suppliers", "quantity": 25}), 200)
    r = show("Stock add 20", c.patch(f"/products/{pid}/stock", json={"quantity": 20, "operation": "add"}), 200); print("   quantity =", r.json()["quantity"])
    r = show("Stock remove 20", c.patch(f"/products/{pid}/stock", json={"quantity": 20, "operation": "remove"}), 200); print("   quantity =", r.json()["quantity"])
    r = show("Statistics", c.get("/products/statistics"), 200); print("  ", r.json())
    r = show("Low stock threshold=10", c.get("/products/low-stock?threshold=10"), 200); print("   ", [(p["product_code"], p["quantity"]) for p in r.json()["products"]])
    r = show("Soft delete", c.delete(f"/products/{pid}"), 200); print("   is_active =", r.json()["product"]["is_active"])
    show("Still retrievable after delete", c.get(f"/products/{pid}"), 200)

    print("\n== ERROR TESTS ==")
    r = show("1. Duplicate product code", c.post("/products", json=BASE), 409); print("  ", r.json())
    r = show("2. Product not found", c.get("/products/99999"), 404); print("  ", r.json())
    show("3. Negative price", c.post("/products", json={**BASE, "product_code": "X1", "price": -5}), 422)
    show("4. Negative quantity", c.post("/products", json={**BASE, "product_code": "X2", "quantity": -1}), 422)
    show("5. Invalid page (0)", c.get("/products?page=0"), 422)
    show("6. Invalid limit (1000)", c.get("/products?limit=1000"), 422)
    r = show("7. Invalid sort field (password)", c.get("/products?sort_by=password"), 422); print("  ", r.json())
    show("8. Invalid sort order", c.get("/products?sort_order=sideways"), 422)
    mid = c.get("/products/search?keyword=mouse").json()["products"][0]["product_id"]
    r = show("9. Remove more stock than available", c.patch(f"/products/{mid}/stock", json={"quantity": 999, "operation": "remove"}), 400); print("  ", r.json())
    show("10. Invalid stock operation", c.patch(f"/products/{mid}/stock", json={"quantity": 5, "operation": "steal"}), 422)
    show("11. Invalid category", c.post("/products", json={**BASE, "product_code": "X3", "category": "Weapons"}), 422)
    show("12. Invalid product id (0 / abc)", c.get("/products/abc"), 422)
    show("13. PATCH duplicate code", c.patch(f"/products/{mid}", json={"product_code": "LAP-001"}), 409)
    show("14. min_price > max_price", c.get("/products?min_price=500&max_price=100"), 400)
    show("15. PATCH empty body", c.patch(f"/products/{mid}", json={}), 422)
