"""Parse banner groups and regional source timers."""

import hashlib
from collections import Counter
from typing import cast

from pydantic import HttpUrl

from prydwen.core.models import Diagnostic
from prydwen.exceptions import UpstreamSchemaError
from prydwen.parsing.assets import absolute_url, image
from prydwen.parsing.document import Document, attr, require, text
from prydwen.parsing.text import aware_time

from ..models.banners import AllBanners, Banner, BannerChip, BannerSchedule, FeaturedEntity, Region


def parse_banners(document: Document) -> AllBanners:
    """Extract declared banner sections and preserve invalid chronological values."""
    nodes = document.root(".article-layout").select(".banner-card")
    if not nodes:
        raise UpstreamSchemaError("No banner cards found")
    banners = []
    ordinals: Counter[str] = Counter()
    for node in nodes:
        name = text(require(node, ".banner-name"))
        timer = require(node, ".art-timer")
        schedules = []
        for region in ("asia", "eu", "na"):
            raw_start = attr(timer, f"data-start-{region}") or None
            raw_end = attr(timer, f"data-end-{region}") or None
            start, end = aware_time(raw_start), aware_time(raw_end)
            valid = not ((raw_start and start is None) or (raw_end and end is None))
            if start is not None and end is not None and end <= start:
                valid = False
            schedules.append(
                BannerSchedule(
                    region=cast(Region, region),
                    raw_start=raw_start,
                    raw_end=raw_end,
                    starts_at=start,
                    ends_at=end,
                    is_valid=bool(valid),
                    end_unannounced=attr(timer, f"data-unann-{region}") == "true",
                )
            )
        art = image(node.select_one(".banner-art img"), document.url)
        fingerprint = repr(
            (
                attr(node, "data-category"),
                str(art.url) if art else name,
                [(schedule.raw_start, schedule.raw_end) for schedule in schedules],
            )
        )
        key = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
        ordinals[key] += 1
        identifier = f"banner-{key}-{ordinals[key]}"
        for schedule in schedules:
            if not schedule.is_valid:
                document.diagnostics.append(
                    Diagnostic(
                        code="invalid_banner_schedule",
                        record_key=identifier,
                        field_path=f"schedules.{schedule.region}",
                        message=f"{name}: start={schedule.raw_start!r}, end={schedule.raw_end!r}",
                    )
                )
        featured = []
        for anchor in node.select("a.featured-rate-up"):
            url = absolute_url(attr(anchor, "href"), document.url)
            if url:
                featured.append(FeaturedEntity(name=text(anchor), url=HttpUrl(url)))
        banners.append(
            Banner(
                identifier=identifier,
                name=name,
                banner_type=attr(node, "data-category") or "unknown",
                section=attr(node, "data-section") or "unknown",
                patch=text(node.select_one(".banner-phase-meta > span")) or None,
                banner_kind=text(node.select_one(".banner-type")) or None,
                description=text(node.select_one(".banner-copy")),
                art=art,
                featured=featured,
                chips=[
                    BannerChip(
                        label=text(chip),
                        description=attr(chip, "title"),
                        icon=image(chip.select_one("img"), document.url),
                    )
                    for chip in node.select(".icon-chip")
                ],
                schedules=schedules,
            )
        )
    return AllBanners(source=document.source(), diagnostics=document.diagnostics, banners=banners)
