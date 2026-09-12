#!/usr/bin/env python3
"""Reference interpreter for `Regards,` — a language written as a corporate email thread."""

import os
import re
import sys
import threading
import time
import traceback

SIGN_OFFS = {"best", "regards", "thanks", "cheers", "warm regards", "kind regards",
             "best regards", "many thanks", "sincerely"}
NONZERO_SIGN_OFFS = {"regards"}  # a bare "Regards," is not a happy exit
GREETING = re.compile(r"^(hi|hello|hey|dear)\b.*,$", re.I)
THREAD_HEADER = re.compile(r"^on .*wrote:$", re.I)
CC_HEADER = re.compile(r"^cc:(.*)$", re.I)
PRAGMA_IPHONE = re.compile(r"^sent from my iphone$", re.I)


class RegardsError(Exception):
    pass


class Bump(Exception):
    pass


class SignOff(Exception):
    pass


class NetNet(Exception):
    """`Net-net, <expr>.` ends the current message and carries its value back to the caller."""

    def __init__(self, value, line):
        super().__init__(value)
        self.value = value
        self.line = line


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


def first_names(header):
    """`Dave Okonkwo <dave@example.com>, Priya` -> ["dave", "priya"]"""
    names = []
    for entry in header.split(","):
        words = re.sub(r"<[^>]*>", "", entry).split()
        if words:
            names.append(words[0].lower())
    return names


# ---------------------------------------------------------------- parsing

def parse_message(lines, base):
    """Parse one message whose own text sits at quote depth `base`.

    Returns (body_nodes, sign_off, people) where people maps first name -> body nodes.
    """
    i = 0
    cc = []
    while i < len(lines) and not (lines[i][0] == base and GREETING.match(lines[i][1])):
        header = CC_HEADER.match(lines[i][1]) if lines[i][0] == base else None
        if header:
            cc += first_names(header.group(1))
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

    tree = build_tree(body, 0, 0)[0]
    for node in walk(tree):
        if node["kind"] == "reply_all":
            node["cc"] = cc
    return tree, sign_off, people


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


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.get("body", []))


NUM = r"-?\d+"
V = r"[a-z][a-z' ]*?"

EXPR_PATTERNS = [
    (rf"^what's left after splitting (?P<b>{V}) across (?P<a>.+)$", "mod"),
    (r"^(?P<p>[a-z]+)'s take(?: on (?P<a>.+))?$", "take"),
    (rf"^(?P<n>{NUM})$", "num"),
    (rf"^(?P<v>{V})$", "var"),
]

COND_PATTERNS = [
    (rf"^there's nothing left after splitting (?P<v>{V}) across (?P<x>.+)$", "divisible"),
    (rf"^we still have (?P<v>{V})$", "positive"),
    (rf"^(?P<v>{V}) is at zero$", "zero"),
    # greedy, so `we're under Dave's take on budget on sprint` splits at the last "on"
    (rf"^we're under (?P<x>.+) on (?P<v>{V})$", "lt"),
    (rf"^we're over (?P<x>.+) on (?P<v>{V})$", "gt"),
]

