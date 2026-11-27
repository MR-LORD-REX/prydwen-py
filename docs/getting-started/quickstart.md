# Quickstart

Keep the game client inside an asynchronous context so owned HTTP sessions and workers close correctly.

```python
import asyncio

from prydwen import Prydwen


async def main():
    async with Prydwen.Endfield() as endfield:
        characters = await endfield.characters()
        print(characters.total_count)

        for entry in await endfield.list_characters():
            print(entry.name, entry.identifier)

        pieces = await endfield.list_gears()
        piece = await endfield.gear(pieces[0].identifier)
        print(piece.name, piece.defense)

        sets = await endfield.list_gear_sets()
        selected = await endfield.gear_set(sets[0].identifier)
        print(selected.name, selected.total_count)

        tiers = await endfield.team_tier_list()
        for tier in tiers.tiers:
            for team in tier.teams:
                print(tier.tier, team.name)
                for slot in team.slots:
                    print(slot.position, [candidate.name for candidate in slot.candidates])


asyncio.run(main())
```

Identifiers from list methods are the lookup contract. Display names are unsuitable because different gear pieces can have the same name. Character identifiers are available now for future character-detail operations.

Every data method accepts `force_new=True` for a fresh request. The first call to each resource already fetches when no valid cache exists; it does not need the flag. List and detail operations for gear share one catalog cache.

```python
async with Prydwen.Endfield() as endfield:
    result = await endfield.characters(force_new=True)
    print(result.delivery.from_cache)
    print(result.source.fetched_at)
```
