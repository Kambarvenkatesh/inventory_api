from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import models  # noqa: F401  (registers the table on Base)
from database.connection import Base, create_database_if_missing, engine
from exceptions.handlers import register_exception_handlers
from routes import product


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_database_if_missing()
    Base.metadata.create_all(bind=engine)   # creates `products` if it doesn't exist
    yield


app = FastAPI(title="Product Inventory Management API", version="1.0.0", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(product.router)


@app.get("/", tags=["Health"])
def root():
    return {"message": "Inventory API is running", "docs": "/docs"}
