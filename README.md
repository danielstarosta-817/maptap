# maptap

Season standings and geography analysis for our daily [MapTap](https://maptap.gg) group.

Live at **https://danielstarosta-817.github.io/maptap/**

## Layout

    index.html               the standings page — one file, inline CSS and JS
    data/scores.json         every posted score: per-day totals and per-round accuracy
    data/daily-series.json   the same totals as compact per-player strings, as the page uses them

## Publishing

GitHub Pages serves `main` from the repo root, so publishing is just:

    git add -A && git commit -m "update standings" && git push

Enable it once under **Settings → Pages → Source: Deploy from a branch → main / (root)**.

## Runtime dependencies

The page is one file, but it is not fully offline: it pulls two things over HTTPS at load.
Neither needs a key, and both are public CDNs.

- **Google Fonts** — Archivo, IBM Plex Mono, Source Serif 4. Each has a real fallback stack,
  so a block just changes the typeface.
- **cdnjs** — `jsvectormap/1.5.3/maps/world.js`, which supplies the country outlines for the
  territory map. It is loaded with a small stub that captures the geometry instead of starting
  the library. If it fails, the map replaces itself with a short message and the region table
  underneath still carries the full breakdown.

Everything else — all scores, region assignments and chart geometry — is inline.

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
