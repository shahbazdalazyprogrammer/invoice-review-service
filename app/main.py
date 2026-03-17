import logging
import app.models
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from app.db import Base, engine
from app.api.routes_reviews import router as reviews_router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Used to replace the deprecated on_event("startup").
    1. Creates DB tables when the app starts.
    2. Only runs against the REAL engine tests
    3. Manage their own tables via conftest.py.
    """
    logger.info("Starting up... creating database tables if they don't exist.")
    Base.metadata.create_all(bind=engine)
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="Invoice Review Service",
    description="Rule-based invoice review: returns PASS, FAIL, or NEEDS_INFO.",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve frontend
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serves the frontend UI at the root URL."""
    return FileResponse("app/static/index.html")

app.include_router(reviews_router)