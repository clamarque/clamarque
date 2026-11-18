"""Generate README SVG assets in the "Cappuccino" style of clamarque.github.io.

Fonts are subset and embedded as base64 woff2 so GitHub renders them
(external font loading is blocked inside README images).

Usage:
    python3 -m venv .venv && .venv/bin/pip install fonttools brotli
    .venv/bin/python scripts/build-assets.py        # writes ./assets/*.svg
"""
import base64, io, os, sys
from html import escape
from fontTools.ttLib import TTFont
from fontTools import subset

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "assets")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- palette
BG, SURFACE, CREAM = "#f5eee3", "#fbf7f0", "#eadcc8"
ESPRESSO, TEXT2, MUTED = "#2a1e17", "#4a3a2f", "#6e5a4b"
LINE, LINE_STRONG = "#e3d6c4", "#d5c4ae"
CARAMEL, CARAMEL_LIGHT = "#9a6438", "#d9b48a"
MUTED_DARK, LINE_DARK, AVAILABLE = "#c8b6a3", "#4a3a2f", "#4f7a4a"

W = 1000
PAD = 56

# ---------------------------------------------------------------- fonts
FONTS = {
    # key: (file, css family, weight, style)
    "serif": ("Fraunces-400.ttf", "Fraunces", 400, "normal"),
    "serif-i": ("Fraunces-400i.ttf", "Fraunces", 400, "italic"),
    "sans": ("Manrope-400.ttf", "Manrope", 400, "normal"),
    "sans-m": ("Manrope-500.ttf", "Manrope", 500, "normal"),
    "sans-b": ("Manrope-600.ttf", "Manrope", 600, "normal"),
    "mono": ("JetBrainsMono-400.ttf", "JetBrains Mono", 400, "normal"),
    "mono-m": ("JetBrainsMono-500.ttf", "JetBrains Mono", 500, "normal"),
}
FALLBACK = {"serif": "Georgia, serif", "sans": "system-ui, sans-serif", "mono": "ui-monospace, monospace"}
_tt = {k: TTFont(os.path.join(FONT_DIR, v[0])) for k, v in FONTS.items()}


def measure(text, font, size, ls=0.0):
    tt = _tt[font]
    cmap, hmtx = tt.getBestCmap(), tt["hmtx"]
    upm = tt["head"].unitsPerEm
    w = 0
    for ch in text:
        g = cmap.get(ord(ch)) or cmap.get(ord("?"))
        w += hmtx[g][0]
    return w * size / upm + ls * len(text)


class Svg:
    def __init__(self, w, h, title):
        self.w, self.h, self.title = w, h, title
        self.parts = []
        self.used = {}  # font key -> set(chars)

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, font, size, fill, ls=0.0, anchor="start", upper=False):
        if upper:
            s = s.upper()
        self.used.setdefault(font, set()).update(s)
        fam, _, wt, st = FONTS[font][1:] if False else (None, None, FONTS[font][2], FONTS[font][3])
        cls = font.split("-")[0]
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        l = f' letter-spacing="{ls:.2f}"' if ls else ""
        self.add(
            f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" font-size="{size}" font-weight="{wt}"'
            f' font-style="{st}" fill="{fill}"{l}{a}>{escape(s)}</text>'
        )
        return measure(s, font, size, ls)

    def runs(self, x, y, runs, size, ls_em=0.0):
        """runs: list of (text, font, fill). Draws inline, returns width."""
        cx = x
        for s, font, fill in runs:
            ls = ls_em * size
            cx += self.text(cx, y, s, font, size, fill, ls=ls)
        return cx - x

    def render(self, path):
        css = []
        for key, chars in self.used.items():
            file, fam, wt, st = FONTS[key]
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern", "liga", "lnum"]
            ft = TTFont(os.path.join(FONT_DIR, file))
            sub = subset.Subsetter(opts)
            sub.populate(text="".join(sorted(chars)) + " ")
            sub.subset(ft)
            buf = io.BytesIO()
            ft.flavor = "woff2"
            ft.save(buf)
            b64 = base64.b64encode(buf.getvalue()).decode()
            css.append(
                f'@font-face{{font-family:"{fam}";font-weight:{wt};font-style:{st};'
                f'src:url(data:font/woff2;base64,{b64}) format("woff2")}}'
            )
        css.append('text{white-space:pre}')
        css.append(f'.serif{{font-family:"Fraunces",{FALLBACK["serif"]}}}')
        css.append(f'.sans{{font-family:"Manrope",{FALLBACK["sans"]}}}')
        css.append(f'.mono{{font-family:"JetBrains Mono",{FALLBACK["mono"]}}}')
        body = "\n".join(self.parts)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" xml:space="preserve" role="img" aria-label="{escape(self.title)}">\n'
            f"<title>{escape(self.title)}</title>\n<style>{''.join(css)}</style>\n{body}\n</svg>\n"
        )
        with open(os.path.join(OUT, path), "w") as f:
            f.write(svg)
        print(f"{path}: {len(svg)//1024} KB")


