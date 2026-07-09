from fastapi import APIRouter
from app.services.catalog_service import get_templates

router = APIRouter()


@router.get("")
async def templates_route():
    return {"status": "success", "items": await get_templates()}
