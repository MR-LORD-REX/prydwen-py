# prydwen-py

**Typed guide data for asynchronous Python applications.** Start with Arknights: Endfield, retrieve only the section you need, and reuse validated results from a persistent local cache.

```python
from prydwen import Prydwen

async with Prydwen.Endfield() as endfield:
    result = await endfield.characters()
    print(result.total_count)
    for character in result.characters:
        print(character.identifier, character.name)
```

The library parses public Prydwen HTML. It combines rendered records with structured metadata already embedded in the page; it does not require a public JSON API. Catalog images, reward icons, and team backgrounds remain links, ready for separate card libraries.

## Start here

- [Installation](getting-started/installation.md) and [quickstart](getting-started/quickstart.md).
- [Endfield methods](reference/endfield.md), including all arguments and returned types.
- [Output models](reference/output-models.md) for identities, stats, assets, tiers, and teams.
- [Caching](guides/caching.md) for `force_new`, storage location, and clearing.
- [Banners and codes](guides/banners-and-codes.md) for regional timing and source uncertainty.

Version 0.1.0 focuses on section-level data. Character-specific builds and skills are future work. This independent project does not claim ownership of the source guide content or artwork.