def wrap(words, size, maxw, ls=0.0):
    """words: list of (word, font, fill). Returns lines of runs."""
    lines, cur, curw = [], [], 0.0
    for word, font, fill in words:
        piece = word if not cur else " " + word
        pw = measure(piece, font, size, ls)
        if cur and curw + pw > maxw:
            lines.append(cur)
            cur, curw = [(word, font, fill)], measure(word, font, size, ls)
        else:
            cur.append((piece, font, fill))
            curw += pw
    if cur:
        lines.append(cur)
    return lines


def words(text, font, fill):
    return [(w, font, fill) for w in text.split()]


def panel(svg, x, y, w, h, fill=BG, stroke=LINE, r=20):
    s = f' stroke="{stroke}" stroke-width="1"' if stroke else ""
    svg.add(f'<rect x="{x+0.5}" y="{y+0.5}" width="{w-1}" height="{h-1}" rx="{r}" fill="{fill}"{s}/>')


def rule(svg, x1, x2, y, color=LINE):
    svg.add(f'<line x1="{x1}" y1="{y+0.5}" x2="{x2}" y2="{y+0.5}" stroke="{color}" stroke-width="1"/>')


def eyebrow(svg, x, y, s, fill=CARAMEL):
    return svg.text(x, y, s, "mono", 12, fill, ls=12 * 0.12, upper=True)


def para(svg, x, y, ws, size, maxw, lh):
    lines = wrap(ws, size, maxw)
    for i, line in enumerate(lines):
        svg.runs(x, y + i * lh, line, size)
    return len(lines) * lh


# ================================================================ hero
def hero():
    H = 500
    s = Svg(W, H, "Charles Lamarque — Je conçois des produits web rapides, fiables et beaux.")
    panel(s, 0, 0, W, H)
    y = PAD + 18
    s.add(f'<circle cx="{PAD+3.5}" cy="{y-4}" r="3.5" fill="{AVAILABLE}"/>')
    x = PAD + 17
    x += s.text(x, y, "Disponible en freelance", "mono", 12, TEXT2, ls=1.44, upper=True)
    rule(s, x + 14, x + 54, y - 5, LINE_STRONG)
    s.text(x + 68, y, "10+ ans en ESN · Lille", "mono", 12, TEXT2, ls=1.44, upper=True)
    s.text(W - PAD, y, "FR · EN", "mono", 12, MUTED, ls=1.44, anchor="end", upper=True)

    size, lh = 76, 76 * 0.98
    ls = -0.03
    lines = [
        [("Je conçois des produits", "serif", ESPRESSO)],
        [("web ", "serif", ESPRESSO), ("rapides, fiables", "serif-i", CARAMEL)],
        [("et beaux.", "serif", ESPRESSO)],
    ]
    ty = y + 40 + size * 0.8
    for i, ln in enumerate(lines):
        s.runs(PAD - 3, ty + i * lh, ln, size, ls_em=ls)

    ry = ty + 2 * lh + 40
    rule(s, PAD, W - PAD, ry)
    body = (
        words("Je suis Charles, développeur full-stack JavaScript.", "sans", TEXT2)
        + words("Plus de dix ans", "sans-b", ESPRESSO)
        + words("à livrer pour le retail & l'e-commerce, l'immobilier, l'énergie et le transport — de l'idée à la production, sans superflu.", "sans", TEXT2)
    )
    para(s, PAD, ry + 42, body, 17, 500, 28)

    # signature block, right
    sx = W - PAD
    s.text(sx, ry + 50, "Charles Lamarque", "serif-i", 30, ESPRESSO, ls=-0.6, anchor="end")
    s.text(sx, ry + 80, "Full-stack JS · TypeScript", "mono", 12, CARAMEL, ls=1.44, anchor="end", upper=True)
    s.render("hero.svg")


