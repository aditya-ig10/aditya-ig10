#!/usr/bin/env python3
"""Fetches contribution data from GitHub and writes data/github-stats.json.

Env: GH_TOKEN (required), GH_LOGIN (default aditya-ig10).
The default Actions token sees public contributions only. To include private ones,
add a personal access token with the read:user scope as a repo secret named STATS_TOKEN.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

LOGIN = os.environ.get("GH_LOGIN", "aditya-ig10")
TOKEN = os.environ["GH_TOKEN"]
OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "github-stats.json"))


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "profile-stats"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    return data["data"]


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


now = dt.datetime.now(dt.timezone.utc)
today = now.date()

meta = gql("query($l:String!){user(login:$l){createdAt repositories(ownerAffiliations:OWNER,privacy:PUBLIC){totalCount}}}",
           {"l": LOGIN})["user"]
created = dt.datetime.fromisoformat(meta["createdAt"].replace("Z", "+00:00"))

CAL = """query($l:String!,$from:DateTime!,$to:DateTime!){user(login:$l){
  contributionsCollection(from:$from,to:$to){contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""

counts = {}
start = created
while start < now:
    end = min(start + dt.timedelta(days=360), now)  # the API allows at most one year per request
    cal = gql(CAL, {"l": LOGIN, "from": iso(start), "to": iso(end)})["user"]["contributionsCollection"]["contributionCalendar"]
    for week in cal["weeks"]:
        for day in week["contributionDays"]:
            d = dt.date.fromisoformat(day["date"])
            if d <= today:
                counts[d] = max(counts.get(d, 0), day["contributionCount"])
    start = end + dt.timedelta(days=1)

first = min(counts)
days = [first + dt.timedelta(days=i) for i in range((today - first).days + 1)]
n = lambda d: counts.get(d, 0)

# longest streak
best_len, best_end, run = 0, None, 0
for d in days:
    run = run + 1 if n(d) > 0 else 0
    if run > best_len:
        best_len, best_end = run, d
longest = {"n": best_len,
           "start": (best_end - dt.timedelta(days=best_len - 1)).isoformat() if best_len else today.isoformat(),
           "end": best_end.isoformat() if best_len else today.isoformat()}

# current streak (today may still be empty, so the streak can end yesterday)
d = today if n(today) > 0 else today - dt.timedelta(days=1)
cur_end, cur_len = d, 0
while n(d) > 0:
    cur_len += 1
    d -= dt.timedelta(days=1)
current = {"n": cur_len, "start": (cur_end - dt.timedelta(days=cur_len - 1)).isoformat() if cur_len else today.isoformat(),
           "end": cur_end.isoformat() if cur_len else today.isoformat()}

weekly = []
for i in range(52):
    wend = today - dt.timedelta(days=7 * (51 - i))
    wstart = wend - dt.timedelta(days=6)
    weekly.append({"w": wstart.isoformat(), "n": sum(n(wstart + dt.timedelta(days=j)) for j in range(7))})

year_days = [today - dt.timedelta(days=i) for i in range(364)]
best_day = max(days, key=n)
stats = {
    "sample": False,
    "login": LOGIN,
    "generated": iso(now),
    "since": created.year,
    "repos": meta["repositories"]["totalCount"],
    "total_all": sum(counts.values()),
    "total_year": sum(n(x) for x in year_days),
    "active_days_year": sum(1 for x in year_days if n(x) > 0),
    "current": current,
    "longest": longest,
    "best_day": {"n": n(best_day), "date": best_day.isoformat()},
    "last7": [n(today - dt.timedelta(days=6 - i)) for i in range(7)],
    "weekly": weekly,
}
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(stats, f, indent=1)
print(f"{LOGIN}: {stats['total_all']} contributions, current streak {current['n']}, longest {longest['n']}")