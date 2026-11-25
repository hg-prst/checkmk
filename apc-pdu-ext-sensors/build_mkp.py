#!/usr/bin/env python3
# Copyright (C) 2026 Hugo Proost - License: MIT
"""Build the Checkmk extension package (.mkp) from this source tree.

Layout of an MKP (Checkmk 2.4, see cmk/mkp_tool/_mkp.py):
    <name>-<version>.mkp  (tar.gz)
      info                    manifest as Python literal
      info.json               same manifest as JSON
      cmk_addons_plugins.tar  files relative to ~/local/lib/python3/cmk_addons/plugins/

Usage:  python3 build_mkp.py [--version X.Y.Z] [--outdir DIR]
Python 3 standard library only.
"""

import argparse
import io
import json
import pprint
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"  # == content of cmk_addons_plugins part

MANIFEST = {
    "title": "APC PDU Temperature and Humidity metrics (external)",
    "name": "apc_pdu_ext_sensors",
    "description": (
        "SNMP check apc_rackpdu_ext_env for external temperature and humidity sensors on APC "
        "(Schneider) rack PDUs (PowerNet-MIB rPDU2SensorTempHumidityStatusTable). One check "
        "discovers Temperature Ext Sensor #N and Humidity Ext Sensor #N, with a discovery name "
        "per sensor number and one ruleset for upper/lower levels and factors of both metrics."
    ),
    "version": "1.1.0",
    "version.packaged": "2.4.0",
    "version.min_required": "2.4.0",
    "version.usable_until": None,
    "author": "Hugo Proost (h.proost[at]iubentium[dot]nl)",
    "download_url": "https://github.com/hg-prst/checkmk/tree/main/apc-pdu-ext-sensors",
}

PART = "cmk_addons_plugins"


def collect_files() -> list[Path]:
    files = []
    for path in sorted(SRC.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(SRC)
        if "__pycache__" in rel.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        files.append(rel)
    return files


def _info(name: str, size: int, mode: int, mtime: int) -> tarfile.TarInfo:
    ti = tarfile.TarInfo(name)
    ti.size, ti.mode, ti.mtime = size, mode, mtime
    ti.uid = ti.gid = 0
    ti.uname = ti.gname = "root"
    ti.type = tarfile.REGTYPE
    return ti


def build_part_tar(files: list[Path], mtime: int) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.GNU_FORMAT) as tar:
        for rel in files:
            data = (SRC / rel).read_bytes()
            executable = "libexec" in rel.parts
            tar.addfile(_info(str(rel), len(data), 0o755 if executable else 0o644, mtime),
                        io.BytesIO(data))
    return buf.getvalue()


def build(version: str, outdir: Path) -> Path:
    mtime = int(time.time())
    files = collect_files()
    manifest = {**MANIFEST, "version": version, "files": {PART: [str(f) for f in files]}}
    members = [
        ("info", (pprint.pformat(manifest) + "\n").encode()),
        ("info.json", json.dumps(manifest).encode()),
        (f"{PART}.tar", build_part_tar(files, mtime)),
    ]
    outdir.mkdir(parents=True, exist_ok=True)
    target = outdir / f"{manifest['name']}-{version}.mkp"
    with tarfile.open(target, mode="w:gz", format=tarfile.GNU_FORMAT) as tgz:
        for name, data in members:
            tgz.addfile(_info(name, len(data), 0o644, mtime), io.BytesIO(data))
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", default=MANIFEST["version"])
    parser.add_argument("--outdir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    target = build(args.version, args.outdir)
    print(f"Built {target}")


if __name__ == "__main__":
    main()
