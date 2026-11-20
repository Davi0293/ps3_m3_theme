#!/usr/bin/env python3
"""Build PS3 .p3t themes from the folders under themes/.

It writes the same p3tcompiler input XML that theme-studio's ThemeBuild.cs writes, then runs
Sony's p3tcompiler.exe on it. p3tcompiler is a Windows program, so the real build needs Windows
(the GitHub Actions workflow uses windows-latest). --dry-run builds the XML and checks every
file and size on any OS, without running the compiler.

Usage:
  python build_theme.py --tools <folder holding p3tcompiler.exe> [--out dist] [--only purple]
  python build_theme.py --dry-run
"""
import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
THEMES = os.path.join(HERE, "themes")

# slot id -> (width, height); anything else in icons/ is rejected
ICON_SLOTS = {
    "icon_user": (128, 128), "icon_setting": (128, 128), "icon_photo": (128, 128),
    "icon_music": (128, 128), "icon_video": (128, 128), "icon_game": (128, 128),
    "icon_network": (128, 128), "icon_friend": (128, 128), "icon_tv": (128, 128),
}


def png_size(path):
    with open(path, "rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    return struct.unpack(">II", head[16:24])


def jpeg_size(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:2] != b"\xff\xd8":
        raise ValueError(f"{path} is not a JPEG")
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    raise ValueError(f"no size found in {path}")


def check(path, kind, want):
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    got = png_size(path) if kind == "png" else jpeg_size(path)
    if got != want:
        raise ValueError(f"{os.path.relpath(path, HERE)} is {got[0]}x{got[1]}, expected {want[0]}x{want[1]}")


def stage_name(name):
    # the Sony tools split unquoted paths at spaces; keep staged names to letters, digits, . and -
    return re.sub(r"[^A-Za-z0-9.\-]", "_", name)


def write_xml(src, stage, meta):
    """Same element/attribute layout as ThemeBuild.writeThemeXml."""
    def put(name, rel):
        shutil.copyfile(os.path.join(src, rel), os.path.join(stage, name))
        return name

    root = ET.Element("theme")
    table = ET.SubElement(root, "infotable")
    info = ET.SubElement(table, "info", name=meta["name"])
    for key in ("author", "genre", "version", "comment", "url"):
        if meta.get(key):
            info.set(key, meta[key])
    info.set("icon", put("icon.png", "icon.png"))
    info.set("preview", put("preview.png", "preview.png"))
    ET.SubElement(table, "localizedinfo", locale="en", name=meta["name"])

    icons = ET.SubElement(root, "icontable")
    icon_dir = os.path.join(src, "icons")
    for fname in sorted(os.listdir(icon_dir)):
        slot = os.path.splitext(fname)[0]
        ET.SubElement(icons, "icon", id=slot,
                      src=put(stage_name(fname), os.path.join("icons", fname)))

    bgs = ET.SubElement(root, "bgimagetable")
    ET.SubElement(bgs, "bgimage", hd=put("bg_hd.jpg", "bg_hd.jpg"), sd=put("bg_sd.jpg", "bg_sd.jpg"))

    ET.SubElement(root, "font", selection=str(meta.get("font", 0)))
    ET.SubElement(root, "color", selection=str(meta.get("color", 0)))

    ET.indent(root, space="\t")
    path = os.path.join(stage, "theme.xml")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


def validate(src):
    with open(os.path.join(src, "theme.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    check(os.path.join(src, "icon.png"), "png", (64, 64))
    check(os.path.join(src, "preview.png"), "png", (480, 270))
    check(os.path.join(src, "bg_hd.jpg"), "jpeg", (1920, 1080))
    check(os.path.join(src, "bg_sd.jpg"), "jpeg", (640, 480))
    icon_dir = os.path.join(src, "icons")
    found = [f for f in os.listdir(icon_dir) if f.lower().endswith(".png")]
    if not found:
        raise ValueError("icons/ is empty")
    for fname in found:
        slot = os.path.splitext(fname)[0]
        if slot not in ICON_SLOTS:
            raise ValueError(f"icons/{fname}: unknown slot '{slot}'")
        check(os.path.join(icon_dir, fname), "png", ICON_SLOTS[slot])
    return meta


def scratch_dir(name):
    base = os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()
    if " " in base:  # same workaround as ToolRun.MakeScratchDir
        base = os.path.join(os.path.splitdrive(base)[0] + os.sep, "ProgramData")
    path = os.path.join(base, "p3t-build", name)
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", help="folder containing p3tcompiler.exe")
    ap.add_argument("--out", default=os.path.join(HERE, "dist"))
    ap.add_argument("--only", help="build just this theme folder name")
    ap.add_argument("--dry-run", action="store_true", help="validate and write the XML, do not run the compiler")
    args = ap.parse_args()

    names = sorted(d for d in os.listdir(THEMES) if os.path.isdir(os.path.join(THEMES, d)))
    if args.only:
        names = [n for n in names if n == args.only]
    if not names:
        sys.exit("no themes found")

    compiler = None
    if not args.dry_run:
        if not args.tools:
            sys.exit("--tools is required unless --dry-run")
        compiler = os.path.abspath(os.path.join(args.tools, "p3tcompiler.exe"))
        if not os.path.isfile(compiler):
            sys.exit(f"p3tcompiler.exe not found in {args.tools}")
        if os.name != "nt":
            sys.exit("p3tcompiler.exe is a Windows program; run this on Windows (or use --dry-run)")

    os.makedirs(args.out, exist_ok=True)
    failed = []
    for name in names:
        src = os.path.join(THEMES, name)
        print(f"== {name}")
        try:
            meta = validate(src)
            stage = scratch_dir(name)
            xml_path = write_xml(src, stage, meta)
            if args.dry_run:
                shutil.copyfile(xml_path, os.path.join(args.out, f"{name}.theme.xml"))
                print(f"   ok: {meta['name']} (XML written, compiler not run)")
                continue
            proc = subprocess.run([compiler, xml_path], cwd=os.path.dirname(compiler),
                                  stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)
            print((proc.stdout + proc.stderr).strip())
            produced = os.path.splitext(xml_path)[0] + ".p3t"
            if proc.returncode != 0 or not os.path.isfile(produced):
                raise RuntimeError(f"p3tcompiler failed (exit {proc.returncode})")
            final = os.path.join(args.out, f"M3_Expressive_{name.capitalize()}.p3t")
            shutil.copyfile(produced, final)
            print(f"   built {final} ({os.path.getsize(final)} bytes)")
        except Exception as exc:  # keep going so one bad theme shows all the errors
            print(f"   FAILED: {exc}")
            failed.append(name)
    if failed:
        sys.exit("failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
