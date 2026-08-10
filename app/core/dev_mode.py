def is_developer_mode_header(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}
