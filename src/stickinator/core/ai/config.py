"""Provider configuration and the per-run AI context.

Everything here is picklable and Qt-free: the context travels to the worker
process. API keys live in the context for the length of a run and are never
written to settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from stickinator.core.params import Params

LOCAL = "local"
HTTP = "http"
OPENAI = "openai"
PROVIDERS = (LOCAL, HTTP, OPENAI)

DEFAULT_OPENAI_PROMPT = (
    "Remove the background, keep the subject unchanged, and leave a transparent background."
)


@dataclass(frozen=True, slots=True)
class LocalConfig:
    model: str = "isnet-general-use"
    alpha_matting: bool = False
    foreground_threshold: int = 240
    background_threshold: int = 10
    erode_size: int = 10
    use_coreml: bool = False
    model_dir: str = ""


@dataclass(frozen=True, slots=True)
class HttpConfig:
    url: str = ""
    field_name: str = "image"
    auth_header: str = "X-Api-Key"
    auth_format: str = "{key}"
    extra_headers: str = ""
    extra_fields: str = ""


@dataclass(frozen=True, slots=True)
class OpenAIConfig:
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-image-1"
    prompt: str = DEFAULT_OPENAI_PROMPT


@dataclass(frozen=True, slots=True)
class AiContext:
    provider: str = LOCAL
    api_key: str = ""
    timeout: float = 60.0
    local: LocalConfig = field(default_factory=LocalConfig)
    http: HttpConfig = field(default_factory=HttpConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)


@dataclass(frozen=True, slots=True)
class AiSettings(Params):
    """Flat, JSON-friendly settings edited in the Settings dialog."""

    provider: str = LOCAL
    timeout: float = 60.0

    local_model: str = "isnet-general-use"
    local_alpha_matting: bool = False
    local_foreground: int = 240
    local_background: int = 10
    local_erode: int = 10
    local_coreml: bool = False
    local_model_dir: str = ""

    http_url: str = ""
    http_field: str = "image"
    http_auth_header: str = "X-Api-Key"
    http_auth_format: str = "{key}"
    http_extra_headers: str = ""
    http_extra_fields: str = ""

    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-image-1"
    openai_prompt: str = DEFAULT_OPENAI_PROMPT

    def __post_init__(self) -> None:
        if self.provider not in PROVIDERS:
            msg = f"unknown provider: {self.provider}"
            raise ValueError(msg)
        if self.timeout <= 0:
            msg = "timeout must be positive"
            raise ValueError(msg)
        if not 0 <= self.local_foreground <= 255:
            msg = "foreground threshold must be between 0 and 255"
            raise ValueError(msg)
        if not 0 <= self.local_background <= 255:
            msg = "background threshold must be between 0 and 255"
            raise ValueError(msg)
        if self.local_erode < 0:
            msg = "erode size must not be negative"
            raise ValueError(msg)

    def to_context(self, api_key: str) -> AiContext:
        return AiContext(
            provider=self.provider,
            api_key=api_key,
            timeout=self.timeout,
            local=LocalConfig(
                model=self.local_model,
                alpha_matting=self.local_alpha_matting,
                foreground_threshold=self.local_foreground,
                background_threshold=self.local_background,
                erode_size=self.local_erode,
                use_coreml=self.local_coreml,
                model_dir=self.local_model_dir,
            ),
            http=HttpConfig(
                url=self.http_url,
                field_name=self.http_field,
                auth_header=self.http_auth_header,
                auth_format=self.http_auth_format,
                extra_headers=self.http_extra_headers,
                extra_fields=self.http_extra_fields,
            ),
            openai=OpenAIConfig(
                base_url=self.openai_base_url,
                model=self.openai_model,
                prompt=self.openai_prompt,
            ),
        )
