from app.database.fake_store import store


async def generate_image(user_id: str, payload: dict) -> dict:
    job = store.create_job(user_id, "image", payload)
    return {"status": "success", "jobId": job["id"], "queuePosition": job["queuePosition"], "progress": job["progress"]}


async def generate_video(user_id: str, payload: dict) -> dict:
    job = store.create_job(user_id, "video", payload)
    return {"status": "success", "jobId": job["id"], "queuePosition": job["queuePosition"], "progress": job["progress"]}
