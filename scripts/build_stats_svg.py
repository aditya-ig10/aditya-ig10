#!/usr/bin/env python3
"""Renders data/github-stats.json into assets/stats-{light,dark}.svg.

Owns all geometry for the stats dashboard; the checked-in SVGs are its output,
so the GitHub Action only needs this script plus fetch-github-stats.py.
Stdlib only.
"""
import json
import os
import re
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
FILES = ["assets/stats-light.svg", "assets/stats-dark.svg"]
PALETTES = {
    "light": {"bg": "#F3F7F7", "ink": "#0C2430", "muted": "#52707A", "teal": "#0A8F85",
              "purple": "#6A4CE0", "orange": "#F97316", "amber": "#FBBF24",
              "blue": "#2563C9", "pink": "#D63A6A"},
    "dark": {"bg": "#0A1A21", "ink": "#E9F1F2", "muted": "#8FA8B0", "teal": "#3FD6C8",
             "purple": "#B49CFF", "orange": "#FB923C", "amber": "#FCD34D",
             "blue": "#7FB8FF", "pink": "#FF8FAB"},
}


def fmt(n):
    return f"{n:,}"


def fmt_day(iso):
    return date.fromisoformat(iso).strftime("%b %-d, %Y")


def fmt_range(a, b):
    if a == b:
        return fmt_day(a)
    da, db = date.fromisoformat(a), date.fromisoformat(b)
    if (da.year, da.month) == (db.year, db.month):
        return f'{da.strftime("%b %-d")} to {db.strftime("%-d")}, {db.year}'
    return f"{fmt_day(a)[:-6]} to {fmt_day(b)}"


