#!/usr/bin/python3

import asyncio
import os
from datetime import datetime, timezone, timedelta

import aiohttp

from github_stats import Stats

# ── Canvas ────────────────────────────────────────────────────────────────────
W       = 860
PAD     = 20
GAP     = 12

# Row 1: stats (left) + languages (right), both at y=20, height=310
CARD1_X  = 26
CARD1_Y  = 20
CARD1_W  = 400
CARD1_H  = 210

CARD2_X  = 440
CARD2_Y  = 20
CARD2_W  = 400
CARD2_H  = 210

# Row 2: contribution graph — starts at y = 20+310+12 = 342
GRAPH_Y  = CARD1_Y + CARD1_H + GAP   # 342
GRAPH_H  = 210
GRAPH_CX = 20
GRAPH_CW = 820

TOTAL_H  = GRAPH_Y + GRAPH_H + PAD   # 342+210+20 = 572

# ── Dracula palette ───────────────────────────────────────────────────────────
BG     = "#282a36"
CARD   = "#1e1f29"
BORDER = "#44475a"
PINK   = "#ff79c6"
PURPLE = "#bd93f9"
GREEN  = "#50fa7b"
CYAN   = "#8be9fd"
ORANGE = "#ffb86c"
FG     = "#f8f8f2"
MUTED  = "#6272a4"

LANG_COLORS = {
    "Python":"#3572A5","Rust":"#dea584","Go":"#00ADD8",
    "TypeScript":"#2b7489","JavaScript":"#f1e05a","C":"#555555",
    "C++":"#f34b7d","Shell":"#89e051","HTML":"#e34c26",
    "CSS":"#563d7c","Nix":"#7e7eff","Lua":"#000080",
    "Makefile":"#427819","TOML":"#9c4221",
}
def lc(n): return LANG_COLORS.get(n, "#8b949e")

def generate_output_folder():
    if not os.path.isdir("generated"):
        os.mkdir("generated")


# ── Animation helpers ─────────────────────────────────────────────────────────
def a_fade(delay, dur=500):
    return (f'<animate attributeName="opacity" from="0" to="1" '
            f'dur="{dur}ms" begin="{delay}ms" fill="freeze"/>')

def a_slide(delay, dx=-24, dur=450):
    return (f'<animate attributeName="opacity" from="0" to="1" '
            f'dur="{dur}ms" begin="{delay}ms" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" '
            f'from="{dx},0" to="0,0" dur="{dur}ms" begin="{delay}ms" '
            f'fill="freeze" additive="sum"/>')

def a_dash(delay, length, dur=500):
    return (f'<animate attributeName="stroke-dashoffset" '
            f'from="{length}" to="0" dur="{dur}ms" begin="{delay}ms" fill="freeze"/>')

def a_grow(delay, to_w, dur=450):
    return (f'<animate attributeName="width" from="0" to="{to_w}" '
            f'dur="{dur}ms" begin="{delay}ms" fill="freeze"/>')


# ── SVG defs ──────────────────────────────────────────────────────────────────
def svg_defs():
    return f"""<defs>
  <linearGradient id="g-bar" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="{PINK}"/>
    <stop offset="100%" stop-color="{PURPLE}"/>
  </linearGradient>
  <linearGradient id="g-area" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%"   stop-color="{PURPLE}" stop-opacity="0.45"/>
    <stop offset="100%" stop-color="{PURPLE}" stop-opacity="0.02"/>
  </linearGradient>
  <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
    <feGaussianBlur stdDeviation="2.5" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="glow-sm" x="-80%" y="-80%" width="260%" height="260%">
    <feGaussianBlur stdDeviation="1.5" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>"""


# ── Card shell ────────────────────────────────────────────────────────────────
def card(x, y, w, h):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{CARD}"/>'

