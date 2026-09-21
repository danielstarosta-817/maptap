#!/usr/bin/env python3
"""Region analysis: turn MapTap's archive of daily locations into REG / OWN / TERR.

The chat tells us how everyone scored on each of the five rounds. The archive tells us
where those rounds were. Joining them is what makes every geography section on the page
possible, and until this existed the whole lot was computed once by hand and then carried
verbatim through every rebuild, slowly going stale.

The archive names a place as free text -- "Palomar Observatory, California", "Baghdad,
Iraq", "The Terracotta Army". Everything hangs on turning that into a country, so
resolve() is deliberately conservative: anything it cannot place with confidence is
reported and left out rather than guessed into the wrong region.
"""
import collections
import re

# --------------------------------------------------------------------- resolution

US_STATES = {
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
    "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan",
    "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina",
    "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
    "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
    "Washington DC", "District of Columbia",
}

# Tail-of-string aliases. Only unambiguous ones belong here.
ALIAS = {
    "USA": "United States", "U.S.": "United States", "US": "United States",
    "England": "United Kingdom", "Scotland": "United Kingdom",
    "Wales": "United Kingdom", "Northern Ireland": "United Kingdom",
    "UK": "United Kingdom", "Great Britain": "United Kingdom",
    "Channel Islands (British Crown Dependencies)": "United Kingdom",
    "Turkiye": "Turkey", "Türkiye": "Turkey",
    "Czech Republic": "Czechia",
    "North Macedonia": "Macedonia",
    # RC uses the map's own spellings, so alias onto those rather than the common names
    "South Korea": "Korea", "Korea, South": "Korea", "Republic of Korea": "Korea",
    "North Korea": "Dem. Rep. Korea", "Korea, North": "Dem. Rep. Korea",
    "Laos": "Lao PDR", "Lao People's Democratic Republic": "Lao PDR",
    "Solomon Islands": "Solomon Is.",
    "Cote d'Ivoire": "Ivory Coast", "Côte d'Ivoire": "Ivory Coast",
    "Democratic Republic of Congo": "Dem. Rep. Congo",
    "Democratic Republic of the Congo": "Dem. Rep. Congo",
    "Republic of the Congo": "Congo",
    "South Sudan": "S. Sudan",
    "The Gambia": "Gambia",
    "Sao Tome and Principe": "Sao Tome and Principe",
    "São Tomé and Príncipe": "Sao Tome and Principe",
    "Vatican City": "Italy",          # enclave; sits in the Italy region
    "Monaco": "France",               # ditto, France & Low Countries
    "Sicily": "Italy",
    "Zanzibar": "Tanzania",
    "Tahiti": "French Polynesia", "French Polynesia": "French Polynesia",
    "Jerusalem": "Israel",
    "Tokyo": "Japan",
    "Bermuda": "United Kingdom",
    "US Virgin Islands": "United States",
    "Antigua and Barbuda": "Antigua and Barbuda",
    "Central African Republic": "Central African Rep.",
    "Marshall Islands": "Marshall Islands",
    "Comoros": "Comoros",
    "Switzerland)": "Switzerland",    # stray bracket in the source
}

# Whole-string special cases: landmarks and events the tail cannot resolve.
WHOLE = {
    "Mount Everest": "Nepal",
    "The Suez Canal": "Egypt",
    "Niagara Falls": "Canada",
    "The Terracotta Army": "China",
    "The Kentucky Derby": "United States",
    "The Battle of Waterloo (Belgium)": "Belgium",
}

# Deliberately unplaceable -- open ocean or too vague to pin to a country.
DROP = {
    "the location where the Titanic sank",
    "Antarctica",
    "World War II",
    "British Overseas Territory",
    "United Kingdom Overseas Territory",
    "French Overseas Territory",
}

PAREN = re.compile(r"\(\s*(?:modern[- ]day\s+)?([^)]+?)\s*\)\s*$", re.I)


def resolve(location, countries):
    """Best-effort country for one archive location string, or None.

    `countries` is the set of country names the region table actually knows about, so a
    resolution that lands on something unmapped is treated as a failure rather than
    silently dropping the round into no region at all.
    """
    loc = location.strip()
    if loc in WHOLE:
        return WHOLE[loc]
    tail = loc.rsplit(",", 1)[-1].strip()
    if tail in DROP or loc in DROP:
        return None

    # "Babylon (modern day Iraq)" -> Iraq
    m = PAREN.search(tail) or PAREN.search(loc)
    if m:
        inner = m.group(1).strip()
        if inner in countries:
            return inner
        if inner in ALIAS and ALIAS[inner] in countries:
            return ALIAS[inner]

    for cand in (tail, ALIAS.get(tail), "United States" if tail in US_STATES else None):
        if cand and cand in countries:
            return cand
    return None


