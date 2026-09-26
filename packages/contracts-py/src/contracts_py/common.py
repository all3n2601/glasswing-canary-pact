from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

SCHEMA_VERSION = "2.1.0"
SchemaVersion = Literal["2.1.0"]

ID_PATTERN = r"^[a-z][a-z0-9_]*$"
ID = Annotated[str, StringConstraints(pattern=ID_PATTERN, max_length=80)]
USD = int
Ratio = Annotated[float, Field(ge=0, le=1)]
Severity = Annotated[int, Field(ge=1, le=5)]
Day = Annotated[int, Field(ge=0)]


def prefixed(*prefixes: str) -> Any:
    alternatives = "|".join(prefixes)
    return Annotated[str, StringConstraints(pattern=rf"^(?:{alternatives})[a-z0-9_]*$", max_length=80)]


RoleID = prefixed("role_")


def max_words(limit: int) -> AfterValidator:
    def check(text: str) -> str:
        if len(text.split()) > limit:
            raise ValueError(f"must be at most {limit} words")
        return text

    return AfterValidator(check)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
