"""Does your email compile? The Regards playground, as one small Flask app."""

import sys
from email import policy
from email.parser import BytesHeaderParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
# In the repo, regards.py and the examples sit one folder up. In the Vercel bundle they sit alongside.
ROOT = HERE if (HERE / "regards.py").exists() else HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))  # run this interpreter rather than an installed copy

from flask import Flask, abort, jsonify, render_template, request, send_file  # noqa: E402

import regards  # noqa: E402
import sandbox  # noqa: E402

EXAMPLES = ROOT / "examples"
MAX_SOURCE = 200_000
# Shown first, in this order. attachment.rgrd needs a file from disk, which the playground won't read.
FEATURED = ["countdown.rgrd", "hello.rgrd", "fizzbuzz.rgrd", "standup.rgrd", "unread.rgrd", "typos.rgrd",
            "truth_machine.rgrd", "planning_poker.rgrd", "forecast.rgrd", "reply_all.rgrd", "ooo.rgrd",
            "cat.rgrd", "brainfuck.rgrd", "budget.eml"]
HIDDEN = {"attachment.rgrd", "finance.rgrd"}
SUGGESTED_INPUT = {
    "truth_machine.rgrd": "1\n",
    "cat.rgrd": "Anything you type here comes straight back out.\n",
    "brainfuck.rgrd": "++++++++[>++++[>++>+++>+++>+<<<<-]>+>+>->>+[<]<-]>>.>---.+++++++..+++.>>.<-.<.+++.------."
                      "--------.>>+.>++.!",
}

app = Flask(__name__)
app.config.update(RUN_TIMEOUT=5, MAX_CONTENT_LENGTH=2 * 1024 * 1024)


def examples():
    found = [p for p in EXAMPLES.glob("*") if p.suffix in (".rgrd", ".eml") and p.name not in HIDDEN]
    rank = {name: i for i, name in enumerate(FEATURED)}
    return sorted(found, key=lambda p: (rank.get(p.name, len(FEATURED)), p.name))


def subject_of(path):
    if path.suffix == ".eml":
        with path.open("rb") as f:
            return str(BytesHeaderParser(policy=policy.default).parse(f).get("Subject", ""))
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lower().startswith("subject:"):
            return line.split(":", 1)[1].strip()
    return ""


@app.get("/")
def index():
    return render_template("index.html", version=regards.__version__)


@app.post("/api/run")
def run():
    timeout = app.config["RUN_TIMEOUT"]
    upload = request.files.get("eml")
    if upload:
        result = sandbox.run_program(eml=upload.read(), stdin=request.form.get("stdin", ""), timeout=timeout)
    else:
        body = request.get_json(silent=True) or {}
        source, stdin = str(body.get("source", "")), str(body.get("stdin", ""))
        if len(source) + len(stdin) > MAX_SOURCE:
            abort(413)
        result = sandbox.run_program(source=source, stdin=stdin, timeout=timeout)
    return jsonify(result)


@app.get("/api/examples")
def list_examples():
    return jsonify([{"name": p.name, "kind": p.suffix[1:], "subject": subject_of(p),
                     "stdin": SUGGESTED_INPUT.get(p.name, "")} for p in examples()])


@app.get("/api/examples/<path:name>")
def example(name):
    match = next((p for p in examples() if p.name == name), None)
    if match is None:
        abort(404)
    mimetype = "message/rfc822" if match.suffix == ".eml" else "text/plain; charset=utf-8"
    return send_file(match, mimetype=mimetype)
