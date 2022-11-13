import os

from dotenv import load_dotenv
from fastapi import status
from fastapi.responses import JSONResponse

load_dotenv()

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

ALGORITHM = os.getenv("ALGORITHM", default="HS256")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", default="key")

POSTGRES_DB = os.getenv("POSTGRES_DB", default="postgres")
POSTGRES_USER = os.getenv("POSTGRES_USER", default="postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", default="postgres")
POSTGRES_SERVER = os.getenv("POSTGRES_SERVER", default="localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", default="5432")

TESTING = os.getenv("TESTING")
if TESTING:
    POSTGRES_SERVER = "db-test"
DATABASE_URL = (f"postgresql://{POSTGRES_USER}:"
                f"{POSTGRES_PASSWORD}@"
                f"{POSTGRES_SERVER}:"
                f"{POSTGRES_PORT}/"
                f"{POSTGRES_DB}")

STATIC_ROOT = os.path.join(os.path.dirname(__file__), "static/")
DATA_ROOT = os.path.join(os.path.dirname(__file__), "data/")

NOT_AUTHENTICATED = JSONResponse({"detail": "Not authenticated"}, status.HTTP_401_UNAUTHORIZED)
NOT_FOUND = JSONResponse({"detail": "NotFound"}, status.HTTP_404_NOT_FOUND)