# ================================================================ stats
def stats():
    H = 150
    s = Svg(W, H, "10+ années d'expérience · 20+ projets livrés · 126 étoiles GitHub · ∞ cappuccinos par jour")
    panel(s, 0, 0, W, H, fill=CREAM, stroke=None)
    items = [("10", "+", "Années d'expérience"), ("20", "+", "Projets livrés"),
             ("126", "", "Étoiles GitHub"), ("∞", "", "Cappuccinos par jour")]
    colw = (W - 2 * PAD) / 4
    for i, (n, em, label) in enumerate(items):
        x = PAD + i * colw + (32 if i else 0)
        if i:
            s.add(f'<line x1="{PAD+i*colw+0.5}" y1="32" x2="{PAD+i*colw+0.5}" y2="{H-32}" stroke="{LINE_STRONG}"/>')
        font = "sans" if n == "∞" else "serif"
        w = s.text(x, 84, n, font, 54, ESPRESSO, ls=-1.6)
        if em:
            s.text(x + w, 84, em, "serif-i", 54, CARAMEL, ls=-1.6)
        s.text(x, 114, label, "sans", 15, TEXT2)
    s.render("stats.svg")


# ================================================================ section head
def section_head(fname, num, title_runs, lead, alt):
    lead_w = 380
    lines = wrap(words(lead, "sans", TEXT2), 17, lead_w)
    H = max(200, PAD * 2 + len(lines) * 28 + 40)
    s = Svg(W, H, alt)
    panel(s, 0, 0, W, H)
    eyebrow(s, PAD, PAD + 12, num)
    s.runs(PAD - 2, PAD + 92, title_runs, 60, ls_em=-0.03)
    ly = PAD + 92 - (len(lines) - 1) * 28
    for i, ln in enumerate(lines):
        s.runs(W - PAD - lead_w, ly + i * 28, ln, 17)
    return s, H


