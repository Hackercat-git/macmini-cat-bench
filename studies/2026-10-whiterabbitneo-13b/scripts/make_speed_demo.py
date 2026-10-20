#!/usr/bin/env python3
"""make_speed_demo.py — plays back the measured answer speed of models side by side, at the REAL timings from docs/bench-data/stream.json
(bench_stream.py legt per tekststuk vast wanneer het binnenkwam). Niets wordt versneld of gesimuleerd.

  python make_speed_demo.py            # docs/snelheidsdemo.html (zelf af te spelen) en docs/snelheidsdemo.gif (te delen, bv. in Discord)
  python make_speed_demo.py --html     # alleen de HTML
"""
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "docs" / "bench-data" / "stream.json"
OUT_HTML = ROOT / "docs" / "speed-demo.html"
OUT_GIF = ROOT / "docs" / "speed-demo.gif"
NAMEN = {"wrn13b": "WhiteRabbitNeo 13B (Llama 2)", "qwen2.5-coder:14b": "qwen2.5-coder 14B", "qwen3:8b": "qwen3 8B", "phi4:14b": "phi4 14B",
         "qwen3.8:27b": "qwen3.8 27B", "wrn25-qwen7b": "WhiteRabbitNeo 2.5 (Qwen) 7B", "deephat7b": "DeepHat V1 7B",
         "wrn-llama3-8b": "WhiteRabbitNeo (Llama 3) 8B", "dolphin-llama3:8b": "dolphin-llama3 8B", "deepseek-r1:14b": "deepseek-r1 14B (thinks aloud first)",
         "codestral:22b": "codestral 22B", "qwen2.5-coder:32b": "qwen2.5-coder 32B"}
GIF_KEUZE = ["wrn13b", "wrn25-qwen7b", "qwen2.5-coder:14b", "qwen3.8:27b"]       # vier naast elkaar in de GIF; de HTML kan er meer tonen
FPS = 10
GIF_BREEDTE, GIF_HOOGTE = 960, 560


def naam(m: str) -> str:
    return NAMEN.get(m, m)


def komma(x: float, nd: int = 1) -> str:
    return f"{x:.{nd}f}"


def zichtbaar(stukjes: list, t: float) -> str:
    """De tekst die op tijd t (seconden sinds het versturen) al binnen is."""
    return "".join(tekst for tijd, tekst in stukjes if tijd <= t)


def aantal(stukjes: list, t: float) -> int:
    return sum(1 for tijd, _ in stukjes if tijd <= t)


def regels(tekst: str, breedte: int, max_regels: int) -> list:
    """Tekst teruggebroken op `breedte` tekens; als het niet past, de laatste regels (zoals een terminal die meescrolt)."""
    uit = []
    for alinea in (tekst or "").replace("\r", "").split("\n"):
        uit += textwrap.wrap(alinea, breedte, break_long_words=True) or [""]
    return uit[-max_regels:]


def duur(data: dict, keuze: list) -> float:
    return max((data["modellen"][m]["stukjes"][-1][0] for m in keuze if m in data["modellen"] and data["modellen"][m]["stukjes"]), default=0.0)


def laad() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