def header(cx, cy, cw, text, color, delay=50, centered=False):
    div_len = cw - 32
    tx = (cx + cw // 2) if centered else (cx + 16)
    anchor = 'text-anchor="middle" ' if centered else ''
    title_y = cy + 26
    div_y   = cy + 42
    return (
        f'<g opacity="0" transform="translate(-20,0)">{a_slide(delay)}'
        f'<text x="{tx+10}" y="{title_y}" font-family="system-ui,sans-serif" '
        f'font-size="14" font-weight="700" fill="{color}" {anchor}letter-spacing="0.3">{text}</text>'
        f'</g>'
        f'<line x1="{cx+16}" y1="{div_y}" x2="{cx+16+div_len}" y2="{div_y}" '
        f'stroke="{BORDER}" stroke-width="0.8" '
        f'stroke-dasharray="{div_len}" stroke-dashoffset="{div_len}">'
        f'{a_dash(delay+80, div_len)}'
        f'</line>'
    )


# ── Icons ─────────────────────────────────────────────────────────────────────
ICONS = {
    "star":     "M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z",
    "fork":     "M6 3a2 2 0 100 4 2 2 0 000-4zm12 0a2 2 0 100 4 2 2 0 000-4zM6 9a2 2 0 00-2 2v1a2 2 0 002 2h1v2a2 2 0 002 2h6a2 2 0 002-2v-2h1a2 2 0 002-2v-1a2 2 0 00-2-2h-5V7h-2v2H6z",
    "commits":  "M11 4a8 8 0 100 16A8 8 0 0011 4zm0 2a6 6 0 110 12A6 6 0 0111 6zm0 2a4 4 0 100 8 4 4 0 000-8z",
    "eye":      "M12 5C7 5 2.73 8.11 1 12c1.73 3.89 6 7 11 7s9.27-3.11 11-7c-1.73-3.89-6-7-11-7zm0 12a5 5 0 110-10 5 5 0 010 10zm0-8a3 3 0 100 6 3 3 0 000-6z",
    "repo":     "M4 4h16v2H4zm0 4h16v2H4zm0 4h10v2H4zm0 4h10v2H4z",
    "flame":    "M12 2c0 6-6 8-6 14a6 6 0 0012 0c0-6-6-8-6-14zm0 16a2 2 0 01-2-2c0-2 2-4 2-6 0 2 2 4 2 6a2 2 0 01-2 2z",
    "bolt":     "M13 2L4 13h7l-2 9 11-12h-7z",
    "calendar": "M5 4h14a2 2 0 012 2v12a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2zm0 4v10h14V8H5zm2 2h4v3H7v-3zm6 0h4v3h-4v-3z",
}

def icon(name, x, y, color, delay=0, size=16):
    s = size / 24
    p = ICONS.get(name, "")
    return (f'<g transform="translate({x},{y}) scale({s:.3f})" opacity="0">'
            f'{a_fade(delay)}'
            f'<path d="{p}" fill="{color}"/>'
            f'</g>')


# ── 1. Stats card (with streak rows) ─────────────────────────────────────────
# 7 rows total: stars, forks, contribs, views, repos, current streak, longest streak
# rows spaced 32px from baseline 88, fitting in h=310

def build_stats_card(name, stars, forks, contribs, views, repos,
                     current_streak, longest_streak):
    cx, cy, cw, ch = CARD1_X, CARD1_Y, CARD1_W, CARD1_H
    rows = [
        ("star",     "Stars",           f"{stars:,}",          ORANGE,  120),
        # ("fork",     "Forks",           f"{forks:,}",           CYAN,   180),
        ("commits",  "Contributions",   f"{contribs:,}",        GREEN,   240),
        # ("eye",      "Profile Views",   f"{views:,}",           PURPLE,  300),
        # ("repo",     "Repositories",    f"{repos:,}",           PINK,    360),
        ("flame",    "Current Streak",  f"{current_streak}d",   ORANGE,  420),
        ("bolt",     "Longest Streak",  f"{longest_streak}d",   CYAN,    480),
    ]
    out = [
        card(cx, cy, cw, ch),
        header(cx, cy, cw, f"{name}'s Stats", PINK, delay=50),
    ]
    for i, (ico, label, val, color, delay) in enumerate(rows):
        icon_top  = cy + 74 + i * 32
        text_base = cy + 88 + i * 32
        icon_x    = cx + 16
        text_x    = cx + 58
        val_x     = cx + cw - 16
        out += [
            icon(ico, icon_x, icon_top, color, delay, size=16),
            f'<g opacity="0" transform="translate(-20,0)">{a_slide(delay)}'
            f'<text x="{text_x}" y="{text_base}" font-family="system-ui,sans-serif" '
            f'font-size="13" fill="{FG}">{label}</text>'
            f'<text x="{val_x}" y="{text_base}" font-family="system-ui,sans-serif" '
            f'font-size="13" font-weight="700" fill="{color}" text-anchor="end">{val}</text>'
            f'</g>',
        ]
    return "\n".join(out)


# ── 2. Languages card ─────────────────────────────────────────────────────────
# Segmented bar + legend grid (by commits), fits in w=400 h=310

def build_language_card(commit_scores):
    cx, cy, cw, ch = CARD2_X, CARD2_Y, CARD2_W, CARD2_H
    MAX   = 8
    BAR_H = 10
    ROW_H = 22
    COLS  = 2

    OX    = cx + 16
    P_W   = cw - 32          # 368
    col_w = P_W // COLS      # 184

    BAR_Y  = cy + 58         # just below divider at cy+42, some padding
    LEG_Y0 = BAR_Y + BAR_H + 20

    total  = sum(commit_scores.values()) or 1
    top    = sorted(commit_scores.items(), key=lambda t: t[1], reverse=True)[:MAX]

    out = [
        card(cx, cy, cw, ch),
        header(cx, cy, cw, "Languages (by Commits)", CYAN, delay=100),
        # background track for the bar
        f'<rect x="{OX}" y="{BAR_Y}" width="{P_W}" height="{BAR_H}" rx="5" fill="{BORDER}"/>',
    ]

    # segmented bar
    cur = OX
    for j, (name, val) in enumerate(top):
        seg_w = max(2, int((val / total) * P_W))
        delay = 200 + j * 55
        out.append(
            f'<rect x="{cur}" y="{BAR_Y}" width="0" height="{BAR_H}" rx="2" fill="{lc(name)}">'
            f'{a_grow(delay, seg_w)}'
            f'</rect>'
        )
        cur += seg_w

    # legend grid
    for idx, (name, val) in enumerate(top):
        pct   = val / total * 100
        col   = idx % COLS
        row   = idx // COLS
        lx    = OX + col * col_w
        ly    = LEG_Y0 + row * ROW_H
        delay = 600 + idx * 45
        out += [
            f'<g opacity="0">{a_fade(delay)}'
            f'<circle cx="{lx+6}" cy="{ly-5}" r="5" fill="{lc(name)}"/>'
            f'<text x="{lx+16}" y="{ly}" font-family="system-ui,sans-serif" '
            f'font-size="11" fill="{FG}">{name}</text>'
            f'<text x="{lx+col_w-4}" y="{ly}" font-family="system-ui,sans-serif" '
            f'font-size="11" fill="{GREEN}" text-anchor="end">{pct:.1f}%</text>'
            f'</g>',
        ]

    return "\n".join(out)


# ── 3. Contribution graph ─────────────────────────────────────────────────────
def build_graph(daily):
    cx, cy = GRAPH_CX, GRAPH_Y
    cw, ch = GRAPH_CW, GRAPH_H

    ML, MR, MT, MB = 28, 12, 52, 26
    pw     = cw - ML - MR
    ph     = ch - MT - MB
    plot_l = cx + ML
    base_y = cy + MT + ph

    today  = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=29)
    dmap   = {d["date"]: d["count"] for d in daily}
    pts    = [{"date": (cutoff + timedelta(days=i)).isoformat(),
               "count": dmap.get((cutoff + timedelta(days=i)).isoformat(), 0)}
              for i in range(30)]
    max_c  = max(p["count"] for p in pts) or 1

    def px(i): return cx + ML + i * pw / 29
    def py(v): return cy + MT + ph - (v / max_c) * ph

    coords = [(px(i), py(p["count"])) for i, p in enumerate(pts)]

    def smooth(c):
        d = f"M{c[0][0]:.1f},{c[0][1]:.1f}"
        for i in range(1, len(c)):
            x0, y0 = c[i-1]; x1, y1 = c[i]
            cp = (x0 + x1) / 2
            d += f" C{cp:.1f},{y0:.1f} {cp:.1f},{y1:.1f} {x1:.1f},{y1:.1f}"
        return d

    line_d   = smooth(coords)
    area_d   = line_d + f" L{coords[-1][0]:.1f},{base_y} L{coords[0][0]:.1f},{base_y} Z"
    path_len = int(pw * 1.2)

    out = [
        header(cx, cy, cw, "Contribution Graph — Last 30 Days", CYAN, delay=600),
    ]

    for frac in [0.25, 0.5, 0.75, 1.0]:
        gy = cy + MT + ph - frac * ph
        gv = round(max_c * frac)
        out += [
            f'<line x1="{plot_l}" y1="{gy:.1f}" x2="{cx+cw-MR}" y2="{gy:.1f}" '
            f'stroke="{BORDER}" stroke-width="0.6" stroke-dasharray="4,4"/>',
            f'<text x="{plot_l-4}" y="{gy+4:.1f}" font-family="system-ui,sans-serif" '
            f'font-size="9" fill="{MUTED}" text-anchor="end">{gv}</text>',
        ]

    out.append(
        f'<path d="{area_d}" fill="url(#g-area)" opacity="0">'
        f'{a_fade(700, 800)}'
        f'</path>'
    )
    out.append(
        f'<path d="{line_d}" fill="none" stroke="{PINK}" stroke-width="2.2" '
        f'stroke-linejoin="round" filter="url(#glow)" '
        f'stroke-dasharray="{path_len}" stroke-dashoffset="{path_len}">'
        f'{a_dash(750, path_len, 900)}'
        f'</path>'
    )

    for i, (x, y) in enumerate(coords):
        delay = 1650 + i * 22
        out += [
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{CARD}" '
            f'stroke="{GREEN}" stroke-width="2" filter="url(#glow-sm)" opacity="0">'
            f'{a_fade(delay, 180)}</circle>',
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2" fill="{GREEN}" opacity="0">'
            f'{a_fade(delay, 180)}</circle>',
        ]

    label_y = base_y + 18
    for i, p in enumerate(pts):
        if i % 5 == 0 or i == 29:
            out.append(
                f'<text x="{px(i):.1f}" y="{label_y}" font-family="system-ui,sans-serif" '
                f'font-size="9" fill="{MUTED}" text-anchor="middle">{p["date"][5:]}</text>'
            )

    return "\n".join(out)


