from pydantic import BaseModel


class TemplateItem(BaseModel):
    id: str
    name: str
    category: str


class DiscoverItem(BaseModel):
    id: str
    title: str
    type: str
