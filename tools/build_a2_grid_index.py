#!/usr/bin/env python3
"""Indexa un pack de capturas NAM A2 como GRILLA de amp en data/a2_capture_grids.json.

Un pack tipo "VOX AC30 CH [Hyper Accuracy+]" trae ~100 capturas amp-only del
mismo amp barriendo las perillas reales (canal, Volume, Tone Cut, Bass, Treble).
Este tool parsea los nombres a coordenadas de grilla y escribe la entrada que
routes.py::_pick_a2_grid_capture usa para elegir, por tono, la captura más
cercana a las perillas RS (el amp suena por captura A2; el cab IR sigue siendo
el nuestro).

Convención de nombres soportada (pack de @slamminmofo):
    SLAMMIN_VOX_AC30_{N|TB}_V{vol}_TC{tc}[_B{bass}_T{treble}][_ETIQUETA]_S.nam
Las variantes con booster externo (DALLASTREBLE) se indexan con "boost": true y
el picker las ignora (no son el amp a secas).

⚠️ Licencia T3K: los .nam NO se redistribuyen — el índice (nombres/coordenadas)
sí viaja en data/, los archivos los instala cada usuario (--install los copia a
<config>/nam_models/amps/<subdir>/).

Uso:
  python3 tools/build_a2_grid_index.py "/ruta/al/pack" \
      --gear Amp_EN30 --subdir a2_vox_ac30 \
      --install "~/Library/Application Support/feedback-desktop/slopsmith-config/nam_models"
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

# SLAMMIN_VOX_AC30_TB_V5_TC4_B7_T8_PUSH_S.nam → ch/v/tc/b/t (+boost si trae
# DALLASTREBLE). Tolerante a espacios raros ("MIDS _S") y etiquetas libres.
_NAME_RE = re.compile(
    r"_(?P<ch>N|TB)_V(?P<v>\d+)_TC(?P<tc>\d+)"
    r"(?:_B(?P<b>\d+)_T(?P<t>\d+))?"
    r"(?P<rest>.*)\.nam$", re.IGNORECASE)


def parse_pack(pack_dir: Path) -> list[dict]:
    caps = []
    for f in sorted(pack_dir.glob("*.nam")):
        m = _NAME_RE.search(f.name)
        if not m:
            print(f"  ⚠ no parsea: {f.name}", file=sys.stderr)
            continue
        cap = {
            "file": f.name,
            "ch": m.group("ch").upper(),
            "v": int(m.group("v")),
            "tc": int(m.group("tc")),
        }
        if m.group("b") is not None:
            cap["b"] = int(m.group("b"))
            cap["t"] = int(m.group("t"))
        rest = (m.group("rest") or "").upper()
        if "DALLAS" in rest or "BOOST" in rest:
            cap["boost"] = True
        caps.append(cap)
    return caps


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pack_dir")
    ap.add_argument("--gear", required=True, help="rs_gear del amp (p.ej. Amp_EN30)")
    ap.add_argument("--subdir", required=True,
                    help="subcarpeta bajo nam_models/amps/ (p.ej. a2_vox_ac30)")
    ap.add_argument("--install", default=None,
                    help="raíz nam_models donde copiar el pack (opcional)")
    args = ap.parse_args()

    pack_dir = Path(args.pack_dir).expanduser()
    caps = parse_pack(pack_dir)
    if not caps:
        raise SystemExit("ningún .nam parseado")
    n_boost = sum(1 for c in caps if c.get("boost"))
    chans = sorted({c["ch"] for c in caps})
    print(f"{len(caps)} capturas ({n_boost} con boost externo), canales: {chans}")

    out_path = HERE / "data" / "a2_capture_grids.json"
    grids = {}
    if out_path.exists():
        grids = json.loads(out_path.read_text())
    grids.setdefault("_meta", (
        "A2 capture grids — packs de capturas NAM A2 (TONE3000) indexados como "
        "grilla por amp. El picker (_pick_a2_grid_capture) elige por tono la "
        "captura más cercana a las perillas RS; snap-only (la cadena de playback "
        "es serial — el morph gradual vive en el A2 player VST, fase 2). Los "
        ".nam NO se redistribuyen (licencia T3K): cada usuario instala el pack "
        "con tools/build_a2_grid_index.py --install."))
    grids[args.gear] = {
        "pack_name": pack_dir.name,
        "library_subdir": args.subdir,
        # canal por defecto del pick (los tonos RS del AC30 = voz Top Boost)
        "channel_default": "TB",
        # perilla RS → eje de grilla (tc_inv: Tone Cut es presencia INVERSA)
        "knob_map": {"v": "Gain", "t": "Treble", "b": "Bass", "tc_inv": "Pres"},
        # pesos de la distancia (V domina: es el carácter de drive)
        "axis_weights": {"v": 3.0, "t": 1.5, "b": 1.5, "tc": 0.75},
        "captures": caps,
    }
    out_path.write_text(json.dumps(grids, indent=1, ensure_ascii=False) + "\n")
    print(f"índice → {out_path} ({args.gear}: {len(caps)} capturas)")

    if args.install:
        dest = Path(args.install).expanduser() / "amps" / args.subdir
        dest.mkdir(parents=True, exist_ok=True)
        copied = 0
        for c in caps:
            src = pack_dir / c["file"]
            dst = dest / c["file"]
            if not dst.exists() or dst.stat().st_size != src.stat().st_size:
                shutil.copy2(src, dst)
                copied += 1
        print(f"instalado → {dest} ({copied} copiados, {len(caps) - copied} ya estaban)")


if __name__ == "__main__":
    main()
