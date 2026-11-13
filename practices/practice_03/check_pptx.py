"""Check slide titles in output.pptx and report.

This script:
- Loads practices/practice_03/output.pptx
- Prints a list of slide titles (one per slide)
- Returns exit code 0 if there are at least 5 slides and all titles are non-empty
  Otherwise returns exit code 1

It attempts to import python-pptx; if missing, installs it into the current
Python environment via `python -m pip install python-pptx`.

Style: follows rules from STYLEGUIDE.md (PEP 8 excerpt for practice 3).
"""

from __future__ import annotations

import os
import site
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

PPTX_PATH = os.path.join(os.path.dirname(__file__), "output.pptx")


def ensure_python_pptx() -> None:
    """Ensure python-pptx is importable; install via pip if missing.

    Minimal bootstrap to avoid adding repo-managed virtualenvs here.
    """

    try:
        import pptx  # noqa: F401
        return
    except ImportError:
        pass

    # Use a local venv alongside this script (shared with lint.py convention)
    base_dir = os.path.dirname(__file__)
    venv_dir = os.path.join(base_dir, ".venv")
    venv_python = os.path.join(venv_dir, "bin", "python")

    if not os.path.isdir(venv_dir):
        print("[check_pptx] Creating local venv at", venv_dir, file=sys.stderr)
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])

    # Install dependency inside the venv
    print("[check_pptx] Installing dependency in venv: python-pptx", file=sys.stderr)
    subprocess.check_call([venv_python, "-m", "pip", "install", "python-pptx"]) 

    # Re-run this script under the venv interpreter so imports succeed
    if os.path.realpath(sys.executable) != os.path.realpath(venv_python):
        script_path = os.path.abspath(__file__)
        # Use subprocess and exit with child's code to avoid environment quirks
        proc = subprocess.run([venv_python, script_path] + sys.argv[1:], check=False)
        sys.exit(proc.returncode)


def extract_titles(presentation_cls=None) -> tuple[list[str], list[str]]:
    """Return (titles, warnings) extracted from PPTX.

    Strategy:
    - Prefer slide.shapes.title if present (when python-pptx is available)
    - Fallback to XML unzip/parse otherwise
    """

    if presentation_cls is not None:
        prs = presentation_cls(PPTX_PATH)
        titles: list[str] = []
        warnings: list[str] = []

        for idx, slide in enumerate(prs.slides, start=1):
            text = ""
            title_shape = getattr(slide.shapes, "title", None)
            if title_shape is not None and hasattr(title_shape, "text"):
                # Some shapes may not expose .text; guard by attribute check
                text = (title_shape.text or "").strip()

            if not text:
                for shape in slide.shapes:
                    if getattr(shape, "has_text_frame", False) and hasattr(shape, "text"):
                        cand = (shape.text or "").strip()
                        if cand:
                            text = cand
                            warnings.append(
                                f"Slide {idx}: title placeholder missing; used first text shape"
                            )
                            break

            titles.append(text)

        return titles, warnings

    # Fallback: raw XML parse (no python-pptx)
    titles: list[str] = []
    warnings: list[str] = [
        "python-pptx unavailable; used XML fallback for text extraction"
    ]
    with zipfile.ZipFile(PPTX_PATH, "r") as zf:
        slide_names = sorted(
            [n for n in zf.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
        )
        ns = {
            "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        }
        for name in slide_names:
            with zf.open(name) as fp:
                tree = ET.parse(fp)
            root = tree.getroot()
            # Find first text chunk: <a:t>
            text = ""
            for elt in root.findall('.//a:t', ns):
                if elt.text and elt.text.strip():
                    text = elt.text.strip()
                    break
            titles.append(text)
    return titles, warnings


def print_report(titles: list[str], warnings: list[str]) -> None:
    print("PPTX Title Check Report")
    print(f"File: {PPTX_PATH}")
    print(f"Total slides: {len(titles)}")
    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"- {w}")

    print("Titles:")
    for i, t in enumerate(titles, start=1):
        shown = t if t else "[EMPTY]"
        print(f"- {i}: {shown}")


def evaluate(titles: list[str]) -> tuple[bool, list[str]]:
    ok = True
    reasons: list[str] = []
    if len(titles) < 5:
        ok = False
        reasons.append("fewer than 5 slides")
    empties = [i for i, t in enumerate(titles, start=1) if not t]
    if empties:
        ok = False
        reasons.append("empty titles: " + ", ".join(map(str, empties)))
    return ok, reasons


def main() -> int:
    ensure_python_pptx()

    # Attempt to import python-pptx after ensuring environment
    # Force site-packages to the front of sys.path to avoid namespace shadowing
    sp_list = []
    if hasattr(site, "getsitepackages"):
        # getsitepackages may not exist in some embedders; guard via hasattr
        sp_list = list(reversed(site.getsitepackages()))
    for sp in sp_list:
        if sp not in sys.path:
            sys.path.insert(0, sp)

    try:
        from pptx import Presentation  # type: ignore
    except ImportError:
        # Second-chance import: avoid implicit namespace packages like skills/pptx
        # that can shadow the installed python-pptx distribution.
        for path in list(sys.path):
            if ("/skills" in path or path.rstrip(os.sep).endswith("skills")) and path in sys.path:
                sys.path.remove(path)
        sys.modules.pop("pptx", None)
        try:
            from pptx import Presentation  # type: ignore
        except ImportError:
            Presentation = None

    try:
        titles, warnings = extract_titles(Presentation)
    except FileNotFoundError:
        print(f"Error: file not found: {PPTX_PATH}", file=sys.stderr)
        return 1
    except (OSError, ValueError, ET.ParseError) as exc:
        print(f"Error while reading PPTX: {exc}", file=sys.stderr)
        return 1

    print_report(titles, warnings)
    ok, reasons = evaluate(titles)
    if ok:
        print("Result: PASS")
        return 0
    print("Result: FAIL (" + "; ".join(reasons) + ")")
    return 1


if __name__ == "__main__":
    sys.exit(main())