# ================================================================ about + now
def about():
    s0 = None
    body = ("Dix ans de conseil m'ont appris que livrer du code ne suffit pas. Je pense produit, "
            "je me soucie du résultat business et de la maintenabilité long terme — comme un membre "
            "d'équipe fiable. Le résultat : des apps livrées plus vite, qui scalent proprement et "
            "qui font plaisir à utiliser.")
    now = [("Je construis", "Badminton Manager, une web app pour organiser sessions, joueurs et matchs — en Next.js et TypeScript."),
           ("J'apprends", "React Server Components, runtimes edge et workflows de dev assistés par IA."),
           ("J'explore", "Design systems, motion design et patterns d'UI accessibles.")]
    bw = 420
    blines = wrap(words(body, "sans", TEXT2), 17, bw)
    colw = (W - 2 * PAD - 2 * 48) / 3
    nlines = [wrap(words(t, "serif", ESPRESSO), 21, colw) for _, t in now]
    top_h = max(170, len(blines) * 28 + 20)
    now_h = 40 + max(len(n) for n in nlines) * 29
    H = PAD + 30 + top_h + 48 + now_h + 24
    s = Svg(W, H, "I. Positionnement — Builder, pas juste développeur. En ce moment : Badminton Manager, React Server Components, design systems.")
    panel(s, 0, 0, W, H)
    eyebrow(s, PAD, PAD + 12, "I. Positionnement")
    s.runs(PAD - 2, PAD + 92, [("Builder, ", "serif", ESPRESSO), ("pas juste", "serif-i", CARAMEL)], 54, ls_em=-0.03)
    s.runs(PAD - 2, PAD + 92 + 60, [("développeur.", "serif", ESPRESSO)], 54, ls_em=-0.03)
    for i, ln in enumerate(blines):
        s.runs(W - PAD - bw, PAD + 44 + i * 28, ln, 17)
    ry = PAD + 30 + top_h
    rule(s, PAD, W - PAD, ry)
    for c, ((label, _), lines) in enumerate(zip(now, nlines)):
        x = PAD + c * (colw + 48)
        eyebrow(s, x, ry + 48, label)
        for i, ln in enumerate(lines):
            s.runs(x, ry + 84 + i * 29, ln, 21, ls_em=-0.015)
    s.render("about.svg")


# ================================================================ work
def work_head():
    s, H = section_head("work.svg", "II. Projets",
                        [("Ce que j'ai ", "serif", ESPRESSO), ("construit", "serif-i", CARAMEL)],
                        "Une sélection de projets favoris, de l'interface utilisateur à l'architecture backend.",
                        "II. Projets — Ce que j'ai construit")
    s.render("work.svg")


def card(fname, name, tags, desc, foot, link, h=None, small=False):
    cw = 490
    size = 17 if small else 16
    lines = wrap(words(desc, "sans", TEXT2), 15.5, cw - 2 * 32)
    H = h or (32 + 24 + 50 + len(lines) * 24 + 56)
    s = Svg(cw, H, f"{name} — {desc}")
    panel(s, 0, 0, cw, H, fill=SURFACE)
    s.text(32, 46, tags, "mono", 11.5, MUTED, ls=1.38, upper=True)
    tsize = 24 if small else 32
    w = s.text(31, 46 + 18 + tsize * 0.85, name, "serif", tsize, ESPRESSO, ls=-tsize * 0.025)
    if link:
        s.text(31 + w + 8, 46 + 18 + tsize * 0.85, "↗", "mono", tsize * 0.6, CARAMEL)
    dy = 46 + 18 + tsize * 0.85 + 34
    for i, ln in enumerate(lines):
        s.runs(32, dy + i * 24, ln, 15.5)
    rule(s, 32, cw - 32, H - 52, LINE)
    s.text(32, H - 22, foot, "mono", 11.5, CARAMEL if link else MUTED, ls=1.38, upper=True)
    return s, H


def projects():
    items = [
        ("badminton.svg", "Badminton Manager", "Next.js · PWA",
         "Organiser et gérer sessions, joueurs et matchs de badminton — pensée pour fluidifier la coordination de club et d'événements.",
         "Démo en ligne ↗", True),
        ("hubmovies.svg", "Hubmovies", "Nuxt · Firebase · PWA",
         "Une application mobile-first pour gérer films et séries.", "hubmovies.app ↗", True),
        ("contelune.svg", "Contelune", "Next.js · Ollama · FLUX",
         "Histoires du soir interactives pour enfants : on choisit un thème et des héros, une IA locale raconte à voix haute une histoire illustrée, chapitre par chapitre.",
         "Projet perso · local", False),
        ("crema.svg", "Crema", "React · Vite · Supabase",
         "Suivi de budget et de patrimoine qui explique simplement : budget du mois, import des relevés bancaires, comptes, crédits et bilan mensuel.",
         "Projet perso · local", False),
    ]
    _equal_rows(items, small=False)

    oss = [
        ("oss-angular-movies.svg", "angular-movies", "Open source · 60 étoiles",
         "Une PWA pour parcourir les films, construite avec Angular et l'API TMDB.", "TypeScript · dépôt ↗", True),
        ("oss-kibana-health.svg", "kibana_health_metric_vis", "Open source · 46 étoiles",
         "Plugin Kibana 4.x à 7.x qui colore une métrique selon l'état de santé prévu.", "HTML · dépôt ↗", True),
    ]
    _equal_rows(oss, small=True)


