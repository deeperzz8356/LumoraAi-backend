from fastapi import APIRouter
from app.services.job_service import get_job, retry_job

router = APIRouter()


@router.get("/{job_id}")
async def get_job_route(job_id: str):
    job = await get_job(job_id)
    if not job:
        return {"status": "error", "message": "Job not found"}
    return {"status": "success", "data": job}


@router.post("/{job_id}/retry")
async def retry_job_route(job_id: str):
    return await retry_job(job_id)
