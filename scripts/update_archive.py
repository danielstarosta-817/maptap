#!/usr/bin/env python3
"""Keep a local mirror of MapTap's published archive.

Two things get pulled, both from endpoints the site itself serves publicly:

  data/archive.json    per date, the five locations in round order
  data/world.json      per date, the mean accuracy and perfect-rate of each round
                       across MapTap's own sample of real players

This is the reference data the standings are checked against: the chat export says what
we scored, this says what we were scoring on. It only ever fetches dates it does not
already have, one at a time with a pause, and identifies itself in the User-Agent.

Stdlib only. Run it with no arguments; --max limits how many new dates one run fetches
so a cold start spreads over a few days instead of hammering the site.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

REPO = "https://github.com/danielstarosta-817/maptap"
UA = "maptap-standings/1.0 (+%s) python-urllib" % REPO
ARCHIVE_START = dt.date(2026, 3, 23)          # the day the group chat started
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

WORLD_URL = ("https://firebasestorage.googleapis.com/v0/b/jjexperiment-12af6.appspot.com"
             "/o/map_data%2F{date}.json?alt=media")
PAGE_URL = "https://maptap.gg/history/{month}{day}.html"


def get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def places_for(day):
    """The five locations, in round order. Older pages carry JSON-LD; newer ones
    carry a per-story "places" field. Try both before giving up."""
    html = get(PAGE_URL.format(month=MONTHS[day.month - 1], day=day.day))

    m = re.search(r'"about"\s*:\s*(\[[\s\S]*?\])', html)
    if m:
        try:
            names = [x.get("name") for x in json.loads(m.group(1)) if x.get("name")]
            if len(names) == 5:
                return names
        except (ValueError, AttributeError):
            pass

    names = []
    for hit in re.finditer(r'"places"\s*:\s*(\[[^\]]*\])', html):
        try:
            arr = json.loads(hit.group(1))
        except ValueError:
            continue
        if arr:
            names.append(arr[0])
    return names[:5]


def world_for(day):
    """Mean accuracy and perfect-rate per round, over MapTap's sampled players."""
    try:
        raw = get(WORLD_URL.format(date=day.isoformat()))
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            return None                      # not published for that date
        raise
    j = json.loads(raw)
    sums, counts, perfect = [0.0] * 5, [0] * 5, [0] * 5
    for player in j.get("players", []):
        for i, rnd in enumerate((player.get("rounds") or [])[:5]):
            score = rnd.get("score")
            if isinstance(score, (int, float)):
                sums[i] += score
                counts[i] += 1
                if score == 100:
                    perfect[i] += 1
    if not any(counts):
        return None
    return {
        "sampled": j.get("sampledPlayerCount"),
        "players": j.get("totalPlayers"),
        "avg": [round(sums[i] / counts[i], 2) if counts[i] else None for i in range(5)],
        "perfect": [round(100.0 * perfect[i] / counts[i], 1) if counts[i] else None
                    for i in range(5)],
    }


def load(name):
    path = os.path.join(DATA, name)
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    return {}


def save(name, obj):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, name), "w") as fh:
        json.dump(dict(sorted(obj.items())), fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=60,
                    help="most new dates to fetch in one run (default 60)")
    ap.add_argument("--start", default=ARCHIVE_START.isoformat())
    ap.add_argument("--delay", type=float, default=1.0,
                    help="seconds between requests (default 1.0)")
    args = ap.parse_args()

    archive, world = load("archive.json"), load("world.json")
    start = dt.date.fromisoformat(args.start)
    # the world sample for a given day is published after it ends, so stop at yesterday
    end = dt.date.today() - dt.timedelta(days=1)

    wanted = []
    day = start
    while day <= end:
        key = day.isoformat()
        if key not in archive or key not in world:
            wanted.append(day)
        day += dt.timedelta(days=1)

    if not wanted:
        print("up to date through %s (%d dates archived)" % (end, len(archive)))
        return 0

    todo = wanted[: args.max]
    print("%d date(s) missing, fetching %d this run" % (len(wanted), len(todo)))

    added_a = added_w = 0
    failures = []
    for day in todo:
        key = day.isoformat()
        if key not in archive:
            try:
                names = places_for(day)
                if names:
                    archive[key] = names
                    added_a += 1
                    if len(names) != 5:
                        print("  %s  only %d location(s) listed" % (key, len(names)))
                else:
                    failures.append((key, "no locations found"))
            except Exception as e:                       # noqa: BLE001 - report and move on
                failures.append((key, "page: %s" % e))
            time.sleep(args.delay)
        if key not in world:
            try:
                w = world_for(day)
                if w:
                    world[key] = w
                    added_w += 1
            except Exception as e:                       # noqa: BLE001
                failures.append((key, "world: %s" % e))
            time.sleep(args.delay)

    save("archive.json", archive)
    save("world.json", world)
    print("archive: +%d (now %d)   world: +%d (now %d)"
          % (added_a, len(archive), added_w, len(world)))

    if failures:
        print("\n%d problem(s):" % len(failures), file=sys.stderr)
        for key, why in failures[:20]:
            print("  %s  %s" % (key, why), file=sys.stderr)
        # A handful of gaps is normal. Everything failing means the markup moved, and
        # that should be loud rather than a silently empty file.
        if added_a == 0 and added_w == 0:
            print("nothing could be fetched at all - has the site changed?", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
