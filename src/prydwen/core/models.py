"""Shared validated output types and source provenance."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl


class Model(BaseModel):
    """A typed output whose fields cannot be reassigned accidentally."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Identifier(Model):
    """A display name and the identifier accepted by resource lookups."""

    name: str
    identifier: str


class AssetLink(Model):
    """An image URL observed in the source HTML."""

    url: HttpUrl
    alt: str | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)


class EntityAssets(Model):
    """Known image variants without speculative URL construction."""

    icon: AssetLink | None = None
    card: AssetLink | None = None
    portrait: AssetLink | None = None
    background: AssetLink | None = None
    additional: list[AssetLink] = Field(default_factory=list)


class Diagnostic(Model):
    """A recoverable source issue attached to a parsed dataset."""

    code: str
    message: str
    record_key: str | None = None
    field_path: str | None = None


class SourceInfo(Model):
    """The upstream document that established a dataset."""

    url: HttpUrl
    fetched_at: AwareDatetime
    updated_on: date | None = None
    content_sha256: str
    parser_version: int = 1
    extraction: Literal["dom", "dom+embedded"] = "dom"


class DeliveryInfo(Model):
    """How this call obtained its data; excluded from persistent payloads."""

    from_cache: bool
    read_at: AwareDatetime


class Dataset(Model):
    """Source and diagnostics common to all resource collections."""

    source: SourceInfo
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    delivery: DeliveryInfo | None = Field(default=None, exclude=True)
