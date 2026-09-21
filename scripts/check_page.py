#!/usr/bin/env python3
"""Refuse to publish a page whose JavaScript does not parse.

Every table and both maps on this page are rendered by the inline script, so a single
stray character in the generated block takes the whole page down while the HTML still
looks perfectly healthy to anything that only reads text. That is exactly how a broken
build reached production once: the generated block got truncated by one character, the
page served a 200 with correct-looking markup, and every table came up empty.

Run after build.py. Needs node; skips with a warning if node is not installed.
"""
import re, shutil, subprocess, sys, tempfile, os

PAGE = os.path.join(os.path.dirname(__file__), "..", "index.html")

def main():
    html = open(PAGE, encoding="utf-8").read()

    # the generated block must still end its comment line properly
    i = html.find("/* ---- GENERATED:BEGIN")
    if i == -1:
        print("check: no generated block found", file=sys.stderr); return 1
    if not html[i:html.index("\n", i)].rstrip().endswith("*/"):
        print("check: the GENERATED:BEGIN line is truncated -- the block boundary moved",
              file=sys.stderr)
        return 1

    if not shutil.which("node"):
        print("check: node not installed, skipping the syntax check")
        return 0

    blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
    if not blocks:
        print("check: no inline script found", file=sys.stderr); return 1

    for n, body in enumerate(blocks, 1):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(body); path = fh.name
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        os.unlink(path)
        if r.returncode != 0:
            print("check: inline script %d does not parse -- refusing to publish\n%s"
                  % (n, r.stderr.strip()), file=sys.stderr)
            return 1

    print("check: %d inline script(s) parse" % len(blocks))
    return 0

if __name__ == "__main__":
    sys.exit(main())
