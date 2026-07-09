async def create_upload_ticket(user_id: str, filename: str | None = None) -> dict:
    return {
        "status": "success",
        "uploadUrl": "https://example.com/upload/demo",
        "fileId": f"file_{user_id}",
        "filename": filename or "upload.bin",
    }
