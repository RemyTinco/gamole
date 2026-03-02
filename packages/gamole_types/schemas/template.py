"""Template schemas - ported from packages/types/src/schemas/template.ts."""

from pydantic import BaseModel


class TemplateSection(BaseModel):
    heading: str
    placeholder: str


class Template(BaseModel):
    name: str
    description: str | None = None
    required_headings: list[str]
    default_sections: list[TemplateSection]
    custom_field_mappings: dict[str, str] | None = None
