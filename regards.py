#!/usr/bin/env python3
"""Reference interpreter for `Regards,` — a language written as a corporate email thread."""

import re
import sys
import time
import traceback

SIGN_OFFS = {"best", "regards", "thanks", "cheers", "warm regards", "kind regards",
             "best regards", "many thanks", "sincerely"}
NONZERO_SIGN_OFFS = {"regards"}  # a bare "Regards," is not a happy exit
GREETING = re.compile(r"^(hi|hello|hey|dear)\b.*,$", re.I)
THREAD_HEADER = re.compile(r"^on .*wrote:$", re.I)
PRAGMA_IPHONE = re.compile(r"^sent from my iphone$", re.I)


class RegardsError(Exception):
    pass


class Bump(Exception):
    pass


class SignOff(Exception):
    pass


def fail(line, msg):
    first, _, rest = msg.partition("\n")
    where = f" (line {line})" if line else ""
    raise RegardsError(f"error: {first}{where}" + (f"\n{rest}" if rest else ""))


# ---------------------------------------------------------------- lexing

def normalize(text):
    """Undo what email clients do to text: smart quotes, dashes, whitespace."""
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = re.sub(r"\s*(—|–|--|-)\s+", " - ", text)
    return re.sub(r"\s+", " ", text).strip()


def lex(source):
    """Yield (quote_depth, text, line_number) for every line. `> >` and `>>` both count 2."""
    out = []
    for n, raw in enumerate(source.splitlines(), 1):
        m = re.match(r"^((?:\s*>)*)\s?(.*)$", raw)
        depth = m.group(1).count(">")
        out.append((depth, normalize(m.group(2)), n))
    return out


def var_key(name):
    """`open reqs`, `req`, `Reqs` all name the same variable: last word, singular, lowercase."""
    word = name.lower().split()[-1]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    return word


# ---------------------------------------------------------------- parsing

def parse_message(lines, base):
    """Parse one message whose own text sits at quote depth `base`.

    Returns (body_nodes, sign_off, people) where people maps first name -> body nodes.
    """
    i = 0
    while i < len(lines) and not (lines[i][0] == base and GREETING.match(lines[i][1])):
        i += 1
    if i == len(lines):
        fail(lines[0][2] if lines else None, "no greeting. Who is this addressed to?")
    i += 1

    body = []
    sign_off = None
    while i < len(lines):
        depth, text, n = lines[i]
        i += 1
        if not text:
            continue
        if depth == base and text.endswith(",") and text[:-1].lower() in SIGN_OFFS:
            sign_off = text[:-1].lower()
            break
        if depth < base:
            fail(n, "line is quoted less than the message it belongs to")
        body.append((depth - base, text, n))
    if sign_off is None:
        fail(None, "no sign-off. The thread is still open.")

    people = {}
    signature_seen = False
    while i < len(lines):
        depth, text, n = lines[i]
        i += 1
        if not text:
            continue
        if depth == base and THREAD_HEADER.match(text):
            sender = text.rsplit(",", 1)[-1]
            sender = re.sub(r"<[^>]*>|wrote:", "", sender, flags=re.I).split()
            if not sender:
                fail(n, "can't tell who wrote this quoted message")
            quoted = []
            while i < len(lines) and (lines[i][0] > base or not lines[i][1]):
                quoted.append(lines[i])
                i += 1
            q_body, _, q_people = parse_message(quoted, base + 1)
            people[sender[0].lower()] = q_body
            for name, nodes in q_people.items():
                people.setdefault(name, nodes)
        elif depth == base and PRAGMA_IPHONE.match(text):
            print("warning: `Sent from my iPhone` present; optimizations disabled.", file=sys.stderr)
        elif depth == base and not signature_seen:
            signature_seen = True
        elif base == 0:
            fail(n, f"unreachable code after `{sign_off.title()},`.\n"
                    "       Nothing below a sign-off is read. This is true of email generally.")
    return build_tree(body, 0, 0)[0], sign_off, people


def build_tree(items, i, depth):
    nodes = []
    while i < len(items):
        d, text, n = items[i]
        if d < depth:
            break
        if d > depth:
            fail(n, "quoted deeper than anything it could be replying to")
        node = parse_statement(text, n)
        i += 1
        if text.endswith(":"):
            node["body"], i = build_tree(items, i, depth + 1)
            if not node["body"]:
                fail(n, "this needs a reply quoted underneath it")
        nodes.append(node)
    return nodes, i


NUM = r"-?\d+"
V = r"[a-z][a-z' ]*?"

EXPR_PATTERNS = [
    (rf"^what's left after splitting (?P<b>{V}) across (?P<a>.+)$", "mod"),
    (rf"^(?P<n>{NUM})$", "num"),
    (rf"^(?P<v>{V})$", "var"),
]

