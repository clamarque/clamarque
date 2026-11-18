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


# ================================================================ hero (geek)
# One banner in the site palette; everything else in the README is plain
# markdown. A Pac-Man eats the dots along the bottom (SMIL + CSS, both
# render inside GitHub <img> SVGs).
def hero():
    H = 340
    DUR = 9  # seconds per lap
    s = Svg(W, H, "Charles Lamarque — dev full-stack JavaScript à Lille. Un Pac-Man mange des points en bas.")
    panel(s, 0, 0, W, H)

    # prompt line with blinking cursor
    y = PAD + 6
    x = PAD
    x += s.text(x, y, "~/clamarque", "mono", 14, CARAMEL)
    x += s.text(x, y, " $ ", "mono", 14, MUTED)
    x += s.text(x, y, "whoami", "mono", 14, ESPRESSO)
    s.add(f'<rect class="cur" x="{x+4:.1f}" y="{y-13}" width="8" height="16" fill="{CARAMEL}"/>')
    s.add('<style>.cur{animation:b 1s steps(1) infinite}@keyframes b{50%{opacity:0}}</style>')
    # availability, right
    lbl = "dispo en freelance"
    lw = s.text(W - PAD, y, lbl, "mono", 12, TEXT2, ls=1.44, anchor="end", upper=True)
    s.add(f'<circle cx="{W-PAD-lw-12:.1f}" cy="{y-4}" r="3.5" fill="{AVAILABLE}"/>')

    # headline
    ty = y + 82
    s.runs(PAD - 3, ty, [("Salut, moi c'est Charles —", "serif", ESPRESSO)], 54, ls_em=-0.025)
    s.runs(PAD - 3, ty + 58, [("dev full-stack ", "serif", ESPRESSO), ("JavaScript", "serif-i", CARAMEL),
                              (".", "serif", ESPRESSO)], 54, ls_em=-0.025)
    s.text(PAD, ty + 104, "10+ ans en ESN · Lille · TypeScript addict · carbure au cappuccino",
           "mono", 13, MUTED, ls=0.3)

    # ---- pac-man track
    ty = H - 48
    x0, x1 = -40, W + 40
    span = x1 - x0
    dots = list(range(PAD + 14, W - PAD, 26))
    pellet = dots[-3]
    for dx in dots:
        t = (dx - x0) / span
        r = 6 if dx == pellet else 2.6
        fill = CARAMEL if dx == pellet else LINE_STRONG
        s.add(f'<circle cx="{dx}" cy="{ty}" r="{r}" fill="{fill}">'
              f'<animate attributeName="opacity" values="1;1;0;0;1" '
              f'keyTimes="0;{t:.4f};{t+0.002:.4f};0.995;1" dur="{DUR}s" repeatCount="indefinite"/></circle>')

    mouth = ('<path fill="{c}" d="M0,0 L13,-9 A16,16 0 1,0 13,9 Z">'
             '<animate attributeName="d" dur="0.32s" repeatCount="indefinite" '
             'values="M0,0 L13,-9 A16,16 0 1,0 13,9 Z;M0,0 L16,-1 A16,16 0 1,0 16,1 Z;M0,0 L13,-9 A16,16 0 1,0 13,9 Z"/></path>')
    ghost = (f'<g transform="translate(-16,-16)">'
             f'<path fill="{CARAMEL}" d="M0,32 V14 A16,16 0 0,1 32,14 V32 L27,27 L21,32 L16,27 L11,32 L5,27 Z"/>'
             f'<circle cx="10" cy="13" r="4.5" fill="{SURFACE}"/><circle cx="22" cy="13" r="4.5" fill="{SURFACE}"/>'
             f'<circle cx="12" cy="13" r="2" fill="{ESPRESSO}"/><circle cx="24" cy="13" r="2" fill="{ESPRESSO}"/></g>')
    s.add(f'<g><animateTransform attributeName="transform" type="translate" '
          f'values="{x0},{ty};{x1},{ty}" dur="{DUR}s" repeatCount="indefinite"/>'
          f'{mouth.format(c=ESPRESSO)}</g>')
    s.add(f'<g><animateTransform attributeName="transform" type="translate" '
          f'values="{x0-90},{ty};{x1-90},{ty}" dur="{DUR}s" repeatCount="indefinite"/>{ghost}</g>')
    s.render("hero.svg")


hero()


# ================================================================ crema sections
# Transparent SVGs rendered twice: "-light" and "-dark", swapped by
# <picture> + prefers-color-scheme in the README.
THEMES = {
    "light": dict(ink=ESPRESSO, soft=MUTED, accent=CARAMEL, line=LINE_STRONG,
                  fill=ESPRESSO, fill_ink=BG, outline=LINE_STRONG),
    "dark": dict(ink=BG, soft=MUTED_DARK, accent=CARAMEL_LIGHT, line=LINE_DARK,
                 fill=CARAMEL_LIGHT, fill_ink=ESPRESSO, outline="#5a4a3e"),
}


def section_title(name, num, label, title_runs):
    for theme, c in THEMES.items():
        H = 92
        alt = f"{num} — {label} — " + "".join(t for t, _ in title_runs)
        s = Svg(W, H, alt)
        w = s.text(2, 30, f"{num} — {label}", "mono", 12, c["accent"], ls=1.44, upper=True)
        s.add(f'<line x1="{w+18:.0f}" y1="25.5" x2="{W-2}" y2="25.5" stroke="{c["line"]}"/>')
        runs = [(t, f, c["accent"] if f == "serif-i" else c["ink"]) for t, f in title_runs]
        s.runs(0, 76, runs, 38, ls_em=-0.025)
        s.render(f"h-{name}-{theme}.svg")


