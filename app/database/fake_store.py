from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4



def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FakeStore:
    users: dict[str, dict] = field(default_factory=dict)
    jobs: dict[str, dict] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    templates: list[dict] = field(default_factory=list)
    discover_items: list[dict] = field(default_factory=list)
    notifications: list[dict] = field(default_factory=list)
    credits: dict[str, int] = field(default_factory=dict)
    profiles: dict[str, dict] = field(default_factory=dict)
    settings: dict[str, dict] = field(default_factory=dict)

    def seed(self) -> None:
        if self.templates:
            return

        self.templates.extend([
            {"id": "tpl_001", "name": "Cinematic Portrait", "category": "image"},
            {"id": "tpl_002", "name": "Product Reveal", "category": "video"},
            {"id": "tpl_003", "name": "Social Reel", "category": "video"},
        ])
        self.discover_items.extend([
            {"id": "dsc_001", "title": "Trending Neon Style", "type": "image"},
            {"id": "dsc_002", "title": "Short Motion Promo", "type": "video"},
        ])
        self.notifications.extend([
            {"id": "ntf_001", "title": "Welcome to Lumora AI", "body": "Your demo backend is ready."},
            {"id": "ntf_002", "title": "Credits updated", "body": "You received starter credits."},
        ])

    def ensure_user(self, user_id: str) -> None:
        self.seed()
        if user_id not in self.users:
            self.users[user_id] = {
                "id": user_id,
                "email": f"{user_id}@demo.local",
                "displayName": "Demo Creator",
                "createdAt": now_iso(),
            }
            self.credits[user_id] = 10
            self.profiles[user_id] = {
                "id": user_id,
                "displayName": "Demo Creator",
                "bio": "Lumora AI demo profile",
                "credits": 10,
            }

    def create_job(self, user_id: str, job_type: str, payload: dict, *, result_url: str | None = None) -> dict:
        self.ensure_user(user_id)
        job_id = f"job_demo_{uuid4().hex[:8]}"
        job = {
            "id": job_id,
            "userId": user_id,
            "type": job_type,
            "status": "success",
            "queuePosition": 1,
            "progress": 100,
            "resultUrl": result_url or f"https://example.com/{job_id}.mp4",
            "payload": payload,
            "createdAt": now_iso(),
        }
        self.jobs[job_id] = job
        self.history.insert(0, {
            "id": f"hist_{job_id}",
            "jobId": job_id,
            "title": payload.get("prompt", "Generated item"),
            "status": "completed",
            "createdAt": job["createdAt"],
            "userId": user_id,
        })
        self.notifications.insert(0, {
            "id": f"ntf_{job_id}",
            "title": "Generation complete",
            "body": f"Job {job_id} finished successfully.",
        })
        return job


store = FakeStore()
