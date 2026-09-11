# maptap

Season standings and geography analysis for our daily [MapTap](https://maptap.gg) group.

Live at **https://danielstarosta-817.github.io/maptap/**

## Layout

    index.html               the standings page — one file, inline CSS and JS,
                             collapsible sections, and the custom-round builder
    puzzles/<n>.json         optional numbered custom rounds, shared as #n=<n>
    data/scores.json         every posted score: per-day totals and per-round accuracy
    data/daily-series.json   the same totals as compact per-player strings, as the page uses them

## Publishing

GitHub Pages serves `main` from the repo root, so publishing is just:

    git add -A && git commit -m "update standings" && git push

Enable it once under **Settings → Pages → Source: Deploy from a branch → main / (root)**.

## Runtime dependencies

The page is one file, but it is not fully offline. Everything it fetches is a public CDN or
tile service; none of it needs a key.

- **Google Fonts** — Archivo, IBM Plex Mono, Source Serif 4. Each has a real fallback stack,
  so a block just changes the typeface.
- **Leaflet 1.9.4** (cdnjs) — both `leaflet.js` and `leaflet.css`. The stylesheet is not
  optional: without it the map panes are unpositioned and tiles stack vertically. The page
  probes for it at runtime and falls back if it is missing.
- **Esri World Shaded Relief** tiles, `.../World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}`
  (note Esri's y-before-x ordering), max zoom 13. Attribution is a licence condition and is
  rendered on the map: *Tiles © Esri — Source: Esri, USGS, NOAA*. Relief rather than satellite
  imagery on purpose — seven translucent ownership colours turn to mud over imagery.
- **topojson 3.0.2** (cdnjs) and **world-atlas countries-110m** (jsDelivr) — real lat/lng
  country geometry, dissolved into the 30 regions with `topojson.merge` so same-owner
  neighbours read as one block.
- **cdnjs** — `jsvectormap/1.5.3/maps/world.js`. Still used for the custom-round builder's
  pin map, and as the territory map's fallback renderer.
- **Nominatim** (OpenStreetMap) — place search in the round builder, so a round is built by
  typing "cairo egypt" or "nile river" rather than clicking blind. Keyless, throttled client-side
  to one request a second as their usage policy requires. Results are © OpenStreetMap
  contributors, ODbL. Pleasingly, it resolves historical names too: *british honduras* → Belize,
  *upper volta* → Burkina Faso. If it is unreachable the row falls back to clicking the map.

**Fallback chain.** If Leaflet, its stylesheet, or the country geometry fails to load — or if
eight tiles error before any succeeds — the territory map quietly reverts to the flat Miller
SVG it used before, with a note saying so. If that geometry is missing too, the ownership table
below carries the full breakdown. The section degrades rather than going blank.

**Dark mode.** Esri's relief is a light basemap only, so under the dark theme the tile pane is
dimmed with a CSS filter (`brightness(.52) contrast(1.08) saturate(.8)`) rather than inverted —
inverting shaded relief turns mountains into pits.

**Known gotcha, already handled.** Natural Earth and jsvectormap spell countries differently
(`Laos` vs `Lao PDR`, `North Korea` vs `Dem. Rep. Korea`, lowercase `eSwatini`). The country to
region map covers both spellings and the page asserts at runtime that every country resolves,
logging any that do not — a silent miss would quietly shrink a region and shift the totals.
Antarctica and the French Southern Territories are deliberately unassigned. All 177 countries
currently resolve.

Everything else — scores, region ownership, chart geometry, the custom-round encoder — is inline.

## Sharing a custom round

Two routes, both from the builder at the bottom of the page:

- **`#p=<code>`** — the whole round packed into the link. The payload is masked rather than left
  as readable base64 JSON, so the answers are not legible at a glance. This is obfuscation, not
  secrecy: the page decodes it in the browser, so anyone determined can too.
- **`#n=<number>`** — the round lives in `puzzles/<number>.json` and the URL carries no answers
  at all. Hit **Numbered instead** in the builder, save the JSON it prints, push. Costs a commit
  per round; worth it if you care that the link gives nothing away.

Links made before the masking was added still decode.

## Data notes

- **Scores** come from the group chat export: 920 unique entries over 170 puzzle days,
  23 March to 8 September 2026. Where someone posted twice for one day, the first attempt counts.
  Cross-checked against the standings ChatGPT produced on 22 July: wins matched exactly for all
  six players who were playing then.
- **A win** goes to the highest final score of the day; on a tie, everyone at the top gets one.
- **MapTap's scoring formula**, recovered by least-squares fitting the 920 posted finals against their
  five round accuracies, is `1*R1 + 1*R2 + 2*R3 + 3*R4 + 3*R5`, out of 1000. It reproduces all 920
  entries exactly, with zero error, which is why a posted final never equals the sum of its rounds.
  The custom round builder uses the same weighting.
- **Locations** come from MapTap's permanent per-date archive pages, which name the five stories
  in round order. 166 of the 170 days list all five; the other four list only four and sit out of
  the geography tables — 830 rounds joined, 818 placed in one of 30 regions.
- **World averages** in the round-position chart come from MapTap's daily sample of roughly
  630 real players.
- **Posting times** come from chat timestamps, counting only the 909 scores posted on the
  puzzle's own day.

## Privacy

`whatsapp_chat/` holds the raw export and is gitignored — it contains a phone number and every
message in the group. Keep it that way. The published page and the files in `data/` carry only
first names and scores.
