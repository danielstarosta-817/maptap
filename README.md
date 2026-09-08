# maptap

Season standings and geography analysis for our daily [MapTap](https://maptap.io) group.

Live at **https://danielstarosta-817.github.io/maptap/**

## Layout

    index.html   the standings page — self-contained (inline CSS/JS, inlined map geometry)
    data/        scraped archive + group leg data

## Publishing

GitHub Pages serves `main` from the repo root, so publishing is just:

    git add -A && git commit -m "update standings" && git push

Enable it once under **Settings → Pages → Source: Deploy from a branch → main / (root)**.

## Notes

- Single self-contained HTML file. Country geometry is inlined rather than fetched at runtime.
- Round order for each date comes from MapTap's public archive pages; per-round world averages
  come from the daily player sample.
