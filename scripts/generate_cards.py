#!/usr/bin/env python3
"""Genera las tarjetas SVG del perfil (stats, top langs, pins de repos).

Corre con GITHUB_TOKEN en el env (en Actions viene solo; local: gh auth token).
Escribe los SVG en assets/. Sin dependencias externas.
"""
import json
import os
import sys
import urllib.request
from html import escape

LOGIN = "JuanMoisio"
PINNED = ["KipuBankV4", "ESP32Proyects", "MQTT_ESP32_SERVER", "ServerPQ"]
OUT = os.path.join(os.path.dirname(__file__), "..", "assets")

# Paleta tokyonight
BG = "#1a1b27"
TITLE = "#70a5fd"
LABEL = "#c0caf5"
VALUE = "#38bdae"
MUTED = "#565f89"
FONT = "font-family=\"'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif\""

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar { totalContributions }
    }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
      totalCount
      nodes {
        name
        description
        isFork
        stargazerCount
        forkCount
        primaryLanguage { name color }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def gql(query, variables):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("Falta GITHUB_TOKEN en el entorno")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        sys.exit(f"GraphQL error: {body['errors']}")
    return body["data"]


def card(width, height, title, inner):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
  <rect width="{width}" height="{height}" rx="10" fill="{BG}"/>
  <text x="24" y="34" {FONT} font-size="16" font-weight="600" fill="{TITLE}">{escape(title)}</text>
{inner}
</svg>
"""


def stats_card(u):
    cal = u["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    commits = u["contributionsCollection"]["totalCommitContributions"]
    stars = sum(n["stargazerCount"] for n in u["repositories"]["nodes"])
    rows = [
        ("Contribuciones (último año)", cal),
        ("Commits (último año)", commits),
        ("Pull requests", u["pullRequests"]["totalCount"]),
        ("Issues", u["issues"]["totalCount"]),
        ("Repos públicos", u["repositories"]["totalCount"]),
        ("Stars", stars),
        ("Followers", u["followers"]["totalCount"]),
    ]
    rows = [(l, v) for l, v in rows if v]  # sin filas en cero
    inner = []
    y = 64
    for label, value in rows:
        inner.append(f'  <text x="24" y="{y}" {FONT} font-size="13" fill="{LABEL}">{escape(label)}:</text>')
        inner.append(f'  <text x="330" y="{y}" {FONT} font-size="13" font-weight="700" fill="{VALUE}">{value}</text>')
        y += 24
    return card(400, y - 24 + 20, "Stats de JuanMoisio", "\n".join(inner))


def top_langs_card(u, top_n=8):
    totals = {}
    colors = {}
    for repo in u["repositories"]["nodes"]:
        if repo["isFork"]:
            continue
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            totals[name] = totals.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or MUTED
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])[:top_n]
    total = sum(v for _, v in ranked) or 1
    inner = []
    # barra apilada
    x, bar_w = 24.0, 352.0
    for name, size in ranked:
        w = bar_w * size / total
        inner.append(f'  <rect x="{x:.1f}" y="52" width="{max(w, 2):.1f}" height="8" rx="2" fill="{colors[name]}"/>')
        x += w
    # lista en dos columnas
    y0 = 84
    for i, (name, size) in enumerate(ranked):
        col, row = i % 2, i // 2
        lx, ly = 24 + col * 190, y0 + row * 24
        pct = 100.0 * size / total
        inner.append(f'  <circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{colors[name]}"/>')
        inner.append(f'  <text x="{lx + 18}" y="{ly}" {FONT} font-size="12" fill="{LABEL}">{escape(name)} <tspan fill="{MUTED}">{pct:.1f}%</tspan></text>')
    height = y0 + ((len(ranked) + 1) // 2) * 24 + 4
    return card(400, height, "Lenguajes más usados (repos públicos)", "\n".join(inner))


def wrap(text, limit=52, max_lines=2):
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > limit:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
        else:
            cur = f"{cur} {w}".strip()
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(words) and sum(len(l.split()) for l in lines) < len(words):
        lines[-1] = lines[-1][: limit - 1] + "…"
    return lines or [" "]


def pin_card(repo):
    lines = wrap(repo["description"])
    inner = [
        f'  <text x="24" y="{62 + i * 18}" {FONT} font-size="12" fill="{LABEL}">{escape(l)}</text>'
        for i, l in enumerate(lines)
    ]
    y = 62 + len(lines) * 18 + 8
    lang = repo["primaryLanguage"] or {"name": "—", "color": MUTED}
    inner.append(f'  <circle cx="29" cy="{y - 4}" r="5" fill="{lang["color"] or MUTED}"/>')
    inner.append(f'  <text x="42" y="{y}" {FONT} font-size="12" fill="{MUTED}">{escape(lang["name"])}</text>')
    inner.append(f'  <text x="160" y="{y}" {FONT} font-size="12" fill="{MUTED}">★ {repo["stargazerCount"]}   ⑂ {repo["forkCount"]}</text>')
    return card(400, y + 18, repo["name"], "\n".join(inner))


def main():
    u = gql(QUERY, {"login": LOGIN})["user"]
    os.makedirs(OUT, exist_ok=True)
    out = {
        "stats.svg": stats_card(u),
        "top-langs.svg": top_langs_card(u),
    }
    by_name = {n["name"]: n for n in u["repositories"]["nodes"]}
    for name in PINNED:
        if name in by_name:
            out[f"pin-{name}.svg"] = pin_card(by_name[name])
    for fname, svg in out.items():
        with open(os.path.join(OUT, fname), "w") as f:
            f.write(svg)
        print(f"OK {fname}")


if __name__ == "__main__":
    main()
