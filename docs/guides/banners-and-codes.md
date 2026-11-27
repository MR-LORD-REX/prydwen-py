# Banners and codes

All three banner operations use the same cached page. `banner_type` is `"character"`, `"weapon"`, or `"both"` (default).

```python
async with Prydwen.Endfield() as endfield:
    all_banners = await endfield.banners()
    current = await endfield.current_banners("character", region="asia")
    upcoming = await endfield.upcoming_banners("weapon", region="eu")
```

`banners()` includes every source section. `current_banners()` uses the declared current group and excludes schedules reliably ended or not yet started for the chosen region. `upcoming_banners()` includes scheduled-next and teased groups, excluding reliably started or ended schedules. Unknown or invalid schedules retain their declared group and remain inspectable.

Source grouping and time-derived status are different. Schedule models retain raw strings, parsed timezone-aware datetimes, unannounced-end flags, and validity. No month or year is silently corrected. In the November 27, 2026 snapshot, several source end dates precede their start dates; those produce `invalid_banner_schedule` diagnostics.

```python
from datetime import datetime, timezone

async with Prydwen.Endfield() as endfield:
    result = await endfield.banners()
    for banner in result.banners:
        for schedule in banner.schedules:
            print(banner.name, schedule.region, schedule.status(datetime.now(timezone.utc)))
```

Naive evaluation timestamps raise `ValueError`. Local banner identifiers are not official game IDs. Multiple unnamed teaser cards remain distinct.

## Redeem codes

```python
async with Prydwen.Endfield() as endfield:
    result = await endfield.redeem_codes()
    for code in result.codes:
        print(code.code, code.expires_at)
        for reward in code.rewards:
            print(reward.name, reward.quantity, reward.icon)
```

The endpoint is `/arknights-endfield/codes`. Hidden records are excluded. Manual expiry and known expiry timestamps override an old active listing. Expiry is evaluated on every read, including cache hits. Unknown expiry remains `None`; listed active does not guarantee that the game's redemption service will accept a code.

Read-time checks cannot discover new codes, a changed schedule, or a newly invalidated code without known expiry. Use `force_new=True` when you need an updated source snapshot.