# ── Assemble ──────────────────────────────────────────────────────────────────
async def generate_combined_svg(s: Stats) -> None:
    name           = await s.name
    stars          = await s.stargazers
    forks          = await s.forks
    contribs       = await s.total_contributions
    views          = await s.views
    repos          = len(await s.repos)
    commit_l       = await s.languages_by_commits
    daily          = await s.daily_contributions
    streak         = await s.streak_stats

    current_streak = streak["current_streak"]
    longest_streak = streak["longest_streak"]

    parts = [
        f'<svg width="{W}" height="{TOTAL_H}" viewBox="0 0 {W} {TOTAL_H}" '
        f'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">',
        f'<rect width="{W}" height="{TOTAL_H}" fill="{BG}" rx="12"/>',
        svg_defs(),
        build_stats_card(name, stars, forks, contribs, views, repos,
                         current_streak, longest_streak),
        build_language_card(commit_l),
        build_graph(daily),
        '</svg>',
    ]

    generate_output_folder()
    path = "generated/github-stats.svg"
    with open(path, "w") as f:
        f.write("\n".join(parts))
    print(f"✓ {path}  ({W}×{TOTAL_H})")


# ── Main ──────────────────────────────────────────────────────────────────────
async def main() -> None:
    token = os.getenv("ACCESS_TOKEN")
    if not token: raise Exception("ACCESS_TOKEN required")
    user  = os.getenv("GITHUB_ACTOR")
    if not user: raise RuntimeError("GITHUB_ACTOR required")

    ex_repos = os.getenv("EXCLUDED")
    ex_langs = os.getenv("EXCLUDED_LANGS")
    raw_fork = os.getenv("EXCLUDE_FORKED_REPOS", "")

    async with aiohttp.ClientSession() as session:
        s = Stats(user, token, session,
                  exclude_repos={x.strip() for x in ex_repos.split(",")} if ex_repos else None,
                  exclude_langs={x.strip() for x in ex_langs.split(",")} if ex_langs else None,
                  ignore_forked_repos=bool(raw_fork) and raw_fork.strip().lower() != "false")
        await generate_combined_svg(s)

if __name__ == "__main__":
    asyncio.run(main())
