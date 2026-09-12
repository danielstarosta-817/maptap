#!/usr/bin/env python3
"""Rebuild the standings from a fresh WhatsApp export.

    python3 scripts/build.py

Reads  whatsapp_chat/chat.txt   the export, replaced wholesale each time
       data/archive.json        MapTap's locations per date (scripts/update_archive.py)
       data/world.json          MapTap's per-round player averages

Writes data/scores.json, data/daily-series.json, and the GENERATED block inside index.html.

The export is cumulative, so every run recomputes from scratch. That is deliberate: late
posts, edits and parser fixes all get picked up retroactively, and there is no incremental
merge to drift. Stdlib only.
"""

import datetime as dt
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAT = os.path.join(HERE, "whatsapp_chat", "chat.txt")
DATA = os.path.join(HERE, "data")
PAGE = os.path.join(HERE, "index.html")

# Export came off an Eastern phone; these are each player's own clock.
PLAYERS = ["Brian", "Gabe", "Drew", "Zach", "Brett", "Luke", "Danny"]
TZ = {"Gabe": ("PT", -3), "Luke": ("PT", -3), "Zach": ("CT", -1),
      "Brian": ("ET", 0), "Drew": ("ET", 0), "Brett": ("ET", 0), "Danny": ("ET", 0)}
# Whoever exports the chat appears as "You"; everyone else by their saved name.
ALIASES = {"You": "Danny", "Brian Harris": "Brian", "Gabe Starosta": "Gabe",
           "Drew Orvieto": "Drew", "Zach Epstein": "Zach", "Brett Orvieto": "Brett",
           "+1 (954) 684-6506": "Luke"}
WEIGHTS = [1, 1, 2, 3, 3]          # MapTap's own, recovered by fitting 920 posted finals
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

HDR = re.compile(r"^\[(\d+)/(\d+)/(\d+), (\d+):(\d+):(\d+)\s*([AP]M)\] (.+?): (.*)$")
EMOJI = r"(?:[\U0001F300-\U0001FAFF☀-➿⬀-⯿]️?)"
LEG = re.compile(r"(\d{1,3})\s*(" + EMOJI + ")")


# --------------------------------------------------------------------------- parsing
def read_chat(path):
    """Every posted result: puzzle date, player, five round accuracies, final, timestamp."""
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()

    msgs, cur = [], None
    for line in raw.split("\n"):
        m = HDR.match(line)
        if m:
            if cur:
                msgs.append(cur)
            mo, d, y, hh, mm, ss, ampm, who, body = m.groups()
            hour = int(hh) % 12 + (12 if ampm == "PM" else 0)
            cur = {"ts": dt.datetime(2000 + int(y), int(mo), int(d), hour, int(mm), int(ss)),
                   "who": ALIASES.get(who, who), "body": body}
        elif cur is not None:
            cur["body"] += "\n" + line
    if cur:
        msgs.append(cur)

    # Custom rounds built on the site are for fun and must never reach the standings.
    # They already cannot: a score only counts when a "maptap.gg <Mon> <day>" header sits
    # directly above it, and a custom round emits no such header. This is the second lock,
    # so that loosening the parser later cannot quietly start counting them.
    FAKE = re.compile(r"fake maptap|fake score:", re.I)

    seen, year = {}, None
    for m in msgs:
        if FAKE.search(m["body"]):
            continue
        lines = m["body"].split("\n")
        for i, line in enumerate(lines):
            hit = re.search(r"maptap\.gg\s+(\w+)\s+(\d+)\s*$", line.strip(), re.I)
            if not hit or hit.group(1) not in MONTHS:
                continue
            month = MONTHS.index(hit.group(1)) + 1
            # the post itself carries no year; take it from the timestamp
            pz = dt.date(m["ts"].year, month, int(hit.group(2)))
            legs, total = None, None
            for j in range(i + 1, min(i + 4, len(lines))):
                fin = re.search(r"Final score:\s*([\d,]+)", lines[j])
                if fin:
                    total = int(fin.group(1).replace(",", ""))
                    break
                vals = [int(x) for x, _ in LEG.findall(lines[j])]
                if len(vals) == 5 and legs is None:
                    legs = vals
            if total is None:
                continue
            key = (pz, m["who"])
            if key not in seen:                      # a repost of the same day is a replay
                seen[key] = {"pz": pz, "who": m["who"], "total": total,
                             "legs": legs or [], "ts": m["ts"]}
    return sorted(seen.values(), key=lambda r: (r["pz"], r["who"]))


