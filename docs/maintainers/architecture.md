# Architecture and adding games

```text
Prydwen facade
  games/<game>/client.py
    core/client.py -> core/cache.py
                   -> core/transport.py
    games/<game>/parsers/* -> parsing/*
    games/<game>/models/*
```

Game clients choose a resource, model, and pure parser. The shared loader manages context lifecycle, coalescing, cache validation, fetches, parsing workers, and atomic persistence. Parsers perform no I/O. Models do not fetch relationships or images.

The site uses streaming SSR, including primary DOM content inside hidden containers. Select known section roots without discarding hidden content. The embedded adapter decodes a bounded subset of literal Next.js JSON text frames; it never evaluates JavaScript or treats unstable Flight IDs/array positions as selectors. Missing optional embedded enrichment falls back to DOM with diagnostics; missing required identities raises an error.

## Character guide pipeline

The Endfield client discovers character URLs from the index and loads one guide under `character_builds/<identifier>`. Shared transport and caching still own all I/O. The pure parser is split by responsibility:

- `parsers/builds.py` validates the page owner and semantic tab/section headings, then assembles review ratings, availability, calculation setups, and chart data.
- `parsers/build_common.py` resolves source character/equipment references and converts prose to ordered safe blocks with emphasis, links, and media.
- `parsers/build_equipment.py` handles ranked recommendations, grouped replacements, individual-slot comparisons, potentials, and skill priority.
- `parsers/build_teams.py` keeps each team's guide local and extracts both timed lanes and untimed instructions. Marker positions calibrate timeline geometry; block widths describe display spans.
- `models/builds.py` defines the renderer contracts. `build_text.py` produces concise prose without filtering any structured records.

DOM order remains authoritative for rankings, loadouts, teams, and prose. Embedded literal JSON enriches identity/stats and supplies chart slices absent from the SSR chart container. Required DOM/metadata count disagreements fail explicitly. Unknown optional enrichment produces diagnostics instead of invented stats or chart values.

Full guides are always cached. Concise projection runs after loading, including on a cache hit, and cannot replace the cached full model. Dynamic cache keys are contained beneath their registered resource group. Clearing that group invalidates in-flight child writes as well as removing existing guide files.

## Add another game

1. Create `src/prydwen/games/<game>/` with endpoints, client, models, and parsers.
2. Supply the known resource set and game key to the shared base client.
3. Add pure parsers and fixture-based tests for that game's HTML shape.
4. Import and alias its client on the root `Prydwen` facade.
5. Register its known resource keys with root cache clearing and document the new API.

Keep source keys, display names, official game IDs, and local fallback identifiers distinct. New games can use different domain models while sharing only transport/cache/provenance primitives. Do not add game-specific selectors to the shared loader.

Runtime models use lists for the user's collection contract and collection metadata directly on each dataset. There is no separate envelope object in the public return API.