# ── HTML ─────────────────────────────────────────────────────────────────────
def maak_html(data: dict) -> str:
    modellen = {m: v for m, v in data["modellen"].items() if v.get("stukjes")}
    volgorde = sorted(modellen, key=lambda m: -(modellen[m]["tok_s"] or 0))
    payload = {m: {"naam": naam(m), "tok_s": modellen[m]["tok_s"], "ttft": modellen[m]["ttft_s"], "stukjes": modellen[m]["stukjes"]} for m in volgorde}
    js = json.dumps({"vraag": data["vraag"], "modellen": payload, "volgorde": volgorde}, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>How fast does a model answer?</title>
<style>
:root {{ --ink:#0b0b0b; --ink2:#52514e; --line:#dcdbd5; --blue:#2a78d6; --bg:#fff; --panel:#fafaf8; }}
@media (prefers-color-scheme: dark) {{ :root {{ --ink:#f0efec; --ink2:#c3c2b7; --line:#3a3a37; --blue:#3987e5; --bg:#1a1a19; --panel:#222220; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ font-size:24px; margin:0 0 4px; }} p {{ color:var(--ink2); margin:4px 0 12px; }}
.bar {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin:12px 0 16px; }}
button {{ font:inherit; padding:7px 14px; border:1px solid var(--line); background:var(--panel); color:var(--ink); border-radius:8px; cursor:pointer; }}
button.go {{ background:var(--blue); border-color:var(--blue); color:#fff; font-weight:600; }}
.klok {{ font:600 18px ui-monospace,Consolas,monospace; min-width:90px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:12px; }}
.panel {{ border:1px solid var(--line); border-radius:10px; background:var(--panel); padding:10px 12px; min-height:300px; display:flex; flex-direction:column; }}
.kop {{ display:flex; justify-content:space-between; gap:8px; align-items:baseline; margin-bottom:6px; }}
.kop b {{ font-size:14px; }} .kop span {{ color:var(--ink2); font-size:12px; font-variant-numeric:tabular-nums; }}
.tekst {{ font:13.5px/1.5 ui-monospace,Consolas,monospace; white-space:pre-wrap; flex:1; overflow:hidden; }}
.meter {{ height:5px; background:var(--line); border-radius:3px; margin-top:8px; overflow:hidden; }} .meter i {{ display:block; height:100%; width:0; background:var(--blue); }}
.voet {{ color:var(--ink2); font-size:12px; margin-top:14px; }}
</style></head><body><main>
<h1>How fast does a model answer?</h1>
<p>The same question given to each model, measured on a Mac mini (Apple M6, 32 GB). This is a <b>replay at the real timings</b>: each piece of text appears exactly when it arrived during the measurement. Nothing is sped up.</p>
<p><i id="vraag"></i></p>
<div class="bar"><button class="go" id="start">▶ Start</button><button id="reset">↺ Restart</button>
<button id="traag">Half speed</button><span class="klok" id="klok">0.0 s</span></div>
<div class="grid" id="grid"></div>
<div class="voet">Tokens per second (tok/s) is how many pieces of text (roughly three quarters of a word each) the model writes per second. At 15 tok/s you can read along without waiting; at 30 it is faster than most people read.</div>
</main>
<script>
const D = {js};
const grid = document.getElementById('grid'), klok = document.getElementById('klok');
document.getElementById('vraag').textContent = 'Question: ' + D.vraag;
const nf = (x, n=1) => x.toFixed(n);
const panels = D.volgorde.map(m => {{
  const v = D.modellen[m], el = document.createElement('div'); el.className = 'panel';
  el.innerHTML = '<div class="kop"><b></b><span></span></div><div class="tekst"></div><div class="meter"><i></i></div>';
  el.querySelector('b').textContent = v.naam;
  el.querySelector('span').textContent = nf(v.tok_s) + ' tok/s · first token after ' + nf(v.ttft, 2) + ' s';
  grid.appendChild(el);
  return {{ m, v, tekst: el.querySelector('.tekst'), meter: el.querySelector('i'), n: 0, eind: v.stukjes[v.stukjes.length-1][0] }};
}});
let t0 = null, tempo = 1, t = 0, raf = null;
function teken() {{
  panels.forEach(p => {{
    let s = '', n = 0;
    for (const [tijd, tekst] of p.v.stukjes) {{ if (tijd > t) break; s += tekst; n++; }}
    p.tekst.textContent = s; p.meter.style.width = Math.min(100, 100 * t / p.eind) + '%';
  }});
  klok.textContent = nf(t) + ' s';
}}
function tik(nu) {{
  t = ((nu - t0) / 1000) * tempo; teken();
  if (t < Math.max(...panels.map(p => p.eind)) + 0.2) raf = requestAnimationFrame(tik); else raf = null;
}}
function start() {{ cancelAnimationFrame(raf); t = 0; t0 = performance.now(); raf = requestAnimationFrame(tik); }}
document.getElementById('start').onclick = start;
document.getElementById('reset').onclick = () => {{ cancelAnimationFrame(raf); t = 0; teken(); }};
document.getElementById('traag').onclick = e => {{ tempo = tempo === 1 ? 0.5 : 1; e.target.textContent = tempo === 1 ? 'Half speed' : 'Normal speed'; }};
teken();
</script></body></html>
"""


# ── GIF en stilstaand beeld ───────────────────────────────────────────────────
def _tekenaar(data: dict, keuze: list):
    """Geeft (keuze, eind, teken) terug; teken(t) levert het beeld op tijd t als PIL-afbeelding."""
    from PIL import Image, ImageDraw, ImageFont
    keuze = [m for m in (keuze or GIF_KEUZE) if m in data["modellen"] and data["modellen"][m].get("stukjes")]
    if not keuze:
        raise SystemExit("no models with data for the image")

    def font(namen, maat):
        for n in namen:
            for map_ in ("C:/Windows/Fonts/", "/System/Library/Fonts/Supplemental/", "/Library/Fonts/", ""):
                try:
                    return ImageFont.truetype(map_ + n, maat)
                except OSError:
                    continue
        return ImageFont.load_default()

    f_kop = font(["segoeuib.ttf", "Arial Bold.ttf", "arialbd.ttf"], 20)
    f_klein = font(["segoeui.ttf", "Arial.ttf", "arial.ttf"], 15)
    f_tekst = font(["consola.ttf", "Menlo.ttc", "Courier New.ttf", "cour.ttf"], 15)
    bg, paneel, ink, ink2, lijn, blauw = (255, 255, 255), (247, 247, 244), (11, 11, 11), (82, 81, 78), (220, 219, 213), (42, 120, 214)
    kol = 2
    rij = (len(keuze) + 1) // 2
    marge, tussen, top = 14, 12, 56
    pw = (GIF_BREEDTE - 2 * marge - tussen * (kol - 1)) // kol
    ph = (GIF_HOOGTE - top - marge - tussen * (rij - 1)) // rij
    chars = max(20, (pw - 24) // 9)
    max_regels = max(3, (ph - 78) // 20)
    eind = duur(data, keuze) + 1.5

    def teken(t: float):
        img = Image.new("RGB", (GIF_BREEDTE, GIF_HOOGTE), bg)
        d = ImageDraw.Draw(img)
        d.text((marge, 12), "How fast does a model answer? Real measurement on a Mac mini (M6, 32 GB)", font=f_kop, fill=ink)
        d.text((GIF_BREEDTE - marge - 90, 15), f"t = {komma(t)} s", font=f_klein, fill=ink2)
        for k, m in enumerate(keuze):
            v = data["modellen"][m]
            x, y = marge + (k % kol) * (pw + tussen), top + (k // kol) * (ph + tussen)
            d.rounded_rectangle([x, y, x + pw, y + ph], radius=10, fill=paneel, outline=lijn)
            d.text((x + 12, y + 8), naam(m), font=f_kop, fill=ink)
            d.text((x + 12, y + 34), f"{komma(v['tok_s'] or 0)} tok/s · first token after {komma(v['ttft_s'], 2)} s", font=f_klein, fill=ink2)
            for r, regel in enumerate(regels(zichtbaar(v["stukjes"], t), chars, max_regels)):
                d.text((x + 12, y + 60 + r * 20), regel, font=f_tekst, fill=ink)
            klaar = v["stukjes"][-1][0]
            d.rectangle([x + 12, y + ph - 12, x + pw - 12, y + ph - 8], fill=lijn)
            d.rectangle([x + 12, y + ph - 12, x + 12 + int((pw - 24) * min(1, t / klaar)), y + ph - 8], fill=blauw)
        return img
    return keuze, eind, teken


def maak_gif(data: dict, pad: Path = OUT_GIF, keuze: list = None, fps: int = FPS) -> int:
    from PIL import Image
    keuze, eind, teken = _tekenaar(data, keuze)
    frames = [teken(i / fps).quantize(colors=24, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for i in range(int(eind * fps) + 1)]
    frames[0].save(pad, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0, optimize=True, disposal=1)
    return Path(pad).stat().st_size


def maak_still(data: dict, pad: Path, t: float = 6.0, keuze: list = None) -> int:
    """Een stilstaand beeld van de demo op tijd t (voor in het rapport)."""
    _, _, teken = _tekenaar(data, keuze)
    teken(t).save(pad, optimize=True)
    return Path(pad).stat().st_size


def main():
    data = laad()
    OUT_HTML.write_text(maak_html(data), encoding="utf-8")
    print("geschreven:", OUT_HTML)
    if "--html" not in sys.argv:
        grootte = maak_gif(data)
        print(f"geschreven: {OUT_GIF} ({grootte / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
