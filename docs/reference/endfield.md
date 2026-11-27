# Endfield methods

All methods are asynchronous and require an active `async with Prydwen.Endfield()` context. `force_new` is keyword-only, defaults to False, and bypasses the selected resource cache. Failed forced refreshes raise an error while preserving the previous valid cache.

## Identity lists

```python
await endfield.list_characters(*, force_new=False) -> list[Identifier]
await endfield.list_weapons(*, force_new=False) -> list[Identifier]
await endfield.list_gears(*, force_new=False) -> list[Identifier]
await endfield.list_gear_sets(*, force_new=False) -> list[Identifier]
```

Each entry has `.name` and `.identifier`. Source order is retained. Gear and gear-set lists share the gear page; character and weapon lists use their respective catalogs. Upcoming characters remain in the character list. Gear names can repeat while identifiers remain distinct.

## Characters

```python
await endfield.characters(*, force_new=False) -> AllCharacters
```

The result contains `.characters`, `.total_count`, `.source`, `.diagnostics`, and `.delivery`. Each character supplies general index metadata and assets. Detailed skills, builds, and character-specific methods are not implemented yet.

## Gear and sets

```python
await endfield.gear(identifier: str, *, force_new=False) -> Gear
await endfield.gear_set(identifier: str, *, force_new=False) -> GearSet
```

Use an exact identifier from the matching list method. `gear()` returns the selected piece. `gear_set()` returns set metadata, `.bonuses`, `.gears`, and `.total_count`. Both look up the shared complete catalog, so switching identifiers does not cause separate page requests. A missing identifier raises `NotFoundError`; empty/invalid identifier input raises `ValueError`.

## Banners

```python
await endfield.banners(banner_type="both", *, force_new=False) -> AllBanners
await endfield.current_banners(banner_type="both", *, region="asia", force_new=False) -> AllBanners
await endfield.upcoming_banners(banner_type="both", *, region="asia", force_new=False) -> AllBanners
```

`banner_type` accepts `"character"`, `"weapon"`, or `"both"`. `region` accepts `"asia"`, `"eu"`, or `"na"`. Unsupported values raise `ValueError` before requesting the resource.

`banners()` returns every source group. Current/upcoming methods combine declared grouping with reliable read-time schedule checks. Upcoming includes teased entries. Unknown/contradictory schedules retain their declared grouping with diagnostics. See [timing semantics](../guides/banners-and-codes.md).

## Codes

```python
await endfield.redeem_codes(*, force_new=False) -> RedeemCodes
```

Returns `.codes` with source-listed active records, reward items, and optional expiry. Hidden/manual-expired records are excluded, and elapsed known expiry is re-evaluated on every call. Unknown expiry does not guarantee redeemability.

## Tier lists

```python
await endfield.tier_list(*, force_new=False) -> TierList
await endfield.team_tier_list(*, force_new=False) -> TeamTierList
```

Character tiers preserve source role buckets, repeated character/form placements, tags, and empty tiers. Team tiers preserve the primary/core character and each ordered teammate slot's alternatives. A team slot's role is None unless the team source explicitly provides one; character-class or editorial-role data is not inferred from its position.

Every collection's `.total_count` describes that collection's meaning: characters, banners, codes, placements, or compositions. The collection field names remain domain-specific (`.characters`, `.banners`, `.codes`, `.tiers`).