STATEMENT_PATTERNS = [
    (rf"^just to level-set, we have (?P<x>{NUM}) (?P<v>{V})\.$", "declare"),
    (rf"^just to level-set, (?P<v>{V}) is (?P<x>.+)\.$", "declare"),
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
    (r"^as discussed, (?P<p>[a-z]+), re: (?P<x>.+)\.$", "call"),
    (r"^as discussed, (?P<p>[a-z]+)\.$", "call"),
    (r"^net-net, (?P<x>.+)\.$", "net_net"),
    (r"^happy to take this offline\.$", "offline"),
    (r"^i(?: am|'m) currently ooo, returning (?P<d>.+):$", "ooo"),
    (r"^resending with the attachment: (?P<f>.+)\.$", "attach"),
    (r"^replying all(?:, re: (?P<x>.+))?\.$", "reply_all"),
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
            if kind == "take":
                return ("take", g["p"].lower(), parse_expr(g["a"], n) if g["a"] else None)
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
        if g.get("f"):
            node["file"] = g["f"]
        if "s" in g:
            node["text"] = m.group("s")
        return node
    fail(n, f"`{text}` isn't something I can action")


# ---------------------------------------------------------------- execution

class Interpreter:
    def __init__(self, people, stdin=sys.stdin, stdout=sys.stdout, folder="."):
        self.globals = {}
        self.scopes = [self.globals]
        self.people = people
        self.stdin = stdin
        self.stdout = stdout
        self.folder = folder
        self.last_var = None
        self.last_ok = True
        self.depth = 0

    def fork(self):
        """Another reader of the same thread: shared variables and people, its own call stack."""
        child = Interpreter(self.people, self.stdin, self.stdout, self.folder)
        child.globals = self.globals
        child.scopes = [self.globals]
        child.depth = self.depth
        return child

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope
        return None

    def get(self, name, line):
        scope = self.lookup(name)
        if scope is None:
            fail(line, f"nobody told me about `{name}`. Can you send it over?")
        self.last_var = name
        return scope[name]

    def declare(self, name, value):
        self.scopes[-1][name] = value
        self.last_var = name

    def assign(self, name, value):
        """Update the nearest variable with this name, or create it in the innermost scope."""
        scope = self.lookup(name)
        if scope is None:
            scope = self.scopes[-1]
        scope[name] = value
        self.last_var = name

    def say(self, text):
        # one write per line, so people replying all at once can't split each other's lines
        self.stdout.write(f"{text}\n")

    def eval(self, expr, line):
        kind = expr[0]
        if kind == "num":
            return expr[1]
        if kind == "var":
            return self.get(expr[1], line)
        if kind == "take":
            _, person, arg = expr
            value = self.call(person, arg, line)
            if value is None:
                fail(line, f"{person.title()} signed off without a net-net. What's the takeaway?")
            return value
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

    def call(self, person, arg, line):
        """Run a person's message. Returns their net-net, or None if they just signed off.

        A person sees the shared variables but not the caller's offline ones. Calling with
        `re:` takes the call offline: the person gets a private scope holding `the ask`.
        """
        body = self.people.get(person)
        if body is None:
            fail(line, f"{person.title()} isn't on this thread. Happy to resend")
        if self.depth >= MAX_CALL_DEPTH:
            fail(line, "this thread has too many replies. Let's set up a meeting")
        scopes = [self.globals] if arg is None else [self.globals, {"ask": self.eval(arg, line)}]
        saved, self.scopes = self.scopes, scopes
        self.depth += 1
        try:
            self.run_message(body)
            return None
        except NetNet as reply:
            return reply.value
        finally:
            self.scopes = saved
            self.depth -= 1

    def attach(self, name, line):
        """Everyone quoted in the attached email becomes callable. Its own body never runs."""
        try:
            with open(os.path.join(self.folder, name), encoding="utf-8") as f:
                source = f.read()
        except (OSError, UnicodeDecodeError):
            fail(line, f"the attachment `{name}` didn't come through. Can you resend?")
        try:
            _, _, people = parse_message(lex(source), 0)
        except RegardsError as e:
            fail(line, f"the attachment `{name}` is garbled: {str(e).removeprefix('error: ')}")
        self.people.update(people)

    def reply_all(self, node, line):
        """Everyone on cc replies at once. They share variables and nobody coordinates."""
        if not node["cc"]:
            fail(line, "nobody is cc'd. Reply-all to whom?")
        for person in node["cc"]:
            if person not in self.people:
                fail(line, f"{person.title()} isn't on this thread. Happy to resend")
        arg = ("num", self.eval(node["expr"], line)) if "expr" in node else None
        errors = []

        def reply(fork, person):
            try:
                fork.call(person, arg, line)
            except BaseException as e:
                errors.append(e)

        replies = [threading.Thread(target=reply, args=(self.fork(), person)) for person in node["cc"]]
        old_size = threading.stack_size(THREAD_STACK_SIZE)
        try:
            for thread in replies:
                thread.start()
        finally:
            threading.stack_size(old_size)
        for thread in replies:
            thread.join()
        if errors:
            raise errors[0]

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
            if node["kind"] == "offline":
                self.scopes.append({})
                try:
                    self.run_block(nodes[i + 1:])
                finally:
                    self.scopes.pop()
                return
            if node["kind"] == "ooo":
                try:
                    self.run_block(nodes[i + 1:])
                except RegardsError:
                    self.run_block(node["body"])
                return
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
        if k == "declare":
            self.declare(var, self.eval(node["expr"], line))
        elif k == "set":
            self.assign(var, self.eval(node["expr"], line))
        elif k == "zero":
            self.assign(var, 0)
        elif k in ("inc", "dec", "double", "halve"):
            v = self.get(var, line)
            self.assign(var, {"inc": v + 1, "dec": v - 1, "double": v * 2, "halve": v // 2}[k])
        elif k in ("add", "sub", "mul", "div"):
            a = self.eval(node["expr"], line)
            b = self.get(var, line)
            if k == "div" and a == 0:
                fail(line, "splitting across zero. That's not a realistic plan")
            self.assign(var, {"add": b + a, "sub": b - a, "mul": b * a, "div": b // a if a else 0}[k])
        elif k == "while":
            while self.test(node["cond"], line):
                self.run_block(node["body"])
        elif k == "bump":
            raise Bump()
        elif k == "call":
            self.call(node["person"], node.get("expr"), line)
        elif k == "net_net":
            raise NetNet(self.eval(node["expr"], line), line)
        elif k == "attach":
            self.attach(node["file"], line)
        elif k == "reply_all":
            self.reply_all(node, line)
        elif k == "print_lit":
            self.say(node["text"])
        elif k == "print":
            self.say(self.eval(node["expr"], line))
        elif k == "flush":
            self.stdout.flush()
        elif k == "read":
            if self.last_var is None:
                fail(line, "asking for thoughts on nothing in particular")
            raw = self.stdin.readline()
            try:
                self.assign(self.last_var, int(raw.strip()))
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
# Replies run on their own threads, which get a small stack by default.
THREAD_STACK_SIZE = 256 * 1024 * 1024


def run(source, stdin=sys.stdin, stdout=sys.stdout, path=None):
    """Run a program. Returns the process exit code.

    `path` is where the program lives; attachments are looked for next to it.
    """
    folder = os.path.dirname(os.path.abspath(path)) if path else "."
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, PYTHON_RECURSION_LIMIT))
    try:
        body, sign_off, people = parse_message(lex(source), 0)
        Interpreter(people, stdin, stdout, folder).run_message(body)
    except NetNet as stray:
        fail(stray.line, "`Net-net` in the original email. There's nobody to report back to")
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
        return run(source, path=argv[1])
    except RegardsError as e:
        print(e, file=sys.stderr)
        return 2
    except Exception:
        traceback.print_exc()
        print("internal error: this is a bug in the interpreter, not in your email.", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
