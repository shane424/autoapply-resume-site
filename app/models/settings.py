from pydantic import BaseModel
from typing import Optional


class LLMConfig(BaseModel):
    provider: str = "claude"
    claude_model: str = "claude-haiku-4-5-20251001"
    ollama_model: str = "llama3.2"
    ollama_base_url: str = "http://localhost:11434"


class FilterConfig(BaseModel):
    keywords: list[str] = []
    roles: list[str] = []
    exclude_keywords: list[str] = []
    remote_only: bool = True


class ApplyConfig(BaseModel):
    default_mode: str = "semiauto"


class UserProfile(BaseModel):
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    website: str = ""
    cover_letter_template: str = ""


class AppSettings(BaseModel):
    llm: LLMConfig = LLMConfig()
    filters: FilterConfig = FilterConfig()
    apply: ApplyConfig = ApplyConfig()
    user_profile: UserProfile = UserProfile()