# ------------------------------------------------------------------ the 12 coarse
# Each fine region belongs to exactly one headline region. Kept explicit: deriving it
# from the names would quietly reshuffle the page the first time one was renamed.
COARSE = {
    "United States & Canada": "North America",
    "Mexico & Central America": "Central America & Caribbean",
    "Caribbean": "Central America & Caribbean",
    "Andes & Northern S. America": "South America",
    "Brazil & Southern Cone": "South America",
    "British Isles": "Western & Southern Europe",
    "Nordics": "Western & Southern Europe",
    "France & Low Countries": "Western & Southern Europe",
    "Germany & the Alps": "Western & Southern Europe",
    "Iberia": "Western & Southern Europe",
    "Italy": "Western & Southern Europe",
    "Central Europe": "Eastern Europe & Russia",
    "The Balkans & Greece": "Eastern Europe & Russia",
    "Baltics & Belarus": "Eastern Europe & Russia",
    "Ukraine & Moldova": "Eastern Europe & Russia",
    "Caucasus": "Eastern Europe & Russia",
    "Russia": "Eastern Europe & Russia",
    "Turkey & the Levant": "Middle East & North Africa",
    "Gulf, Iraq & Iran": "Middle East & North Africa",
    "North Africa": "Middle East & North Africa",
    "West Africa": "Sub-Saharan Africa",
    "Central Africa": "Sub-Saharan Africa",
    "East Africa & the Horn": "Sub-Saharan Africa",
    "Southern Africa": "Sub-Saharan Africa",
    "Central Asia": "Central Asia",
    "South Asia": "South Asia",
    "China & Mongolia": "East Asia",
    "Japan, Korea & Taiwan": "East Asia",
    "Southeast Asia": "Southeast Asia",
    "Australia & New Zealand": "Oceania",
    "Pacific Islands": "Oceania",
}

COARSE_ORDER = ["North America", "Central America & Caribbean", "South America",
                "Western & Southern Europe", "Eastern Europe & Russia",
                "Middle East & North Africa", "Sub-Saharan Africa", "Central Asia",
                "South Asia", "East Asia", "Southeast Asia", "Oceania"]

MIN_REG_ROUNDS = 6      # below this a player's regional delta is noise, so blank it
MIN_OWN_ROUNDS = 8      # a country needs this many rounds to be worth owning
OWN_SHARE = 0.60        # and you must have played this share of them to hold it


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def analyse(recs, archive, rc, players, labels=None):
    """Compute (REG, OWN, TERR, report) from the chat records and the archive.

    labels maps a fine region to its [lat, lon, flag] map-label position, carried from
    the existing page so the hand-placed labels survive.
    """
    countries = {c.strip() for v in rc.values() for c in v.split(",")}
    fine = {}
    for region, names in rc.items():
        for c in names.split(","):
            fine[c.strip()] = region

    by_date = collections.defaultdict(list)
    for r in recs:
        by_date[r["pz"].isoformat()].append(r)

    unresolved = collections.Counter()
    # accuracy samples, keyed by (scope, player)
    reg_acc = collections.defaultdict(lambda: collections.defaultdict(list))
    ter_acc = collections.defaultdict(lambda: collections.defaultdict(list))
    own_acc = collections.defaultdict(lambda: collections.defaultdict(list))
    reg_rounds, ter_rounds, own_rounds = collections.Counter(), collections.Counter(), collections.Counter()
    placed = dropped = 0

    for date, locs in archive.items():
        rows = by_date.get(date, [])
        if not rows:
            continue
        for i, loc in enumerate(locs[:5]):
            country = resolve(loc, countries)
            if not country or country not in fine:
                unresolved[loc.rsplit(",", 1)[-1].strip()] += 1
                dropped += 1
                continue
            region = fine[country]
            coarse = COARSE.get(region)
            placed += 1
            reg_rounds[coarse] += 1
            ter_rounds[region] += 1
            own_rounds[country] += 1
            for r in rows:
                if len(r["legs"]) != 5:
                    continue
                v = r["legs"][i]
                reg_acc[coarse][r["who"]].append(v)
                ter_acc[region][r["who"]].append(v)
                own_acc[country][r["who"]].append(v)

    overall = {p: mean([v for reg in reg_acc.values() for v in reg.get(p, [])])
               for p in players}

    # ---- REG: headline regions, each cell a player's delta from their own average
    REG = []
    for name in COARSE_ORDER:
        if not reg_rounds.get(name):
            continue
        allv = [v for p in players for v in reg_acc[name].get(p, [])]
        deltas = []
        for p in players:
            vals = reg_acc[name].get(p, [])
            deltas.append(round(mean(vals) - overall[p], 1)
                          if len(vals) >= MIN_REG_ROUNDS and overall[p] is not None else None)
        REG.append([name, reg_rounds[name], round(mean(allv), 1), deltas])

    # ---- OWN: countries seen often enough to be worth claiming
    OWN = []
    for country, n in own_rounds.most_common():
        if n < MIN_OWN_ROUNDS:
            continue
        ranked = sorted(((mean(v), p) for p, v in own_acc[country].items()
                         if len(v) >= n * OWN_SHARE), reverse=True)
        if len(ranked) < 2:
            continue
        OWN.append([country, n, ranked[0][1], round(ranked[0][0], 1),
                    ranked[1][1], round(ranked[1][0], 1)])

    # ---- TERR: the 30 map regions, with their hand-placed labels carried through
    TERR = []
    for region in rc:
        n = ter_rounds.get(region, 0)
        if not n:
            continue
        ranked = sorted(((mean(v), p) for p, v in ter_acc[region].items()
                         if len(v) >= n * OWN_SHARE), reverse=True)
        if len(ranked) < 2:
            continue
        allv = [v for p in players for v in ter_acc[region].get(p, [])]
        lab = (labels or {}).get(region, [0, 0, 0])
        TERR.append([region, n, round(mean(allv), 1),
                     ranked[0][1], round(ranked[0][0], 1),
                     ranked[1][1], round(ranked[1][0], 1),
                     lab[0], lab[1], lab[2]])

    report = {"placed": placed, "dropped": dropped,
              "unresolved": unresolved.most_common(),
              "regions": len(TERR), "countries": len(OWN)}
    return REG, OWN, TERR, report
