# Output models

Import domain types from `prydwen.games.endfield.models`. Shared provenance and identity models live in `prydwen.core.models` and the most useful shared models are also re-exported with Endfield types.

## Shared provenance

Collection results carry `.source` (URL, precise fetch time, optional source update date, source hash, parser version, extraction mode), `.diagnostics`, and runtime `.delivery` (`from_cache`, `read_at`). Delivery is excluded from serialized payloads. A cache hit preserves the original fetch time.

Model fields cannot be reassigned. Lists are normal Python lists for ergonomic use; modifying a returned collection does not alter the persistent cache or later calls. Unknown optional fields are None. Public model validation rejects unexpected field names.

## Identity and characters

`Identifier` has `name` and `identifier`.

`Character` has identifier, name, actual page URL, optional source ID/unit ID, rarity, element, operator class, weapon type, assets, synergy tags, upcoming/new flags, and supplementary source tier ratings. Source IDs are opaque Prydwen values, not assumed official game IDs.

`AllCharacters.characters` contains these summaries and `.total_count` returns their count. Character detail-page content is not represented by fabricated zero stats.

## Character guides

`CharacterBuild` is a single-character dataset with `.character`, `.detailed`, `.availability`, `.updates`, `.review`, `.weapons`, `.gear_sets`, `.gear_pieces`, `.potentials`, `.skill_priority`, `.synergies`, `.teams`, `.calculations`, and `.notes`. Both detailed and concise outputs keep the same structured records. Only descriptive prose is shortened in concise mode; see [character builds](../guides/character-builds.md).

- `CharacterReview` contains per-role `BuildRating` records, pros, cons, and ordered review content. Ratings preserve source tiers such as `T0` and mode labels.
- `GuideBlock` contains typed content, text, highlights, list items/children, table rows, links, media, and optional team-local rotation references. Highlighted phrases, media, links, and record order remain available in both modes.
- `EquipmentRef` provides source identity, name, type, optional stats/passive, and assets. `WeaponRecommendation` and `GearRecommendation` attach ranks, explanations, potential/archetype, loadouts, and grouped alternatives. `GearPieceComparison` retains baseline rows and disclaimer markers. `BuildPerformance` stores Decimal comparative percentages with a baseline of 100.
- `PotentialRecommendation` records upgrade names, explanations, and optional cumulative comparisons. `SkillPriority` preserves the exact expression, skills, and operators. `CharacterSynergy` includes partner identity and explanation.
- `BuildTeam` keeps `.members`, `.displayed_members`, `.owner_implicit`, ordered `.guide`, and `.rotations`. `TeamRotation` represents either timed `TimelineRow`/`TimelineAction` lanes or ordered `RotationStep` instructions. Timed values use Decimal seconds, with action spans describing the displayed block geometry.
- `BuildCalculations` contains equipment setups, notes, and optional `DamageDistribution` pies. Each `DamageContribution` preserves its source label and Decimal percentage, including zeros. Chart totals retain published rounding without normalization.
- `SectionAvailability` distinguishes available, pending, and unavailable sections with their source messages. `BuildUpdates` keeps independent source patch labels for review, build, and teams.

## Equipment and stats

`Gear` has identifier, source ID, name, slot, displayed level, defense, stats, optional set identifier, and assets. `GearSet` adds name, source code, bonuses, pieces, and piece count. Setless gear remains setless. `Weapon` contains type, rarity, displayed base attack, stat boosts, passive text/rank, and assets; it is currently an internal catalog output used by the list method.

`StatValue` retains key, label, Decimal value, explicit unit, raw value, optional reference property ID, target, precision, and computed display. `StatBoost` attaches a displayed slot/rank. `BoostRank` is current/maximum. These values are guide data, not computed combat stats.

## Banner models

`AllBanners.banners` contains `Banner` records with local identifier, name, type, declared section, patch/kind, description, art, featured links, icon chips, and regional schedules. All actual source regions remain available even after filtering one region.

`BannerSchedule` keeps raw/parsed start and end values, `end_unannounced`, and `is_valid`. Its `.status(at)` returns `current`, `upcoming`, `ended`, or `unknown` for an explicit aware timestamp. Contradictory dates remain visible and invalid.

## Code models

`RedeemCodes.codes` contains `RedeemCode` records with exact code text, source identity, optional dates/timezone, listed state, manual-expiry flag, rewards, and legacy reward text. `RewardItem` has name, quantity, optional source ID, and icon.

`RedeemCode.is_active(at)` handles known expiry and source state. Cached catalogs retain visible expired codes internally; the public operation returns its active subset.

## Tier and team models

`TierList.tiers` contains rows with normalized/raw tier labels and `.roles`. Each role has a label and `.placements`; each placement includes a character reference, form, tags, new/movement/watchlist flags. One character may have more than one placement. Empty role buckets and rows are retained.

`TeamTierList.tiers` contains rows with `.teams`. Each team has a local identifier, title, source archetype, background link, `.core` candidates, and ordered `.slots`. Each slot contains `.candidates`, a position, and an optional role label. Alternatives are not expanded into all possible combinations.

Both tier lists include `.context` with editorial assumptions and source text. Team character references provide actual character URLs and icons without implicitly fetching character details.