COND_PATTERNS = [
    (rf"^there's nothing left after splitting (?P<v>{V}) across (?P<x>.+)$", "divisible"),
    (rf"^we still have (?P<v>{V})$", "positive"),
    (rf"^(?P<v>{V}) is at zero$", "zero"),
    (rf"^we're under (?P<x>.+?) on (?P<v>{V})$", "lt"),
    (rf"^we're over (?P<x>.+?) on (?P<v>{V})$", "gt"),
]

STATEMENT_PATTERNS = [
    (rf"^just to level-set, we have (?P<x>{NUM}) (?P<v>{V})\.$", "set"),
    (rf"^just to level-set, (?P<v>{V}) is (?P<x>.+)\.$", "set"),
    (rf"^per the attached, (?P<v>{V}) is now (?P<x>.+)\.$", "set"),
    (rf"^(?P<v>{V}) is off the table\.$", "zero"),
    (rf"^good news - we've added another (?P<v>{V})\.$", "inc"),
    (rf"^quick flag: one (?P<v>{V}) is now closed\.$", "dec"),
    (rf"^doubling down on (?P<v>{V})\.$", "double"),
    (rf"^let's cut (?P<v>{V}) in half\.$", "halve"),
    (rf"^rolling (?P<x>.+?) into (?P<v>{V})\.$", "add"),
    (rf"^backing (?P<x>.+?) out of (?P<v>{V})\.$", "sub"),
    (rf"^scaling (?P<v>{V}) by (?P<x>.+)\.$", "mul"),
    (rf"^splitting (?P<v>{V}) across (?P<x>.+)\.$", "div"),
    (r"^that said, if (?P<c>.+):$", "elif"),
    (r"^that said:$", "else"),
    (r"^if (?P<c>.+):$", "if"),
    (r"^per my last email, while (?P<c>.+):$", "while"),
    (r"^bumping this\.$", "bump"),
    (r"^as discussed, (?P<p>[a-z]+)\.$", "call"),
    (r'^circling back on "(?P<s>.*)"\.$', "print_lit"),
    (rf"^circling back on (?P<x>.+)\.$", "print"),
    (r"^\+leadership for visibility\.$", "flush"),
    (r"^(\+[a-z]+|looping in [a-z]+\.)$", "noop"),
    (r"^(thoughts\?|please advise\.)$", "read"),
    (r"^sorry for the delay!$", "sleep"),
    (r"^thanks in advance\.$", "tia"),
]


def parse_expr(text, n):
    for pat, kind in EXPR_PATTERNS:
        m = re.match(pat, text, re.I)
        if m:
            g = m.groupdict()
            if kind == "mod":
                return ("mod", var_key(g["b"]), parse_expr(g["a"], n))
            if kind == "num":
                return ("num", int(g["n"]))
            return ("var", var_key(g["v"]))
    fail(n, f"not sure what `{text}` means. Can you clarify?")


def parse_cond(text, n):
    for pat, kind in COND_PATTERNS:
        m = re.match(pat, text, re.I)
        if m:
            g = m.groupdict()
            x = parse_expr(g["x"], n) if "x" in g else None
            return (kind, var_key(g["v"]), x)
    fail(n, f"not sure what `{text}` means as a condition. Can we align offline?")


def parse_statement(text, n):
    for pat, kind in STATEMENT_PATTERNS:
        m = re.match(pat, text, re.I)
        if not m:
            continue
        g = m.groupdict()
        node = {"kind": kind, "line": n}
        if g.get("v"):
            node["var"] = var_key(g["v"])
        if g.get("x"):
            node["expr"] = parse_expr(g["x"], n)
        if g.get("c"):
            node["cond"] = parse_cond(g["c"], n)
        if g.get("p"):
            node["person"] = g["p"].lower()
        if "s" in g:
            node["text"] = m.group("s")
        return node
    fail(n, f"`{text}` isn't something I can action")


# ---------------------------------------------------------------- execution

