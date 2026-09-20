"""model_sync.py: copy the constants in data/ladder-model.json into the three places that hard code them.

Run after tools/model_refit.py --write:  python tools/model_sync.py [path to the btc-monitor clone]
It rewrites MODEL_V2 in index.html, LADDER2_* in tools/playbook_refresh.py and, when the monitor path is given, _CLOCK,
_MODEL_A, _MODEL_B and _BANDS in its mstr_gap.py. Then run the monitor tests and the Playbook self-test: both pin the ports
to the site's numbers and will need new pins after a real refit.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = json.load(open(os.path.join(ROOT, "data", "ladder-model.json"), encoding="utf-8"))
assert all(b["kind"] in ("exp", "const") for b in M["bands"]), "the ports implement exp and const only"
Y, MO, D = (int(x) for x in M["clock_start"].split("-"))


def rewrite(path, pattern, text, flags=re.S):
    s = open(path, encoding="utf-8", newline="").read(); nl = "\r\n" if "\r\n" in s else "\n"
    new, n = re.subn(pattern, lambda _: text.replace("\n", nl), s, count=1, flags=flags)
    assert n == 1, "pattern not found in %s" % path
    open(path, "w", encoding="utf-8", newline="").write(new); print("synced", os.path.relpath(path, ROOT) if path.startswith(ROOT) else path)


js_bands = ",\n".join('  { q:%s, label:"%s", kind:"%s", p:[%s] }' % (("%g" % b["q"]), b["label"], b["kind"], ", ".join(repr(float(x)) if x else "0" for x in b["p"])) for b in M["bands"])
rewrite(os.path.join(ROOT, "index.html"), r"const MODEL_V2 = \{.*?\] \};",
        'const MODEL_V2 = { name:"v2", clock:"%s", A:%r, B:%r, bands:[\n%s ] };' % (M["clock_start"], M["slope"], M["intercept"], js_bands))

py_bands = ", ".join("(%s, %r, %s)" % (("%g" % b["q"]), float(b["p"][0]), repr(float(b["p"][1])) if len(b["p"]) > 1 else "None") for b in M["bands"])
rewrite(os.path.join(ROOT, "tools", "playbook_refresh.py"), r"LADDER2_CLOCK = datetime\(.*?\r?\n\r?\n",
        "LADDER2_CLOCK = datetime(%d, %d, %d, tzinfo=timezone.utc)\nLADDER2_A, LADDER2_B = %r, %r\nLADDER2_BANDS = [%s]\n\n" % (Y, MO, D, M["slope"], M["intercept"], py_bands))
if len(sys.argv) > 1:
    rewrite(os.path.join(sys.argv[1], "mstr_gap.py"), r"_CLOCK = datetime\(.*?\r?\n_MODEL_A, _MODEL_B = .*?\r?\n_BANDS = \[.*?\]\r?\n",
            "_CLOCK = datetime(%d, %d, %d, tzinfo=timezone.utc)\n_MODEL_A, _MODEL_B = %r, %r\n_BANDS = [%s]\n" % (Y, MO, D, M["slope"], M["intercept"], py_bands))
