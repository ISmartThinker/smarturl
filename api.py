import asyncio
import hashlib
import logging
import re
import socket
from contextlib import asynccontextmanager
from datetime import datetime

import motor.motor_asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, field_validator, HttpUrl
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

MONGO_URI = "mongodb+srv://hakilaakaima:Forhadgandu82@cluster0.q69yjvj.mongodb.net/?retryWrites=true&w=majority&appName=TheSmartToolBot"

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client.url_shortener
collection = db.urls

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def hash_to_shortcode(url):
    return hashlib.md5(url.encode()).hexdigest()[:6].upper()

def is_valid_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False

def is_valid_slug(slug):
    return bool(re.fullmatch(r'[A-Za-z0-9_-]+', slug)) and 3 <= len(slug) <= 30

class ShortenRequest(BaseModel):
    url: HttpUrl
    slug: str = None

    @field_validator("url", mode="before")
    @classmethod
    def add_scheme(cls, v):
        if isinstance(v, str) and not v.startswith(("http://", "https://")):
            return f"https://{v}"
        return v

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        if v is not None and not is_valid_slug(v):
            raise ValueError("Invalid slug! Use only letters, numbers, hyphens, and underscores.")
        return v

async def cleanup_old_urls():
    while True:
        await asyncio.sleep(86400)
        threshold = datetime.utcnow().replace(year=datetime.utcnow().year - 1)
        await collection.delete_many({"created_at": {"$lt": threshold}})

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_old_urls())
    actual_ip = get_local_ip()
    base_url = f"http://{actual_ip}:4000"
    logger.info("SmartURLShortner Successfully Started!")
    logger.info(f"Api Base URL {base_url}")
    logger.info(f"And Other Urls {base_url}/api/short, {base_url}/api/chk, {base_url}/api/del, {base_url}/<code>")
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def home():
    actual_ip = get_local_ip()
    base_url = f"http://{actual_ip}:4000"
    return {
        "message": "SmartURLShortner API",
        "api_base": base_url,
        "endpoints": {
            "shorten": f"{base_url}/api/short?url=https://example.com&slug=custom",
            "check": f"{base_url}/api/chk?url={base_url}/ABC123",
            "delete": f"{base_url}/api/del?url={base_url}/ABC123",
            "redirect": f"{base_url}/ABC123"
        },
        "api_dev": "@ISmartCoder",
        "api_updates": "@abirxdhackz"
    }

@app.get("/api/short")
async def short_url(url: HttpUrl, slug: str = None):
    long_url = str(url)
    if not is_valid_url(long_url):
        raise HTTPException(status_code=400, detail={"error": "Invalid URL", "api_dev": "@ISmartCoder", "api_updates": "@abirxdhackz"})

    if slug:
        if not is_valid_slug(slug):
            raise HTTPException(status_code=400, detail={"error": "Invalid slug! Use only letters, numbers, hyphens, and underscores.", "api_dev": "@ISmartCoder", "api_updates": "@abirxdhackz"})
        short_code = slug
    else:
        short_code = hash_to_shortcode(long_url)

    existing = await collection.find_one({"short_code": short_code})
    if existing:
        if slug and existing["long_url"] != long_url:
            raise HTTPException(status_code=409, detail={"error": "Slug already in use", "api_dev": "@ISmartCoder", "api_updates": "@abirxdhackz"})
    else:
        await collection.insert_one({
            "short_code": short_code,
            "long_url": long_url,
            "clicks": 0,
            "created_at": datetime.utcnow(),
            "last_clicked": None
        })

    short_url = f"http://{get_local_ip()}:4000/{short_code}"
    return {
        "short_url": short_url,
        "original_url": long_url,
        "short_code": short_code,
        "api_dev": "@ISmartCoder",
        "api_updates": "@abirxdhackz"
    }

@app.get("/{short_code}")
async def redirect_short(short_code: str):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', short_code):
        raise HTTPException(status_code=404, detail={"error": "Invalid short code", "api_dev": "@ISmartCoder", "api_updates": "@abirxdhackz"})
    result = await collection.find_one_and_update(
        {"short_code": short_code},
        {"$inc": {"clicks": 1}, "$set": {"last_clicked": datetime.utcnow()}},
        return_document=True
    )
    if result:
        return RedirectResponse(url=result["long_url"], status_code=301)
    raise HTTPException(status_code=404, detail={"error": "Short URL not found", "api_dev": "@ISmartCoder", "api_updates": "@abirxdhackz"})

@app.get("/api/chk")
async def check_clicks(url: str = None):
    if not url:
        raise HTTPException(status_code=400, detail={"error": "Missing 'url'", "api_dev": "@ISmartCoder", "api_updates": "@abirxdhackz"})
    short_code = url.rstrip("/").split("/")[-1]
    if not re.fullmatch(r'[A-Za-z0-9_-]+', short_code):
        raise HTTPException(status_code=400, detail={"error": "Invalid short code", "api_dev": "@ISmartCoder", "api_updates": "@abirxdhackz"})
    doc = await collection.find_one({"short_code": short_code})
    if not doc:
        raise HTTPException(status_code=404, detail={"error": "Short URL not found", "api_dev": "@ISmartCoder", "api_updates": "@abirxdhackz"})
    last_clicked = doc["last_clicked"].strftime("%Y-%m-%d %H:%M:%S") if doc["last_clicked"] else "Never"
    return {
        "short_code": doc["short_code"],
        "original_url": doc["long_url"],
        "clicks": doc["clicks"],
        "created_at": doc["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
        "last_clicked": last_clicked,
        "api_dev": "@ISmartCoder",
        "api_updates": "@abirxdhackz"
    }

@app.get("/api/del")
async def delete_url(url: str = None):
    if not url:
        raise HTTPException(status_code=400, detail={"error": "Missing 'url'", "api_dev": "@ISmartCoder", "api_updates": "@abirxdhackz"})
    short_code = url.rstrip("/").split("/")[-1]
    if not re.fullmatch(r'[A-Za-z0-9_-]+', short_code):
        raise HTTPException(status_code=400, detail={"error": "Invalid short code", "api_dev": "@ISmartCoder", "api_updates": "@abirxdhackz"})
    result = await collection.delete_one({"short_code": short_code})
    if result.deleted_count:
        return {"status": "deleted", "short_code": short_code, "api_dev": "@ISmartCoder", "api_updates": "@abirxdhackz"}
    raise HTTPException(status_code=404, detail={"error": "Short URL not found", "api_dev": "@ISmartCoder", "api_updates": "@abirxdhackz"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=4000, log_level="info")