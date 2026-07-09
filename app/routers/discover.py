from fastapi import APIRouter
from app.services.catalog_service import get_discover_items

router = APIRouter()


@router.get("")
async def discover_route():
    return {"status": "success", "items": await get_discover_items()}