def _equal_rows(items, small):
    for i in range(0, len(items), 2):
        pair = items[i:i + 2]
        hs = [card(*it, small=small)[1] for it in pair]
        h = max(hs)
        for it in pair:
            s, _ = card(*it, h=h, small=small)
            s.render(it[0])


# ================================================================ AI
AI_TOOLS = ["Claude Code", "Cursor", "MCP", "Agent Skills", "Subagents", "Hooks",
            "Workflows multi-agents", "Playwright MCP", "Ollama", "FLUX"]


def ai():
    body = ("L'IA est une coéquipière dans mon workflow, pas une simple autocomplétion. Des agents "
            "enquêtent, planifient, implémentent et relisent — branchés sur les vrais outils de "
            "l'équipe via MCP, guidés par des skills qui encodent notre savoir-faire. Je garde les "
            "décisions et la relecture finale.")
    cells = [
        ("Agents", "Claude Code et Cursor, avec subagents et workflows multi-agents qui enquêtent, planifient, implémentent et relisent."),
        ("MCP", "Des agents branchés sur GitLab, Jira, Datadog, MongoDB, Snowflake, Slack et le navigateur via Playwright."),
        ("Skills", "Des skills maison qui transforment le savoir-faire d'équipe en flux répétables : du ticket à la MR, revue de code locale, tri de la santé prod."),
        ("IA locale", "Ollama et FLUX en local — Contelune raconte des histoires illustrées, entièrement hors ligne."),
    ]
    bw = 420
    blines = wrap(words(body, "sans", TEXT2), 17, bw)
    colw = (W - 2 * PAD - 48) / 2
    clines = [wrap(words(t, "serif", ESPRESSO), 21, colw) for _, t in cells]
    top_h = max(170, len(blines) * 28 + 20)
    row_h = [40 + max(len(clines[i]), len(clines[i + 1])) * 29 + 32 for i in (0, 2)]
    # pills
    PH, GAP, FS = 32, 8, 14
    px, py_lines, cur = PAD, [], []
    for it in AI_TOOLS:
        pw = measure(it, "sans-m", FS) + 28
        if cur and px + pw > W - PAD:
            py_lines.append(cur); cur, px = [], PAD
        cur.append((it, px, pw)); px += pw + GAP
    py_lines.append(cur)
    pills_h = len(py_lines) * (PH + GAP)
    H = PAD + 30 + top_h + sum(row_h) + 24 + pills_h + PAD - 16
    s = Svg(W, H, "III. Ingénierie assistée par IA — Livrer avec des agents. " + ", ".join(AI_TOOLS))
    panel(s, 0, 0, W, H)
    eyebrow(s, PAD, PAD + 12, "III. Ingénierie assistée par IA")
    s.runs(PAD - 2, PAD + 92, [("Livrer avec", "serif", ESPRESSO)], 60, ls_em=-0.03)
    s.runs(PAD - 2, PAD + 152, [("des ", "serif", ESPRESSO), ("agents", "serif-i", CARAMEL)], 60, ls_em=-0.03)
    for i, ln in enumerate(blines):
        s.runs(W - PAD - bw, PAD + 44 + i * 28, ln, 17)
    y = PAD + 30 + top_h
    for r in range(2):
        rule(s, PAD, W - PAD, y)
        for c in range(2):
            idx = r * 2 + c
            x = PAD + c * (colw + 48)
            eyebrow(s, x, y + 44, cells[idx][0])
            for i, ln in enumerate(clines[idx]):
                s.runs(x, y + 80 + i * 29, ln, 21, ls_em=-0.015)
        y += row_h[r]
    rule(s, PAD, W - PAD, y)
    y += 24
    for li, line in enumerate(py_lines):
        ly = y + li * (PH + GAP)
        for it, x, pw in line:
            s.add(f'<rect x="{x+0.5}" y="{ly+0.5}" width="{pw-1:.1f}" height="{PH-1}" rx="15.5" fill="none" stroke="{LINE_STRONG}"/>')
            s.text(x + pw / 2, ly + 21, it, "sans-m", FS, ESPRESSO, anchor="middle")
    s.render("ai.svg")


