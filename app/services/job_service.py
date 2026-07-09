from app.database.fake_store import store


async def get_job(job_id: str) -> dict | None:
    return store.jobs.get(job_id)


async def retry_job(job_id: str) -> dict:
    job = store.jobs.get(job_id)
    if not job:
        return {"status": "error", "message": "Job not found"}
    job["status"] = "success"
    job["progress"] = 100
    return {"status": "success", "jobId": job_id, "queuePosition": 1, "progress": 100}
