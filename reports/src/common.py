"""Shared layout for the project reports. Each report module builds an HTML body;
build.py wraps it and prints it to PDF with headless Chrome."""
import html

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
* { box-sizing: border-box; }
body { font-family: 'DejaVu Sans', 'Liberation Sans', Arial, sans-serif; font-size: 10.2pt;
       line-height: 1.45; color: #1d2430; }
.cover { border-bottom: 3px solid #1f5f8b; padding-bottom: 10px; margin-bottom: 16px; }
.cover .kicker { color: #1f5f8b; font-weight: bold; letter-spacing: .06em; font-size: 9pt; text-transform: uppercase; }
.cover h1 { font-size: 22pt; margin: 4px 0 6px 0; color: #102a43; }
.cover .meta { color: #52606d; font-size: 9pt; }
h2 { font-size: 13.5pt; color: #1f5f8b; margin: 18px 0 6px 0; border-bottom: 1px solid #d9e2ec; padding-bottom: 2px; page-break-after: avoid; }
h3 { font-size: 11pt; color: #243b53; margin: 12px 0 4px 0; page-break-after: avoid; }
p { margin: 5px 0 7px 0; text-align: justify; }
ul, ol { margin: 4px 0 8px 0; padding-left: 20px; }
li { margin: 2px 0; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.6pt; background: #f0f4f8; padding: 0 3px; border-radius: 2px; }
pre { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.2pt; background: #f5f7fa; border: 1px solid #d9e2ec;
      padding: 7px 9px; border-radius: 3px; white-space: pre-wrap; page-break-inside: avoid; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 10px 0; font-size: 8.8pt; page-break-inside: avoid; }
th { background: #1f5f8b; color: white; text-align: left; padding: 4px 6px; font-weight: bold; }
td { border-bottom: 1px solid #d9e2ec; padding: 3px 6px; vertical-align: top; }
tr:nth-child(even) td { background: #f7f9fb; }
figure { margin: 10px 0 12px 0; text-align: center; page-break-inside: avoid; }
figure img { max-width: 100%; border: 1px solid #d9e2ec; }
figure.half img { max-width: 62%; }
figure.third img { max-width: 45%; }
figcaption { font-size: 8.6pt; color: #52606d; margin-top: 3px; text-align: center; }
.row { display: flex; gap: 10px; page-break-inside: avoid; }
.row figure { flex: 1; }
.box { background: #eef6fb; border-left: 4px solid #1f5f8b; padding: 7px 10px; margin: 8px 0; page-break-inside: avoid; }
.box.warn { background: #fff8e6; border-left-color: #d69e2e; }
.kpi { display: flex; gap: 8px; margin: 8px 0 10px 0; page-break-inside: avoid; }
.kpi div { flex: 1; border: 1px solid #d9e2ec; border-radius: 4px; padding: 6px 8px; text-align: center; }
.kpi b { display: block; font-size: 15pt; color: #1f5f8b; }
.kpi span { font-size: 8pt; color: #52606d; }
.toc { font-size: 9.2pt; columns: 2; margin-bottom: 6px; }
.pb { page-break-before: always; }
.small { font-size: 8.6pt; color: #52606d; }
svg text { font-family: 'DejaVu Sans', Arial, sans-serif; }
"""

FIGNUM = {'n': 0}


def reset():
    FIGNUM['n'] = 0


def fig(src, caption, cls=''):
    FIGNUM['n'] += 1
    return (f'<figure class="{cls}"><img src="../figures/{src}">'
            f'<figcaption><b>Figure {FIGNUM["n"]}.</b> {caption}</figcaption></figure>')


def fig2(a, ca, b, cb):
    FIGNUM['n'] += 1
    n1 = FIGNUM['n']
    FIGNUM['n'] += 1
    n2 = FIGNUM['n']
    return (f'<div class="row"><figure><img src="../figures/{a}"><figcaption><b>Figure {n1}.</b> {ca}'
            f'</figcaption></figure><figure><img src="../figures/{b}"><figcaption><b>Figure {n2}.</b> {cb}'
            f'</figcaption></figure></div>')


def table(head, rows):
    h = ''.join(f'<th>{c}</th>' for c in head)
    b = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in rows)
    return f'<table><tr>{h}</tr>{b}</table>'


def page(title, number, subtitle, body):
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>{CSS}</style></head><body>
<div class="cover"><div class="kicker">Indoor Autonomous Delivery Robot · Report {number} of 6</div>
<h1>{title}</h1><div class="meta">{subtitle}<br>Hüseyin Tozluyurt · ROS 2 Jazzy / Gazebo Harmonic simulation stack · November 2026</div></div>
{body}
</body></html>"""