# ================================================================ stack
STACK = [
    ("Socle", ["TypeScript", "JavaScript", "HTML", "CSS"]),
    ("Frontend", ["React", "Next.js", "Vue", "Nuxt", "Angular", "Lit"]),
    ("State management", ["Redux", "Zustand", "Pinia"]),
    ("Styling & UI", ["Tailwind CSS", "Sass", "styled-components", "MUI", "Ant Design", "Vuetify", "PrimeVue", "DaisyUI"]),
    ("Backend & API", ["Node.js", "NestJS", "Express", "GraphQL", "Apollo", "Strapi", "Swagger"]),
    ("Données", ["PostgreSQL", "MongoDB", "Firebase", "Supabase", "Sequelize", "TypeORM"]),
    ("Tests & QA", ["Cypress", "Jest", "Cucumber", "Vitest", "Testing Library", "Puppeteer", "Sentry"]),
    ("DevOps & Cloud", ["Docker", "GitHub Actions", "GitLab CI", "Vercel", "Railway", "Google Cloud", "Azure", "Datadog"]),
    ("Outillage", ["Git", "Vite", "pnpm", "Nx", "ESLint", "Prettier", "Stylelint", "Husky"]),
    ("Organisation", ["Figma", "Postman", "VS Code", "Cursor", "Jira", "Notion"]),
]
DAILY = {"TypeScript", "React", "Next.js", "Vue", "Nuxt", "Node.js", "Tailwind CSS", "Sass",
         "styled-components", "Cypress", "Jest", "Cucumber", "Firebase"}


def stack():
    PH, GAP, FS = 32, 8, 14
    left = PAD
    px0 = PAD + 200
    maxx = W - PAD
    # layout first
    rows = []
    for label, items in STACK:
        lines, cur, x = [], [], px0
        for it in items:
            pw = measure(it, "sans-m", FS) + 28
            if cur and x + pw > maxx:
                lines.append(cur)
                cur, x = [], px0
            cur.append((it, x, pw))
            x += pw + GAP
        lines.append(cur)
        rows.append((label, lines))
    head = PAD + 130
    body_h = sum(len(l) * (PH + GAP) - GAP + 26 for _, l in rows)
    H = head + 30 + body_h + PAD - 26
    s = Svg(W, H, "IV. Stack — " + "; ".join(f"{l}: {', '.join(i)}" for l, i in STACK))
    panel(s, 0, 0, W, H)
    eyebrow(s, PAD, PAD + 12, "IV. Stack")
    s.runs(PAD - 2, PAD + 92, [("Les outils du ", "serif", ESPRESSO), ("métier", "serif-i", CARAMEL)], 60, ls_em=-0.03)
    # legend
    lx = W - PAD
    lw = measure("Au quotidien", "sans-m", 13) + 26
    s.add(f'<rect x="{lx-lw}" y="{PAD+68}" width="{lw}" height="28" rx="14" fill="{ESPRESSO}"/>')
    s.text(lx - lw / 2, PAD + 87, "Au quotidien", "sans-m", 13, BG, anchor="middle")
    lw2 = measure("Aussi utilisé", "sans-m", 13) + 26
    s.add(f'<rect x="{lx-lw-8-lw2+0.5}" y="{PAD+68.5}" width="{lw2-1}" height="27" rx="14" fill="none" stroke="{LINE_STRONG}"/>')
    s.text(lx - lw - 8 - lw2 / 2, PAD + 87, "Aussi utilisé", "sans-m", 13, TEXT2, anchor="middle")

    y = head + 30
    rule(s, PAD, W - PAD, head)
    for ri, (label, lines) in enumerate(rows):
        if ri:
            rule(s, PAD, W - PAD, y - 13)
        eyebrow(s, left, y + 21, label)
        for li, line in enumerate(lines):
            ly = y + li * (PH + GAP)
            for it, x, pw in line:
                if it in DAILY:
                    s.add(f'<rect x="{x}" y="{ly}" width="{pw:.1f}" height="{PH}" rx="16" fill="{ESPRESSO}"/>')
                    s.text(x + pw / 2, ly + 21, it, "sans-m", FS, BG, anchor="middle")
                else:
                    s.add(f'<rect x="{x+0.5}" y="{ly+0.5}" width="{pw-1:.1f}" height="{PH-1}" rx="15.5" fill="none" stroke="{LINE_STRONG}"/>')
                    s.text(x + pw / 2, ly + 21, it, "sans-m", FS, ESPRESSO, anchor="middle")
        y += len(lines) * (PH + GAP) - GAP + 26
    s.render("stack.svg")