class Interpreter:
    def __init__(self, people, stdin=sys.stdin, stdout=sys.stdout):
        self.env = {}
        self.people = people
        self.stdin = stdin
        self.stdout = stdout
        self.last_var = None
        self.last_ok = True
        self.depth = 0

    def get(self, name, line):
        if name not in self.env:
            fail(line, f"nobody told me about `{name}`. Can you send it over?")
        self.last_var = name
        return self.env[name]

    def eval(self, expr, line):
        kind = expr[0]
        if kind == "num":
            return expr[1]
        if kind == "var":
            return self.get(expr[1], line)
        divisor = self.eval(expr[2], line)
        if divisor == 0:
            fail(line, "splitting across zero. That's not a realistic plan")
        return self.get(expr[1], line) % divisor

    def test(self, cond, line):
        kind, var, x = cond
        v = self.get(var, line)
        if kind == "positive":
            return v > 0
        if kind == "zero":
            return v == 0
        if kind == "lt":
            return v < self.eval(x, line)
        if kind == "gt":
            return v > self.eval(x, line)
        d = self.eval(x, line)
        if d == 0:
            fail(line, "splitting across zero. That's not a realistic plan")
        return v % d == 0

    def run_message(self, nodes):
        """Bumping re-sends the whole message, so only a message catches Bump."""
        while True:
            try:
                self.run_block(nodes)
                return
            except Bump:
                continue

    def run_block(self, nodes):
        i = 0
        while i < len(nodes):
            node = nodes[i]
            if node["kind"] == "if":
                chain = [node]
                while i + 1 < len(nodes) and nodes[i + 1]["kind"] in ("elif", "else"):
                    i += 1
                    chain.append(nodes[i])
                    if nodes[i]["kind"] == "else":
                        break
                for branch in chain:
                    if branch["kind"] == "else" or self.test(branch["cond"], branch["line"]):
                        self.run_block(branch["body"])
                        break
            elif node["kind"] in ("elif", "else"):
                fail(node["line"], "`That said` with nothing to push back on")
            else:
                self.execute(node)
            i += 1

    def execute(self, node):
        k, line = node["kind"], node["line"]
        var = node.get("var")
        if k == "set":
            self.env[var] = self.eval(node["expr"], line)
            self.last_var = var
        elif k == "zero":
            self.env[var] = 0
            self.last_var = var
        elif k in ("inc", "dec", "double", "halve"):
            v = self.get(var, line)
            self.env[var] = {"inc": v + 1, "dec": v - 1, "double": v * 2, "halve": v // 2}[k]
        elif k in ("add", "sub", "mul", "div"):
            a = self.eval(node["expr"], line)
            b = self.get(var, line)
            if k == "div" and a == 0:
                fail(line, "splitting across zero. That's not a realistic plan")
            self.env[var] = {"add": b + a, "sub": b - a, "mul": b * a, "div": b // a if a else 0}[k]
        elif k == "while":
            while self.test(node["cond"], line):
                self.run_block(node["body"])
        elif k == "bump":
            raise Bump()
        elif k == "call":
            body = self.people.get(node["person"])
            if body is None:
                fail(line, f"{node['person'].title()} isn't on this thread. Happy to resend")
            self.depth += 1
            if self.depth > MAX_CALL_DEPTH:
                fail(line, "this thread has too many replies. Let's set up a meeting")
            try:
                self.run_message(body)
            finally:
                self.depth -= 1
        elif k == "print_lit":
            print(node["text"], file=self.stdout)
        elif k == "print":
            print(self.eval(node["expr"], line), file=self.stdout)
        elif k == "flush":
            self.stdout.flush()
        elif k == "read":
            if self.last_var is None:
                fail(line, "asking for thoughts on nothing in particular")
            raw = self.stdin.readline()
            try:
                self.env[self.last_var] = int(raw.strip())
                self.last_ok = True
            except ValueError:
                self.last_ok = False
        elif k == "sleep":
            time.sleep(1)
        elif k == "tia":
            if not self.last_ok:
                print(f"warning: line {line}: thanks in advance, but it didn't happen.", file=sys.stderr)


MAX_CALL_DEPTH = 1000
# Each nested call costs several Python frames, and more inside loops and ifs.
PYTHON_RECURSION_LIMIT = 50_000


def run(source, stdin=sys.stdin, stdout=sys.stdout):
    """Run a program. Returns the process exit code."""
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, PYTHON_RECURSION_LIMIT))
    try:
        body, sign_off, people = parse_message(lex(source), 0)
        Interpreter(people, stdin, stdout).run_message(body)
    except RecursionError:
        raise RegardsError("error: this thread has too many replies. Let's set up a meeting") from None
    finally:
        sys.setrecursionlimit(old_limit)
    return 1 if sign_off in NONZERO_SIGN_OFFS else 0


def main(argv):
    if len(argv) != 2:
        print("usage: regards.py <program.rgrd>", file=sys.stderr)
        return 2
    try:
        with open(argv[1], encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        print(f"error: couldn't open `{argv[1]}` ({e.strerror}). Can you reattach?", file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print(f"error: `{argv[1]}` isn't UTF-8 text. The attachment seems corrupted.", file=sys.stderr)
        return 2
    try:
        return run(source)
    except RegardsError as e:
        print(e, file=sys.stderr)
        return 2
    except Exception:
        traceback.print_exc()
        print("internal error: this is a bug in the interpreter, not in your email.", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
