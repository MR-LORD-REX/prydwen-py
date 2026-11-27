# Character builds for renderers

`character_build()` retrieves the Review, Build, and Best Teams content from one character page. It does not fetch each teammate's guide or download images.

```python
from prydwen import Prydwen


async def show_build():
    async with Prydwen.Endfield() as endfield:
        identities = await endfield.list_characters()
        print(identities[0].identifier)

        full = await endfield.character_build("si")
        concise = await endfield.character_build("si", detailed=False)

        print(full.character.name, full.character.assets.icon)
        for rating in concise.review.ratings:
            print(rating.role, rating.tier, rating.mode)
        for option in concise.weapons:
            print(option.rank, option.weapon.name, option.potential)
            print(option.performance.solo_percent, option.performance.team_percent)

        assert concise.calculations.charts == full.calculations.charts
        assert concise.teams[0].rotations == full.teams[0].rotations
```

## Full and concise output

The default `detailed=True` retains all parsed prose. `detailed=False` shortens long paragraph, callout, list-item, pros, and cons text using sentences from the source. It favors emphasized phrases, conditions, and recommendations. Short passages and single-sentence passages can remain unchanged. It uses no external summarization service.

Both modes contain the same records, in the same order: every rating, weapon, potential, gear piece, set, replacement group, comparison, skill priority, synergy, team, chart, and rotation. Numeric values, mechanics, names, headings, table cells, asset URLs, links, and rotation actions are unchanged. `GuideBlock.highlights` always retains the complete emphasized phrases, even when the surrounding explanation is shortened. Render those highlights alongside concise text when they are needed for the card.

The parser keeps prose as ordered `GuideBlock` records rather than executable HTML. Each block identifies a paragraph, heading, list, table, callout, image, video, or rotation reference. Links, list children, media thumbnails, and video URLs remain available. A rotation block's `rotation_index` addresses its containing team's `.rotations` list. Both modes preserve the guide's block and item counts.

## Equipment and comparison values

`.weapons` retains source order, numeric rank, potential, archetype, solo/team performance, and explanations. A weapon can appear more than once at different potentials or in different archetypes.

`.gear_sets` includes the recommended pieces and grouped replacements. Pieces are lists so two kit slots remain separate. A setless loadout has a name such as `"No Set"` and `gear_set=None`; its pieces are still present. Keep each alternative's `.pieces` together rather than treating every piece as an independent replacement.

`.gear_pieces` compares individual slots and keeps unequipped baselines as `piece=None` with their displayed label and percentage. Disclaimer markers remain available. `.potentials` retains upgrade names, explanations, and cumulative comparisons when published. `.skill_priority` preserves the original expression and separate ordered skill names/operators, including `>=` and `=`.

`BuildPerformance.solo_percent` and `.team_percent` are Decimal percentages relative to the source baseline: `100` means 100%, not a fraction or a damage share. They can exceed 100. Missing comparisons are None. Equipment references include observed identities, icons, stats, and passive text when embedded metadata supplies them. Missing joins remain unknown and produce diagnostics.

## Damage charts

```python
for chart in full.calculations.charts:
    print(chart.title, chart.scope, chart.total_percent)
    for contribution in chart.contributions:
        print(contribution.label, contribution.percent)
```

Charts are optional. `.calculations.charts` contains `DamageDistribution` objects with `kind="pie"`, source labels, and Decimal percentages suitable for a chart renderer. Zero slices and source rounding are preserved; totals are not renormalized. The parser reads literal chart values from the page's embedded JSON because the rendered chart container can be empty. It does not estimate percentages or colors from a screenshot. If the HTML advertises a chart but its data is unavailable, diagnostics explain the omission.

`.calculations.members` retains the characters and equipment used by the source comparison setup. `.calculations.notes` preserves associated explanation.

## Best teams and rotations

```python
for team in full.teams:
    print(team.name, [member.name for member in team.members])
    for rotation in team.rotations:
        if rotation.kind == "timeline":
            for row in rotation.rows:
                for action in row.actions:
                    print(row.label, action.action, action.start_seconds, action.end_seconds)
        else:
            for step in rotation.steps:
                print(step.order, step.character.name if step.character else None, step.action)
```

Team guides preserve source-named compositions and their explanations, images, and videos. `.displayed_members` is the roster shown in the team header. Some pages show only three partners and imply the page owner; `.members` includes that owner and `.owner_implicit` records the distinction. Flexible examples can have more than four displayed characters, so the parser does not enforce a four-person list.

Timed rotations contain actor lanes and action names with Decimal `start_seconds`, `duration_seconds`, and computed `end_seconds`. Timing is calibrated from the rendered second markers, with geometry validation. Duration describes the source's displayed block span; it does not claim to be an independently measured cast time. `.displayed_duration_seconds` describes the visible timeline extent. Ordered rotations contain numbered actions without invented timestamps; an unspecified actor remains None. All rotations remain identical with `detailed=False`.

## Availability, refresh, and caching

Check `.availability` before assuming a section exists. States distinguish available content, explicit pending placeholders, and unavailable data. Upcoming characters can have an identity and assets before their build or review is published. `.updates` holds independent review/build/team patch labels, and `.source` supplies fetch provenance.

The first call discovers the character's actual page URL using the cached character index, fetching that index if necessary. An unknown identifier raises `NotFoundError`; refresh `characters(force_new=True)` when an older index needs newly added characters.

Each full guide is cached in `.prywen_cache/arknights-endfield/character_builds/<identifier>.json`. This also applies when the first request uses `detailed=False`; concise views are computed from the full cached model. `character_build("si", force_new=True)` fetches only Si's page again. Clearing the `character_builds` resource removes all such guides and retains the index. See [caching](caching.md) for custom cache roots and clearing.