# ================================================================ contact
def contact():
    lead = ("Mission freelance, MVP, développement continu ou audit. "
            "Chaque mission démarre par un appel découverte gratuit pour cadrer le bon format.")
    lines = wrap(words(lead, "sans", MUTED_DARK), 17, 380)
    H = 260
    s = Svg(W, H, "V. Contact — Un projet ? Discutons-en.")
    panel(s, 0, 0, W, H, fill=ESPRESSO, stroke=None)
    eyebrow(s, PAD, PAD + 12, "V. Contact", fill=CARAMEL_LIGHT)
    s.runs(PAD - 2, PAD + 92, [("Un projet ?", "serif", BG)], 60, ls_em=-0.03)
    s.runs(PAD - 2, PAD + 152, [("Discutons-en.", "serif-i", CARAMEL_LIGHT)], 60, ls_em=-0.03)
    for i, ln in enumerate(lines):
        s.runs(W - PAD - 380, PAD + 100 + i * 28, ln, 17)
    s.render("contact.svg")


# ================================================================ buttons
def button(fname, label, kind):
    FS = 15
    w = int(measure(label, "sans-b", FS) + 48)
    h = 48
    s = Svg(w, h, label)
    if kind == "primary":
        s.add(f'<rect x="0" y="0" width="{w}" height="{h}" rx="24" fill="{ESPRESSO}"/>')
        fill = BG
    else:
        s.add(f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="23.5" fill="{BG}" stroke="{LINE_STRONG}"/>')
        fill = ESPRESSO
    # draw arrows with mono so the glyph exists
    if label[-1] in "→↗":
        tw = measure(label[:-2], "sans-b", FS)
        aw = measure(label[-1], "mono-m", FS)
        x0 = (w - tw - 6 - aw) / 2
        s.text(x0, 30, label[:-2], "sans-b", FS, fill)
        s.text(x0 + tw + 6, 30, label[-1], "mono-m", FS, fill if kind == "primary" else CARAMEL)
    else:
        s.text(w / 2, 30, label, "sans-b", FS, fill, anchor="middle")
    s.render(fname)


hero(); stats(); about(); work_head(); projects(); ai(); stack(); contact()
button("btn-work.svg", "Voir mes projets ↗", "primary")
button("btn-talk.svg", "Discutons-en →", "secondary")
button("btn-email.svg", "M'écrire →", "primary")
button("btn-linkedin.svg", "LinkedIn ↗", "secondary")
button("btn-site.svg", "clamarque.github.io ↗", "secondary")
