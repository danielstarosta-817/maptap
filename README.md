# maptap

Season standings and geography analysis for our daily [MapTap](https://maptap.gg) group.

Live at **https://danielstarosta-817.github.io/maptap/**

## Layout

    index.html               the standings page — one file, inline CSS and JS,
                             collapsible sections, and the custom-round builder
    play.html                standalone player for a custom round, opened by the share link
    data/scores.json         every posted score: per-day totals and per-round accuracy
    data/daily-series.json   the same totals as compact per-player strings, as the page uses them
    data/archive.json        mirror of MapTap's published locations, per date, in round order
    data/world.json          MapTap's own per-round player averages, per date
    scripts/update_archive.py  fetches any dates the two mirrors are missing
    scripts/build.py           rebuilds the standings from a fresh chat export
    scripts/update.sh          import a dropped export, rebuild, commit, push
    scripts/install-watcher.sh make macOS do that automatically

## Updating the standings

On your phone: open the group in WhatsApp, tap the group name, scroll to the bottom,
**Export Chat → Without Media**, and AirDrop the `.txt` to your Mac. WhatsApp has no
date-range option, so this is always the whole history — which is what we want, because
every rebuild recomputes from scratch and picks up late posts and edits retroactively.

Then either drop the file into `whatsapp_chat/` and run:

    ./scripts/update.sh

or, once, install the watcher and stop running anything at all:

    ./scripts/install-watcher.sh

With the watcher on, saving an export into `whatsapp_chat/` is the whole job: macOS notices
the file, imports it, rebuilds, commits, pushes, and shows a notification telling you who is
leading. The `.txt` and the `.zip` AirDrop hands you both work; the import unpacks the zip,
normalises it to `chat.txt` and deletes the dropped copy so the next run does not re-import it.

`update.sh` refuses to import an export with fewer results than the one already in place, so a
truncated file or the wrong chat cannot quietly wipe the season. It only commits when something
actually changed, and only ever commits `index.html` and `data/` — it will not sweep up whatever
else happens to be uncommitted in the repo when it fires. Push needs to work without prompting:
set up an SSH key or the macOS credential helper first, or it will commit and then tell you the
push stalled.

To review before publishing rather than have it push for you:

    MAPTAP_NO_PUSH=1 ./scripts/update.sh

It will import, rebuild and commit, then stop so you can look at the diff and `git push` yourself.

To do it by hand instead:

    cp ~/Downloads/"WhatsApp Chat with ....txt" whatsapp_chat/chat.txt   # replace, don't append
    python3 scripts/build.py
    git add -A && git commit -m "update standings" && git push

`build.py` rewrites the block marked `GENERATED` inside `index.html`, plus `data/scores.json`
and `data/daily-series.json`. It is stdlib-only and idempotent — running it twice changes
nothing the second time.

The export is ~1.5 KB a day, so size is never a constraint, and cadence is purely about how
fresh you want the page. Nothing is lost by waiting.

GitHub Pages serves `main` from the repo root. Enable it once under
**Settings → Pages → Source: Deploy from a branch → main / (root)**.

### What build.py does and does not own

It owns everything derived from the chat: the all-time table, head-to-head, the daily series,
the last-14-day figures, opening-versus-closing rounds, posting times and streaks. It was
checked against the hand-built page and reproduces every one of those exactly.

It does **not** yet recompute the geography — `REG`, `OWN` and `TERR`, the region ownership
that needs `data/archive.json`. Those are carried through from the page verbatim so a rebuild
can never blank them, and the script refuses to write rather than emit a broken page. Same for
the world-field round averages when `data/world.json` is still empty. Once the archive mirror
has backfilled, those can be computed too.

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

## Keeping the reference data current

`.github/workflows/archive.yml` runs `scripts/update_archive.py` daily at 19:40 UTC — after
MapTap publishes the day's player sample — and commits anything new. It only ever fetches dates
the mirrors do not already have, one request at a time with a one-second pause, identifying
itself in the User-Agent. Steady state is one or two requests a day.

The first run backfills, capped at 60 dates so a cold start spreads over a few days. To catch up
faster, run the workflow by hand from the Actions tab and raise the limit. If every fetch fails
the script exits non-zero rather than writing empty files, so a markup change on MapTap's side
shows up as a failed run instead of silently hollowing out the data.

What this does **not** do is update the standings. Those come from the chat export — this is the
reference data they are read against: the export says what we scored, the mirror says what we
were scoring on.

## Custom rounds

Build one at the bottom of the standings page: search five real places, relabel them however you
like, hit **Share this round**. That produces a single link to `play.html`, which opens the round
on its own page with nothing else around it.

The round travels inside the link — nothing is stored anywhere, so anyone in the group can make
one and the links never expire. The payload is packed and masked rather than left as readable
base64, so the answers are not legible at a glance. That is obfuscation, not secrecy: the page
decodes it in the browser, so anyone determined could too.

A round can be shared two ways, and the builder hands you both: the **link**, which opens the
round directly, and the bare **code**, which is pasted into the box on `play.html`. Opening
`play.html` with no round shows that box, and **Play another** on the results screen returns to
it, so you can play several people's rounds without leaving the page.

`play.html` uses **Esri World Imagery** (zoom 19, roughly a metre per pixel) rather than a
labelled basemap — labels would hand over the answer. Tapping drops your pin and locks it in
immediately, as the real game does; there is no confirm step. Scoring uses MapTap's real
multipliers, and the round-end emoji come from the table derived below.

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
- **Round emoji** were derived from the 4,605 rounds in the export by taking the most common
  emoji at each accuracy. That table reproduces 81% of the posted emoji exactly; MapTap varies
  the rest at random, so a perfect match is not possible.
- **Posting times** come from chat timestamps, counting only the 909 scores posted on the
  puzzle's own day.

## Privacy

`whatsapp_chat/` holds the raw export and is gitignored — it contains a phone number and every
message in the group. Keep it that way. The published page and the files in `data/` carry only
first names and scores.