# --------------------------------------------------------------------------- helpers
def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def js(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def ascii_js(text):
    """The page is served as pure ASCII so no host can mis-decode it."""
    out = []
    for ch in text:
        o = ord(ch)
        if o < 128:
            out.append(ch)
        elif o <= 0xFFFF:
            out.append("\\u%04x" % o)
        else:
            v = o - 0x10000
            out.append("\\u%04x\\u%04x" % (0xD800 + (v >> 10), 0xDC00 + (v & 0x3FF)))
    return "".join(out)


# --------------------------------------------------------------------------- stats
def build(recs, archive, world):
    days = sorted({r["pz"] for r in recs})
    by_day = defaultdict(dict)
    for r in recs:
        by_day[r["pz"]][r["who"]] = r
    present = [p for p in PLAYERS if any(r["who"] == p for r in recs)]

    # ---- per player, all time
    st = {p: dict(w=0, tie=0, gp=0, tot=0, h=0, pod=0, g950=0, s800=0,
                  best=0, worst=9999, streak=0, run=0) for p in present}
    for day in days:
        table = by_day[day]
        top = max(x["total"] for x in table.values())
        winners = [w for w, x in table.items() if x["total"] == top]
        order = sorted(table.items(), key=lambda kv: -kv[1]["total"])
        rank, prev = 0, None
        ranks = {}
        for i, (who, x) in enumerate(order):
            if x["total"] != prev:
                rank, prev = i + 1, x["total"]
            ranks[who] = rank
        for who, x in table.items():
            s = st[who]
            s["gp"] += 1
            s["tot"] += x["total"]
            s["best"] = max(s["best"], x["total"])
            s["worst"] = min(s["worst"], x["total"])
            if x["total"] >= 950:
                s["g950"] += 1
            if x["total"] < 800:
                s["s800"] += 1
            if ranks[who] <= 3:
                s["pod"] += 1
            if len(x["legs"]) == 5:
                s["h"] += sum(1 for v in x["legs"] if v == 100)
        for who in present:
            s = st[who]
            if who in winners:
                s["w"] += 1
                if len(winners) > 1:
                    s["tie"] += 1
                s["run"] += 1
                s["streak"] = max(s["streak"], s["run"])
            else:
                s["run"] = 0

    all_rows = sorted(
        [dict(p=p, w=st[p]["w"], tie=st[p]["tie"], gp=st[p]["gp"], h=st[p]["h"],
              pod=st[p]["pod"], g950=st[p]["g950"], s800=st[p]["s800"],
              best=st[p]["best"], worst=st[p]["worst"],
              avg=round(st[p]["tot"] / st[p]["gp"], 1)) for p in present],
        key=lambda r: -r["w"])

    # ---- head to head
    h2h = {}
    for a in present:
        h2h[a] = {}
        for b in present:
            if a == b:
                continue
            wins = losses = 0
            for day in days:
                t = by_day[day]
                if a in t and b in t:
                    if t[a]["total"] > t[b]["total"]:
                        wins += 1
                    elif t[a]["total"] < t[b]["total"]:
                        losses += 1
            h2h[a][b] = [wins, losses]

    # ---- daily series, three digits a day, 000 = did not play
    raw = {}
    for p in present:
        raw[p] = "".join("%03d" % by_day[d].get(p, {}).get("total", 0) for d in days)
    raw["Best"] = "".join("%03d" % max(x["total"] for x in by_day[d].values()) for d in days)

    # ---- last 14 days
    last14 = days[-14:]
    era = []
    for p in present:
        vals = [by_day[d][p]["total"] for d in last14 if p in by_day[d]]
        era.append(dict(p=p, l14=round(mean(vals), 1) if vals else 0, l14n=len(vals)))

    # ---- opening vs closing rounds, and the hardest rounds of the season
    hard_rounds = set()
    if world:
        scored = []
        for date, w in world.items():
            for i, avg in enumerate(w.get("avg") or []):
                if avg is not None:
                    scored.append((avg, date, i))
        scored.sort()
        hard_rounds = {(d, i) for _, d, i in scored[:40]}

    hard = []
    for p in present:
        e = [v for r in recs if r["who"] == p and len(r["legs"]) == 5 for v in r["legs"][:2]]
        hh = [v for r in recs if r["who"] == p and len(r["legs"]) == 5 for v in r["legs"][3:]]
        r5 = [r["legs"][4] for r in recs if r["who"] == p and len(r["legs"]) == 5]
        hv = [r["legs"][i] for r in recs if r["who"] == p and len(r["legs"]) == 5
              for i in range(5) if (r["pz"].isoformat(), i) in hard_rounds]
        hard.append(dict(p=p, v=round(mean(hv), 1) if hv else 0, n=len(hv),
                         e=round(mean(e), 1), h=round(mean(hh), 1), r5=round(mean(r5), 1)))

    # ---- round position: this group against MapTap's field
    ours = []
    for i in range(5):
        ours.append(round(mean([r["legs"][i] for r in recs if len(r["legs"]) == 5]), 1))
    glob = []
    for i in range(5):
        vals = [w["avg"][i] for w in world.values() if (w.get("avg") or [None] * 5)[i] is not None]
        glob.append(round(mean(vals), 1) if vals else None)

    # ---- posting time, on each player's own clock
    same_day = [r for r in recs if r["ts"].date() == r["pz"]]
    base = {p: mean([r["total"] for r in recs if r["who"] == p]) for p in present}
    buckets = [(0, 4, "Midnight&#8211;4am"), (4, 7, "4&#8211;7am"), (7, 9, "7&#8211;9am"),
               (9, 11, "9&#8211;11am"), (11, 14, "11am&#8211;2pm"), (14, 18, "2&#8211;6pm"),
               (18, 24, "6pm&#8211;midnight")]
    agg = defaultdict(lambda: [0.0, 0, 0])
    for r in same_day:
        local = r["ts"] + dt.timedelta(hours=TZ[r["who"]][1])
        top = max(x["total"] for x in by_day[r["pz"]].values())
        for lo, hi, label in buckets:
            if lo <= local.hour < hi:
                agg[label][0] += r["total"] - base[r["who"]]
                agg[label][1] += 1
                agg[label][2] += 1 if r["total"] == top else 0
                break
    timing = [[label, agg[label][1],
               round(agg[label][0] / agg[label][1], 1) if agg[label][1] else 0.0,
               round(100.0 * agg[label][2] / agg[label][1], 1) if agg[label][1] else 0.0]
              for _, _, label in buckets if agg[label][1]]

    clock = []
    for p in present:
        mine = sorted((r for r in same_day if r["who"] == p),
                      key=lambda r: ((r["ts"] + dt.timedelta(hours=TZ[p][1])).hour * 60
                                     + (r["ts"] + dt.timedelta(hours=TZ[p][1])).minute))
        if not mine:
            continue
        mins = [((r["ts"] + dt.timedelta(hours=TZ[p][1])).hour * 60
                 + (r["ts"] + dt.timedelta(hours=TZ[p][1])).minute) for r in mine]
        med = mins[len(mins) // 2]
        pre9 = round(100.0 * sum(1 for m in mins if m < 540) / len(mins))
        half = len(mine) // 2
        early = mean([r["total"] for r in mine[:half]]) or 0
        late = mean([r["total"] for r in mine[half:]]) or 0
        clock.append([p, TZ[p][0], "%02d:%02d" % (med // 60, med % 60), pre9,
                      round(early, 1), round(late, 1)])
    clock.sort(key=lambda c: c[2])

    streaks = {p: st[p]["streak"] for p in present}
    return dict(days=days, by_day=by_day, present=present, all_rows=all_rows, h2h=h2h,
                streaks=streaks,
                raw=raw, era=era, hard=hard, ours=ours, glob=glob,
                timing=timing, clock=clock)


# --------------------------------------------------------------------------- output
def render_block(b, days):
    """The GENERATED region of index.html, in the shape the page's code expects."""
    L = []
    L.append("const ALL=[")
    for r in b["all_rows"]:
        L.append(" {p:%s,w:%d,tie:%d,gp:%d,h:%d,pod:%d,g950:%d,s800:%d,best:%d,worst:%d,avg:%s},"
                 % (js(r["p"]), r["w"], r["tie"], r["gp"], r["h"], r["pod"], r["g950"],
                    r["s800"], r["best"], r["worst"], r["avg"]))
    L[-1] = L[-1].rstrip(",")
    L.append("];")

    L.append("const ERA=[")
    for r in b["era"]:
        L.append(" {p:%s,l14:%s,l14n:%d}," % (js(r["p"]), r["l14"], r["l14n"]))
    L[-1] = L[-1].rstrip(",")
    L.append("];")

    L.append("const H2H=" + js(b["h2h"]) + ";")
    L.append("const ORDER=" + js(b["present"]) + ";")
    L.append("// Daily finals, %s to %s. %d days, 3 digits each, 000 = did not play."
             % (days[0].strftime("%-d %b %Y"), days[-1].strftime("%-d %b %Y"), len(days)))
    L.append("const RAW={")
    for k, v in b["raw"].items():
        L.append("%s:%s," % (k, js(v)))
    L[-1] = L[-1].rstrip(",")
    L.append("};")
    L.append("const NDAYS=%d, DAY0=new Date(%d,%d,%d);"
             % (len(days), days[0].year, days[0].month - 1, days[0].day))
    L.append("const STREAK=" + js(b["streaks"]) + ";")
    L.append("const TIMING=" + js(b["timing"]) + ";")
    L.append("const CLOCK=" + js(b["clock"]) + ";")
    L.append("const ROUNDPOS={global:%s, ours:%s};" % (js(b["glob"]), js(b["ours"])))
    L.append("const HARD=[")
    for r in b["hard"]:
        L.append(" {p:%s,v:%s,n:%d,e:%s,h:%s,r5:%s}," %
                 (js(r["p"]), r["v"], r["n"], r["e"], r["h"], r["r5"]))
    L[-1] = L[-1].rstrip(",")
    L.append("];")
    return "\n".join(L) + "\n"


# Geography (REG / OWN / TERR) is derived from MapTap's archive rather than the chat, and
# changes only as new locations appear. Until the archive mirror covers the season it is
# carried through from the page verbatim, so rebuilding scores never blanks those sections.
GEO_CONSTS = ("REG", "OWN", "TERR")


def previous(old_block, name):
    """Pull one const's source out of the block currently in the page."""
    m = re.search(r"^const %s=.*?^\];$" % name, old_block, re.S | re.M)
    if not m:
        m = re.search(r"^const %s=.*?;$" % name, old_block, re.M)
    return m.group(0) if m else None


def previous_world(old_block):
    """The previous global round means, for when data/world.json is not populated."""
    src = previous(old_block, "ROUNDPOS")
    if not src:
        return None
    m = re.search(r"global:\s*(\[[^\]]*\])", src)
    if not m:
        return None
    try:
        vals = json.loads(m.group(1))
    except ValueError:
        return None
    return vals if any(v is not None for v in vals) else None


def previous_hard(old_block):
    """Previous 40-hardest-round figures, keyed by player."""
    src = previous(old_block, "HARD")
    out = {}
    if not src:
        return out
    for m in re.finditer(r'\{p:\s*"([^"]+)"\s*,\s*v:\s*([\d.]+)\s*,\s*n:\s*(\d+)', src):
        out[m.group(1)] = (float(m.group(2)), int(m.group(3)))
    return out


def carry_geography(old_block):
    kept = []
    for name in GEO_CONSTS:
        m = re.search(r"^const %s=.*?^\];$" % name, old_block, re.S | re.M)
        if not m:
            m = re.search(r"^const %s=.*?;$" % name, old_block, re.M)
        if m:
            kept.append(m.group(0))
    return ("\n".join(kept) + "\n") if kept else ""


def main():
    if not os.path.exists(CHAT):
        print("no export at %s" % CHAT, file=sys.stderr)
        print("export the group from WhatsApp (Without Media) and save it there.", file=sys.stderr)
        return 1

    recs = read_chat(CHAT)
    if not recs:
        print("no MapTap results found in the export - is it the right chat?", file=sys.stderr)
        return 1

    def load(name):
        path = os.path.join(DATA, name)
        return json.load(open(path)) if os.path.exists(path) else {}

    archive, world = load("archive.json"), load("world.json")
    page_preview = open(PAGE, encoding="utf-8").read()
    pb = page_preview.index("/* ---- GENERATED:BEGIN")
    pb = page_preview.index("\n", pb) + 1
    pe = page_preview.index("/* ---- GENERATED:END")
    old_block = page_preview[pb:pe]

    b = build(recs, archive, world)
    days = b["days"]

    # Without the world mirror those figures would come out empty, which would blank the
    # round-position chart and the hardest-rounds column. Keep the previous ones instead.
    if not world:
        carried = previous_world(old_block)
        if carried:
            b["glob"] = carried
        prev_hard = previous_hard(old_block)
        for row in b["hard"]:
            if row["n"] == 0 and row["p"] in prev_hard:
                row["v"], row["n"] = prev_hard[row["p"]]
        if carried or prev_hard:
            print("data/world.json is empty; keeping the previous world figures "
                  "(run scripts/update_archive.py to refresh them)")

    # keep the raw scores alongside the page
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "scores.json"), "w") as fh:
        json.dump({"recs": [{"pz": r["pz"].isoformat(), "who": r["who"],
                             "total": r["total"], "legs": r["legs"]} for r in recs]},
                  fh, indent=1)
        fh.write("\n")
    with open(os.path.join(DATA, "daily-series.json"), "w") as fh:
        json.dump({"d0": days[0].isoformat(), "n": len(days), "series": b["raw"]}, fh, indent=1)
        fh.write("\n")

    page = page_preview
    begin, end = pb, pe
    new = ascii_js(render_block(b, days)) + carry_geography(old_block)
    for name in GEO_CONSTS:
        if ("const %s=" % name) not in new:
            print("could not carry %s through; refusing to write a broken page" % name,
                  file=sys.stderr)
            return 1
    if page[begin:end] == new:
        print("standings unchanged (%d results through %s)" % (len(recs), days[-1]))
        return 0
    open(PAGE, "w", encoding="utf-8").write(page[:begin] + new + page[end:])

    lead = b["all_rows"][0]
    print("%d results, %s to %s" % (len(recs), days[0], days[-1]))
    print("leader: %s, %d wins from %d days (avg %.1f)"
          % (lead["p"], lead["w"], lead["gp"], lead["avg"]))
    missing = [d.isoformat() for d in days if d.isoformat() not in archive]
    if missing:
        print("%d day(s) not yet in data/archive.json - run scripts/update_archive.py"
              % len(missing))
    print("\nrebuilt index.html; commit and push to publish.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