def curve(pts):
    """Catmull-Rom through pts -> smooth SVG cubic path."""
    d = [f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"]
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else pts[i + 1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}")
    return " ".join(d)


def build(s, d, P):
    # ---- activity card (52-week line) ----
    weekly = d["weekly"]
    mx = max(w["n"] for w in weekly) or 1
    busy_i = max(range(len(weekly)), key=lambda i: weekly[i]["n"])
    step = 456 / (len(weekly) - 1)
    pts = [(24 + i * step, 138 - (8 + 64 * w["n"] / mx)) for i, w in enumerate(weekly)]
    path = curve(pts)
    s = re.sub(r'(<path class="ar" fill="url\(#area\)" d=")[^"]+(</path>)',
               lambda m: m.group(1) + path + " L480 138 L24 138 Z" + m.group(2), s)
    s = re.sub(r'(<path class="ln" pathLength="1" fill="none"[^>]* d=")[^"]+(")',
               lambda m: m.group(1) + path + m.group(2), s)
    bx, by = pts[busy_i]
    s = re.sub(r'<circle cx="[\d.]+" cy="[\d.]+" r="4" fill="[^"]+" stroke="[^"]+" stroke-width="2"/>',
               f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="4" fill="{P["bg"]}" stroke="{P["teal"]}" stroke-width="2"/>', s)
    s = re.sub(r'(<text x=")[\d.]+(" y="56\.0" text-anchor="middle" font-size="11" fill="[^"]+">)[^<]*(</text>)',
               lambda m: m.group(1) + f"{max(100, min(bx, 430)):.0f}" + m.group(2) + f"busiest week: {weekly[busy_i]['n']}" + m.group(3), s)
    ex, ey = pts[-1]
    s = re.sub(r'(<g class="en"><circle cx=")[\d.]+(" cy=")[\d.]+(" r="9")',
               lambda m: m.group(1) + f"{ex:.1f}" + m.group(2) + f"{ey:.1f}" + m.group(3), s)
    s = re.sub(r'(<circle cx=")[\d.]+(" cy=")[\d.]+(" r="4\.5" fill=")',
               lambda m: m.group(1) + f"{ex:.1f}" + m.group(2) + f"{ey:.1f}" + m.group(3), s)
    # month labels along the baseline
    # month labels along the baseline: one per month, dropped when too close together
    labels = []
    last_x = -99
    for i, w in enumerate(weekly):
        m = w["w"][:7]
        if not labels or labels[-1][0] != m:
            x = 24 + i * step
            if x - last_x >= 46:
                labels.append((m, x))
                last_x = x
    block = "".join(
        f'<text x="{x:.1f}" y="156" text-anchor="middle" font-size="11" fill="{P["muted"]}">'
        f'{date(int(m[:4]), int(m[5:]), 1).strftime("%b")}</text>'
        for m, x in labels
    )
    s = re.sub(r'<text x="[\d.]+" y="156" text-anchor="middle" font-size="11" fill="[^"]+">[^<]*</text>', "", s)
    s = s.replace('<text class="serif" x="24" y="196"', block + '<text class="serif" x="24" y="196"')
    s = re.sub(r'(<text class="serif" x="24" y="196" font-size="24" fill="[^"]+">)[^<]*(</text>)',
               lambda m: m.group(1) + fmt(d["total_year"]) + m.group(2), s)

    # ---- current streak card ----
    cur = d["current"]
    s = re.sub(r'(<path fill=")[^"]+(" d="M24 2C26 14 40 20)',
               lambda m: m.group(1) + P["orange"] + m.group(2), s)
    s = re.sub(r'(<path fill=")[^"]+(" fill-opacity="\.85" d="M24 26C26 32)',
               lambda m: m.group(1) + P["amber"] + m.group(2), s)
    s = re.sub(r'(<text class="serif" x="116" y="112" font-size="56" fill="[^"]+">)[^<]*(</text>)',
               lambda m: m.group(1) + str(cur["n"]) + m.group(2), s)
    days_x = 116 + 30 * len(str(cur["n"])) + 6
    s = re.sub(r'<text x="154" y="112" font-size="16" fill="[^"]+">days</text>',
               f'<text x="{days_x}" y="112" font-size="16" fill="{P["muted"]}">days</text>', s)
    s = re.sub(r'(<text x="116" y="134" text-anchor="start" font-size="12" fill="[^"]+">)[^<]*(</text>)',
               lambda m: m.group(1) + fmt_range(cur["start"], cur["end"]) + m.group(2), s)
    counter = {"i": 0}

    def dot(m):
        i = counter["i"]
        counter["i"] += 1
        active = d["last7"][i] > 0
        fill = P["orange"] if active else P["muted"]
        op = "" if active else ' fill-opacity=".2"'
        return f'<circle class="dt" cx="{31 + 28 * i}" cy="176" r="8" fill="{fill}"{op} style="animation-delay:{i * 0.2:.1f}s"/>'

    s = re.sub(r'<circle class="dt" cx="\d+" cy="176" r="8" fill="[^"]+"(?: fill-opacity="[^"]+")? style="animation-delay:[\d.]+s"/>', dot, s)
    active7 = sum(1 for n in d["last7"] if n > 0)
    s = re.sub(r'(<text x="24" y="202" text-anchor="start" font-size="11" fill="[^"]+">)[^<]*(</text>)',
               lambda m: m.group(1) + f"{active7} of 7 days active" + m.group(2), s)

    # ---- longest streak card ----
    lo = d["longest"]
    s = re.sub(r'(<text class="serif" x="24" y="96" font-size="48" fill="[^"]+">)[^<]*(</text>)',
               lambda m: m.group(1) + str(lo["n"]) + m.group(2), s)
    s = re.sub(r'(<text x="24" y="118" text-anchor="start" font-size="12" fill="[^"]+">)[^<]*(</text>)',
               lambda m: m.group(1) + fmt_range(lo["start"], lo["end"]) + m.group(2), s)
    # ---- longest streak card: closed-loop medallion ----
    s = re.sub(r'(<circle class="ring" cx="148" cy="116" r="44" fill="none" stroke=")[^"]+(" stroke-width="3\.5" pathLength="360"/>)',
               lambda m: m.group(1) + P["purple"] + m.group(2), s)
    s = re.sub(r'(<circle class="orb-dot" cx="192" cy="116" r="3" fill=")[^"]+(" stroke=")[^"]+(" stroke-width="1\.5"/>)',
               lambda m: m.group(1) + P["orange"] + m.group(2) + P["bg"] + m.group(3), s)
    s = re.sub(r'(<text class="serif" x="148" y="126" text-anchor="middle" font-size="44" fill="[^"]+">)[^<]*(</text>)',
               lambda m: m.group(1) + str(lo["n"]) + m.group(2), s)
    s = re.sub(r'(<text x="148" y="184" text-anchor="middle" font-size="11" fill="[^"]+">)[^<]*(</text>)',
               lambda m: m.group(1) + fmt_range(lo["start"], lo["end"]) + m.group(2), s)

    # ---- all-time card ----
    s = re.sub(r'(<text class="serif" x="24" y="86" font-size="44" fill="[^"]+">)[^<]*(</text>)',
               lambda m: m.group(1) + fmt(d["total_all"]) + m.group(2), s)
    s = re.sub(r'(<text x="24" y="106" text-anchor="start" font-size="13" fill="[^"]+">)[^<]*(</text>)',
               lambda m: m.group(1) + f'since {d["since"]}' + m.group(2), s)
    tail = weekly[-12:]
    mx12 = max(x["n"] for x in tail) or 1
    counter["i"] = 0

    def bar(m):
        i = counter["i"]
        counter["i"] += 1
        v = tail[i]["n"]
        h = 8 + 40 * v / mx12
        return (f'<rect class="br" x="{27 + i * 20.5:.1f}" y="{174 - h:.1f}" width="14" height="{h:.1f}"'
                f' rx="4" fill="{P["blue"]}" fill-opacity="{0.45 + 0.05 * i:.2f}"'
                f' style="animation-delay:{i * 0.05:.2f}s"/>')

    s = re.sub(r'<rect class="br" x="[\d.]+" y="[\d.]+" width="14" height="[\d.]+" rx="4" fill="[^"]+"'
               r' fill-opacity="[\d.]+" style="animation-delay:[\d.]+s"/>', bar, s)

    # ---- right-hand pills ----
    s = re.sub(r'(<g transform="translate\(648 250\)">.*?<text class="serif" x="16" y="40" font-size="26" fill="[^"]+">)[^<]*(</text>)',
               lambda m: m.group(1) + str(d["best_day"]["n"]) + m.group(2), s, flags=re.S)
    s = re.sub(r'(<g transform="translate\(648 250\)">.*?<text x="78" y="44" text-anchor="start" font-size="11" fill="[^"]+">)[^<]*(</text>)',
               lambda m: m.group(1) + fmt_day(d["best_day"]["date"]) + m.group(2), s, flags=re.S)
    s = re.sub(r'(<g transform="translate\(648 318\)">.*?<text class="serif" x="16" y="40" font-size="26" fill="[^"]+">)[^<]*(</text>)',
               lambda m: m.group(1) + str(d["active_days_year"]) + m.group(2), s, flags=re.S)
    s = re.sub(r'(<g transform="translate\(648 386\)">.*?<text class="serif" x="16" y="40" font-size="26" fill="[^"]+">)[^<]*(</text>)',
               lambda m: m.group(1) + str(d["prs"]) + m.group(2), s, flags=re.S)

    # ---- desc + preview footer ----
    desc = (f"Animated GitHub stats: activity over the last 52 weeks, current streak of "
            f"{cur['n']} days, longest streak of {lo['n']} days and {fmt(d['total_all'])} contributions all-time.")
    s = re.sub(r'(<desc id="d">)[^<]*(</desc>)', lambda m: m.group(1) + desc + m.group(2), s)
    if not d.get("sample"):
        s = re.sub(r'<text x="876" y="463"[^>]*>[^<]*</text>', "", s)
    return s


def main():
    data = json.load(open(os.path.join(ROOT, "..", "data", "github-stats.json")))
    for f in FILES:
        s = open(f).read()
        variant = "light" if PALETTES["light"]["bg"] in s else "dark"
        s = build(s, data, PALETTES[variant])
        s = s.replace(' xmlns:c2pa="http://c2pa.org/manifest"', "")
        s = re.sub(r"<metadata>.*?</metadata>", "", s, flags=re.S)
        open(f, "w").write(s)
    print(f'rendered: {fmt(data["total_all"])} all-time · {data["current"]["n"]}d current streak · '
          f'{data["longest"]["n"]}d longest · {data["repos"]} repos')


if __name__ == "__main__":
    main()