STACK = [  # * = au quotidien
    ("Front", ["TypeScript*", "React*", "Next.js*", "Vue*", "Nuxt*", "Angular", "Tailwind CSS*", "Sass", "styled-components"]),
    ("Back & data", ["Node.js*", "NestJS", "Express", "GraphQL", "PostgreSQL", "MongoDB", "Firebase*", "Supabase"]),
    ("Qualité", ["Cypress*", "Jest*", "Vitest", "Testing Library", "Cucumber", "ESLint", "Sentry"]),
    ("DevOps", ["Docker", "GitHub Actions", "GitLab CI", "Vercel", "Google Cloud", "Azure", "Datadog"]),
    ("IA", ["Claude Code*", "Cursor*", "MCP", "Agent Skills", "Ollama", "FLUX"]),
]


def stack():
    LBL, PH, GAP, FS = 150, 30, 7, 13.5
    for theme, c in THEMES.items():
        alt = "Stack — " + " ; ".join(f"{l} : {', '.join(i.rstrip('*') for i in items)}" for l, items in STACK)
        s = Svg(W, 0, alt)
        y = 4
        for ri, (label, items) in enumerate(STACK):
            s.text(2, y + 20, label, "mono", 12, c["accent"], ls=1.44, upper=True)
            x, ly = LBL, y
            for it in items:
                daily = it.endswith("*")
                it = it.rstrip("*")
                pw = measure(it, "sans-m", FS) + 26
                if x + pw > W - 2:
                    x, ly = LBL, ly + PH + GAP
                if daily:
                    s.add(f'<rect x="{x}" y="{ly}" width="{pw:.1f}" height="{PH}" rx="15" fill="{c["fill"]}"/>')
                    s.text(x + pw / 2, ly + 20, it, "sans-m", FS, c["fill_ink"], anchor="middle")
                else:
                    s.add(f'<rect x="{x+0.5}" y="{ly+0.5}" width="{pw-1:.1f}" height="{PH-1}" rx="14.5" fill="none" stroke="{c["outline"]}"/>')
                    s.text(x + pw / 2, ly + 20, it, "sans-m", FS, c["ink"], anchor="middle")
                x += pw + GAP
            y = ly + PH + 14
        # legend
        y += 10
        s.add(f'<rect x="{LBL}" y="{y}" width="22" height="12" rx="6" fill="{c["fill"]}"/>')
        w = s.text(LBL + 30, y + 10.5, "au quotidien", "sans", 13, c["soft"])
        s.add(f'<rect x="{LBL+30+w+22.5:.1f}" y="{y+0.5}" width="21" height="11" rx="5.5" fill="none" stroke="{c["outline"]}"/>')
        s.text(LBL + 30 + w + 52, y + 10.5, "aussi utilisé", "sans", 13, c["soft"])
        s.h = int(y + 18)
        s.render(f"stack-{theme}.svg")


section_title("projets", "01", "Projets", [("Ce que j'ai ", "serif"), ("construit", "serif-i")])
section_title("ia", "02", "IA", [("Livrer avec des ", "serif"), ("agents", "serif-i")])
section_title("stack", "03", "Stack", [("Les outils du ", "serif"), ("métier", "serif-i")])
section_title("activite", "04", "Activité", [("Pac-Man contre mes ", "serif"), ("commits", "serif-i")])
section_title("contact", "05", "Contact", [("Un projet ? ", "serif"), ("Discutons-en.", "serif-i")])
stack()


# ================================================================ project list
PROJECTS = [  # (file, name, tags, description, link?)
    ("badminton", "Badminton Manager", "Next.js · PWA",
     "Organisation de sessions, joueurs et matchs pour les clubs.", True),
    ("hubmovies", "Hubmovies", "Nuxt · Firebase · PWA",
     "Suivi de films et séries, mobile-first.", True),
    ("contelune", "Contelune", "Next.js · Ollama · FLUX",
     "Histoires du soir illustrées, générées par une IA 100 % locale.", False),
    ("crema", "Crema", "React · Vite · Supabase",
     "Suivi de budget et de patrimoine : import des relevés, crédits, bilan mensuel.", False),
    ("angular-movies", "angular-movies", "Angular · TypeScript · 60 étoiles",
     "PWA de films sur l'API TMDB.", True),
    ("kibana-health", "kibana_health_metric_vis", "Kibana · JavaScript · 46 étoiles",
     "Plugin Kibana 4.x à 7.x : couleur d'une métrique selon son état de santé.", True),
]


def project_rows():
    H, DX = 84, 430
    for i, (key, name, tags, desc, link) in enumerate(PROJECTS):
        last = i == len(PROJECTS) - 1
        for theme, c in THEMES.items():
            s = Svg(W, H + (1 if last else 0), f"{name} — {desc} ({tags})")
            s.add(f'<line x1="0" y1="0.5" x2="{W}" y2="0.5" stroke="{c["line"]}"/>')
            if last:
                s.add(f'<line x1="0" y1="{H+0.5}" x2="{W}" y2="{H+0.5}" stroke="{c["line"]}"/>')
            w = s.text(0, 38, name, "serif", 25, c["ink"], ls=-0.6)
            if link:
                s.text(w + 8, 38, "↗", "mono", 15, c["accent"])
            s.text(1, 62, tags, "mono", 11.5, c["accent"], ls=1.2, upper=True)
            lines = wrap(words(desc, "sans", c["soft"]), 15.5, W - DX)
            y0 = H / 2 + 5 - (len(lines) - 1) * 12
            for j, ln in enumerate(lines):
                s.runs(DX, y0 + j * 24, ln, 15.5)
            s.render(f"p-{key}-{theme}.svg")


project_rows()
