#!/usr/bin/env python3
"""Reference interpreter for `Regards,` — a language written as a corporate email thread."""

import difflib
import os
import random
import re
import sys
import threading
import time
import traceback
from collections import deque
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser

__version__ = "1.0.0"

SIGN_OFFS ={"best", "regards", "thanks", "cheers", "warm regards", "kind regards",
             "best regards", "many thanks", "sincerely"}
NONZERO_SIGN_OFFS = {"regards"}  # a bare "Regards," is not a happy exit
GREETING = re.compile(r"^(hi|hello|hey|dear)\b.*,$", re.I)
THREAD_HEADER = re.compile(r"^on .*wrote:$", re.I)
CC_HEADER = re.compile(r"^cc:(.*)$", re.I)
PRAGMA_IPHONE = re.compile(r"^sent from my iphone$", re.I)
POSTSCRIPT = re.compile(r"^(p\.?\s?)+s\b", re.I)
COMMENT = re.compile(r"^fyi\b", re.I)
JARGON = re.compile(r'^going forward, "(?P<x>.+?)" means "(?P<y>.+)"\.?$', re.I)
PLACEHOLDER = re.compile(r"\[([^\[\]]+)\]")
PRONOUNS = {"it", "that"}
PLEASANTRIES = {"pleasantry", "tia", "sleep"}
HR = "hr"
OUTLOOK_FROM = re.compile(r"^from:\s*(?P<who>.+)$", re.I)
OUTLOOK_FIELD = re.compile(r"^(?P<field>sent|date|to|cc|bcc|subject|importance|reply-to):\s*(?P<value>.*)$", re.I)
OUTLOOK_SEPARATOR = re.compile(r"^(_{5,}|[-\s]*(original|forwarded) message[-\s]*|begin forwarded message:)$", re.I)


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


def preprocess(lines):
    """Drop FYI lines, and expand jargon defined with `Going forward` in every line after it."""
    jargon = []
    out = []
    for depth, text, n in lines:
        definition = JARGON.match(text)
        if COMMENT.match(text):
            text = ""
        elif definition:
            jargon.insert(0, jargon_rule(definition.group("x"), definition.group("y")))
            text = ""
        elif jargon:
            text = expand_jargon(text, jargon, n)
        out.append((depth, text, n))
    return out


def jargon_rule(phrase, meaning):
    """`let's synergize on [thing]` -> a regex with one group per placeholder."""
    names = []
    pattern = ""
    for i, part in enumerate(PLACEHOLDER.split(phrase.rstrip(".!?:"))):
        if i % 2 == 0:
            pattern += re.escape(part)
            continue
        name = part.strip().lower()
        if name in names:
            pattern += f"(?P=g{names.index(name)})"
        else:
            pattern += f"(?P<g{len(names)}>.+?)"
            names.append(name)
    return re.compile(pattern + r"(?P<end>[.!?:]?)", re.I), names, meaning


def expand_jargon(text, jargon, n):
    for _ in range(MAX_JARGON_EXPANSIONS):
        for regex, names, meaning in jargon:
            m = regex.fullmatch(text)
            if m:
                break
        else:
            return text
        words = {name: m.group(f"g{i}") for i, name in enumerate(names)}
        text = PLACEHOLDER.sub(lambda p: words.get(p.group(1).strip().lower(), p.group(0)), meaning)
        if not text.endswith((".", ",", "!", "?", ":")):
            text += m.group("end") or "."
    fail(n, "this jargon goes in circles. Can someone say it in plain English?")


# ---------------------------------------------------------------- saved emails

class HtmlText(HTMLParser):
    """Just enough HTML-to-text for email: blocks become lines, blockquotes become `>` quoting."""

    BLOCKS = {"p", "div", "li", "tr", "table", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "hr"}
    HIDDEN = {"head", "style", "script", "title"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines = [[0, ""]]
        self.depth = 0
        self.hidden = 0

    def newline(self):
        if self.lines[-1][1].strip():
            self.lines.append([self.depth, ""])
        else:
            self.lines[-1][0] = self.depth

    def handle_starttag(self, tag, attrs):
        if tag in self.HIDDEN:
            self.hidden += 1
        elif tag == "blockquote":
            self.depth += 1
            self.newline()
        elif tag == "br" or tag in self.BLOCKS:
            self.newline()

    def handle_endtag(self, tag):
        if tag in self.HIDDEN:
            self.hidden -= 1
        elif tag == "blockquote":
            self.depth -= 1
            self.newline()
        elif tag in self.BLOCKS:
            self.newline()

    def handle_data(self, data):
        if not self.hidden:
            self.lines[-1][1] += data

    def text(self):
        return "\n".join("> " * depth + " ".join(line.split()) for depth, line in self.lines if line.strip())


def load_eml(data):
    """A saved .eml file -> (program source, attachments by file name).

    The plain-text part wins; an HTML-only email is flattened, keeping its quoted thread.
    """
    message = BytesParser(policy=policy.default).parsebytes(data)
    body = message.get_body(preferencelist=("plain", "html"))
    if body is None:
        fail(None, "this email has no text in it. Was it all screenshots?")
    text = body.get_content()
    if body.get_content_type() == "text/html":
        parser = HtmlText()
        parser.feed(text)
        parser.close()
        text = parser.text()
    headers = "".join(f"{name}: {message[name]}\n" for name in ("Subject", "Cc") if message[name])
    attachments = {}
    for part in message.iter_attachments():
        name = part.get_filename()
        if name:
            content = part.get_content()
            attachments[name] = content.decode("utf-8", "replace") if isinstance(content, bytes) else content
    return headers + "\n" + text, attachments


def sender_first_name(who):
    """`Dave Okonkwo <dave@…>`, `Okonkwo, Dave` or `dave.okonkwo@example.com` -> `Dave`."""
    name = re.sub(r"<[^>]*>", "", who).strip().strip('"').strip()
    if "," in name:
        name = name.split(",", 1)[1]
    if not name.strip() or "@" in name:
        address = re.search(r"[\w.+-]+(?=@)", who)
        name = re.split(r"[._+-]", address.group(0))[0] if address else ""
    words = name.split()
    return words[0] if words else "Someone"


def unfold_outlook(lines):
    """Outlook doesn't quote replies with `>`. It stacks earlier messages under From:/Sent: blocks,
    so each block becomes an `On …, <Name> wrote:` line and its message moves one level deeper."""
    out = []
    block_depth = None
    i = 0
    while i < len(lines):
        depth, text, n = lines[i]
        fields = []
        if OUTLOOK_FROM.match(text):
            j = i + 1
            while j < len(lines) and lines[j][0] == depth and OUTLOOK_FIELD.match(lines[j][1]):
                fields.append((lines[j][2], OUTLOOK_FIELD.match(lines[j][1])))
                j += 1
        if fields:
            values = {field.group("field").lower(): field.group("value") for _, field in fields}
            when = values.get("sent") or values.get("date") or "an earlier date"
            who = sender_first_name(OUTLOOK_FROM.match(text).group("who"))
            out.append((depth, f"On {when}, {who} wrote:", n))
            for line, field in fields:
                if field.group("field").lower() == "cc":
                    out.append((depth + 1, f"Cc: {field.group('value')}", line))
                else:
                    out.append((depth, "", line))
            block_depth = depth
            i = j
            continue
        if block_depth is not None and text and depth < block_depth:
            block_depth = None
        if OUTLOOK_SEPARATOR.match(text):
            out.append((depth, "", n))
        elif block_depth is not None:
            out.append((depth + 1, text, n))
        else:
            out.append((depth, text, n))
        i += 1
    return out


# ---------------------------------------------------------------- parsing

def parse_message(lines, base):
    """Parse one message whose own text sits at quote depth `base`.

    Returns (body_nodes, sign_off, people) where people maps first name -> body nodes.
    """
    i = 0
    cc, cc_line = [], None
    while i < len(lines) and not (lines[i][0] == base and GREETING.match(lines[i][1])):
        header = CC_HEADER.match(lines[i][1]) if lines[i][0] == base else None
        if header:
            cc += first_names(header.group(1))
            cc_line = lines[i][2]
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
    autocorrect = False
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
            print("warning: `Sent from my iPhone` present; optimizations disabled, autocorrect on.",
                  file=sys.stderr)
            autocorrect = True
        elif depth == base and POSTSCRIPT.match(text):
            continue
        elif depth == base and not signature_seen:
            signature_seen = True
        elif base == 0:
            fail(n, f"unreachable code after `{sign_off.title()},`.\n"
                    "       Nothing below a sign-off is read. This is true of email generally.")

    tree = build_tree(body, 0, 0, autocorrect)[0]
    for node in walk(tree):
        if node["kind"] == "reply_all":
            node["cc"] = cc
    if HR in cc:
        check_politeness(tree, cc_line)
    return tree, sign_off, people


def check_politeness(tree, line):
    """With HR on cc, between a fifth and a third of the statements have to be pleasantries."""
    kinds = [node["kind"] for node in walk(tree)]
    polite = sum(kind in PLEASANTRIES for kind in kinds)
    if polite * 5 < len(kinds):
        fail(line, "HR is cc'd and this email is too curt. Maybe open with `Hope you're well.`")
    if polite * 3 > len(kinds):
        fail(line, "HR is cc'd and this email is sycophantic. Tone it down")


def build_tree(items, i, depth, autocorrect=False):
    nodes = []
    while i < len(items):
        d, text, n = items[i]
        if d < depth:
            break
        if d > depth:
            fail(n, "quoted deeper than anything it could be replying to")
        node = parse_statement(text, n, autocorrect)
        i += 1
        if text.endswith(":"):
            node["body"], i = build_tree(items, i, depth + 1, autocorrect)
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
    (r"^somewhere between (?P<lo>.+?) and (?P<hi>.+)$", "random"),
    (r"^the size of the (?:(?P<q>[a-z]+) )?backlog$", "backlog_size"),
    (r"^(?P<p>[a-z]+)'s take(?: on (?P<a>.+))?$", "take"),
    (rf"^(?P<n>{NUM})$", "num"),
    (rf"^(?P<v>{V})$", "var"),
]

COND_PATTERNS = [
    (rf"^there's nothing left after splitting (?P<v>{V}) across (?P<x>.+)$", "divisible"),
    (r"^we still have an? (?:(?P<q>[a-z]+) )?backlog$", "backlog"),
    (r"^the (?:(?P<q>[a-z]+) )?backlog is empty$", "backlog_empty"),
    (rf"^we still have (?P<v>{V})$", "positive"),
    (rf"^(?P<v>{V}) is at zero$", "zero"),
    # greedy, so `we're under Dave's take on budget on sprint` splits at the last "on"
    (rf"^we're under (?P<x>.+) on (?P<v>{V})$", "lt"),
    (rf"^we're over (?P<x>.+) on (?P<v>{V})$", "gt"),
    (rf"^we're at (?P<x>.+) on (?P<v>{V})$", "eq"),
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
    (rf"^we have a hiring freeze on (?P<v>{V})\.$", "freeze"),
    (rf"^the (?:hiring )?freeze on (?P<v>{V}) is lifted\.$", "unfreeze"),
    (r"^adding (?P<x>.+?) to the (?:(?P<q>[a-z]+) )?backlog\.$", "enqueue"),
    (rf"^picking up the next (?:(?P<q>[a-z]+) )?backlog item as (?P<v>{V})\.$", "dequeue"),
    (rf"^picking up the most urgent (?:(?P<q>[a-z]+) )?backlog item as (?P<v>{V})\.$", "pop"),
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
    (r"^blocking (?P<t>\d+) (?P<u>minutes?|hours?) for this\.$", "timebox"),
    (r"^let me spell out (?P<x>.+)\.$", "spell"),
    (r"^let me spell (?P<x>.+) out\.$", "spell"),
    (r"^reading between the lines\.$", "read_letter"),
    (r'^circling back on "(?P<s>.*)"\.$', "print_lit"),
    (rf"^circling back on (?P<x>.+)\.$", "print"),
    (r"^\+leadership for visibility\.$", "flush"),
    (r"^(\+[a-z]+|looping in [a-z]+\.)$", "noop"),
    (r"^(?:hope (?:you're|you are) (?:doing )?well|hope this helps|hope you had a (?:great|good|nice|lovely) "
     r"weekend|thanks|thank you|appreciate it|much appreciated)[.!]$", "pleasantry"),
    (r"^(thoughts\?|please advise\.)$", "read"),
    (r"^sorry for the delay!$", "sleep"),
    (r"^thanks in advance\.$", "tia"),
]


def pattern_words(patterns):
    """The fixed words of every idiom, which is what autocorrect is allowed to correct towards."""
    words = set()
    for pattern, _ in patterns:
        pattern = re.sub(r"\(\?P<\w+>[^()]*\)", " ", pattern)  # user-supplied text
        pattern = re.sub(r"\[[^\]]*\]", " ", pattern)           # character classes
        words.update(word for word in re.findall(r"[a-z][a-z'-]*", pattern) if len(word) >= 3)
    return words


VOCABULARY = sorted(pattern_words(EXPR_PATTERNS + COND_PATTERNS + STATEMENT_PATTERNS))


def autocorrections(text):
    """Candidate fixes for a mistyped line: each misspelled word on its own first, then all together."""
    words = text.split(" ")
    fixes = {}
    for i, word in enumerate(words):
        typed = word.strip(",.:;!?\"")
        if len(typed) < 3 or typed.lower() in VOCABULARY:
            continue
        match = difflib.get_close_matches(typed.lower(), VOCABULARY, n=1, cutoff=0.8)
        if match:
            fixes[i] = (typed, match[0])

    def apply(indices):
        fixed = list(words)
        for i in indices:
            typed, right = fixes[i]
            fixed[i] = words[i].replace(typed, right, 1)
        return " ".join(fixed), [fixes[i] for i in indices]

    for i in fixes:
        yield apply([i])
    if len(fixes) > 1:
        yield apply(list(fixes))


def parse_expr(text, n):
    for pat, kind in EXPR_PATTERNS:
        m = re.match(pat, text, re.I)
        if m:
            g = m.groupdict()
            if kind == "mod":
                return ("mod", var_key(g["b"]), parse_expr(g["a"], n))
            if kind == "random":
                return ("random", parse_expr(g["lo"], n), parse_expr(g["hi"], n))
            if kind == "backlog_size":
                return ("backlog_size", (g["q"] or "").lower())
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
            if "q" in g:
                return (kind, (g["q"] or "").lower(), None)
            x = parse_expr(g["x"], n) if "x" in g else None
            return (kind, var_key(g["v"]), x)
    fail(n, f"not sure what `{text}` means as a condition. Can we align offline?")


def parse_statement(text, n, autocorrect=False):
    """With `Sent from my iPhone`, a line that doesn't parse gets its typos fixed and another go."""
    try:
        return match_statement(text, n)
    except RegardsError as original:
        if not autocorrect:
            raise
        for fixed, changes in autocorrections(text):
            try:
                node = match_statement(fixed, n)
            except RegardsError:
                continue
            for typed, right in changes:
                print(f"warning: autocorrected `{typed}` to `{right}` (line {n})", file=sys.stderr)
            return node
        raise original


def match_statement(text, n):
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
        if "q" in g:
            node["queue"] = (g["q"] or "").lower()
        if g.get("t"):
            node["seconds"] = int(g["t"]) * (3600 if g["u"].lower().startswith("hour") else 60)
        if "s" in g:
            node["text"] = m.group("s")
        return node
    fail(n, f"`{text}` isn't something I can action")


# ---------------------------------------------------------------- execution

class Interpreter:
    def __init__(self, people, stdin=sys.stdin, stdout=sys.stdout, folder=".", rng=None, attachments=None):
        self.globals = {}
        self.scopes = [self.globals]
        self.people = people
        self.stdin = stdin
        self.stdout = stdout
        self.folder = folder
        self.attachments = attachments or {}
        self.rng = rng or random.Random()
        self.frozen = set()
        self.backlogs = {}
        self.meeting = {"seconds left": None}
        self.last_var = None
        self.subject = None
        self.last_ok = True
        self.depth = 0

    def fork(self):
        """Another reader of the same thread: shared variables and people, its own call stack."""
        child = Interpreter(self.people, self.stdin, self.stdout, self.folder, self.rng, self.attachments)
        child.globals = self.globals
        child.scopes = [self.globals]
        child.frozen = self.frozen
        child.backlogs = self.backlogs
        child.meeting = self.meeting
        child.depth = self.depth
        return child

    def resolve(self, name, line):
        """`it` and `that` mean whichever variable was mentioned last before this statement."""
        if name not in PRONOUNS:
            return name
        if self.subject is None:
            fail(line, f"not sure what `{name}` refers to. Can you be more specific?")
        return self.subject

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope
        return None

    def get(self, name, line):
        name = self.resolve(name, line)
        scope = self.lookup(name)
        if scope is None:
            fail(line, f"nobody told me about `{name}`. Can you send it over?")
        self.last_var = name
        return scope[name]

    def declare(self, name, value, line):
        name = self.resolve(name, line)
        if name not in self.frozen:
            self.scopes[-1][name] = value
        self.last_var = name

    def assign(self, name, value, line):
        """Update the nearest variable with this name, or create it in the innermost scope."""
        name = self.resolve(name, line)
        if name not in self.frozen:
            scope = self.lookup(name)
            if scope is None:
                scope = self.scopes[-1]
            scope[name] = value
        self.last_var = name

    def say(self, text):
        # one write per line, so people replying all at once can't split each other's lines
        self.stdout.write(f"{text}\n")

    def merge(self, text):
        """Fill [placeholders] from variables. Unknown ones go out as typed, like any botched mail merge."""
        def fill(placeholder):
            name = var_key(placeholder.group(1)) if placeholder.group(1).split() else None
            if name in PRONOUNS:
                name = self.subject
            scope = self.lookup(name) if name else None
            return str(scope[name]) if scope is not None else placeholder.group(0)
        return PLACEHOLDER.sub(fill, text)

    def tick(self, line):
        """Each statement takes a second of the meeting, once someone has blocked time for it."""
        left = self.meeting["seconds left"]
        if left is None:
            return
        if left <= 0:
            fail(line, "we're over time. Let's continue next week")
        self.meeting["seconds left"] = left - 1

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
        if kind == "random":
            low, high = self.eval(expr[1], line), self.eval(expr[2], line)
            if low > high:
                fail(line, f"somewhere between {low} and {high} isn't a range. "
                           f"Did you mean between {high} and {low}?")
            return self.rng.randint(low, high)
        if kind == "backlog_size":
            return len(self.backlogs.get(expr[1], ()))
        divisor = self.eval(expr[2], line)
        if divisor == 0:
            fail(line, "splitting across zero. That's not a realistic plan")
        return self.get(expr[1], line) % divisor

    def test(self, cond, line):
        kind, var, x = cond
        if kind == "backlog":
            return bool(self.backlogs.get(var))
        if kind == "backlog_empty":
            return not self.backlogs.get(var)
        v = self.get(var, line)
        if kind == "positive":
            return v > 0
        if kind == "zero":
            return v == 0
        if kind == "lt":
            return v < self.eval(x, line)
        if kind == "gt":
            return v > self.eval(x, line)
        if kind == "eq":
            return v == self.eval(x, line)
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
        """Everyone quoted in the attached email becomes callable. Its own body never runs.

        When the program is a saved .eml file, a real attachment of that name wins over the disk.
        """
        if name in self.attachments:
            source = self.attachments[name]
        else:
            try:
                with open(os.path.join(self.folder, name), encoding="utf-8") as f:
                    source = f.read()
            except (OSError, UnicodeDecodeError):
                fail(line, f"the attachment `{name}` didn't come through. Can you resend?")
        try:
            _, _, people = parse_message(preprocess(unfold_outlook(lex(source))), 0)
        except RegardsError as e:
            fail(line, f"the attachment `{name}` is garbled: {str(e).removeprefix('error: ')}")
        self.people.update(people)

    def reply_all(self, node, line):
        """Everyone on cc replies at once, except HR. They share variables and nobody coordinates."""
        if not node["cc"]:
            fail(line, "nobody is cc'd. Reply-all to whom?")
        recipients = [person for person in node["cc"] if person != HR]
        if not recipients:
            fail(line, "only HR is cc'd, and HR never replies")
        for person in recipients:
            if person not in self.people:
                fail(line, f"{person.title()} isn't on this thread. Happy to resend")
        arg = ("num", self.eval(node["expr"], line)) if "expr" in node else None
        errors = []

        def reply(fork, person):
            try:
                fork.call(person, arg, line)
            except BaseException as e:
                errors.append(e)

        replies = [threading.Thread(target=reply, args=(self.fork(), person)) for person in recipients]
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
            self.subject = self.last_var
            self.tick(node["line"])
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
            self.declare(var, self.eval(node["expr"], line), line)
        elif k == "set":
            self.assign(var, self.eval(node["expr"], line), line)
        elif k == "zero":
            self.assign(var, 0, line)
        elif k in ("inc", "dec", "double", "halve"):
            v = self.get(var, line)
            self.assign(var, {"inc": v + 1, "dec": v - 1, "double": v * 2, "halve": v // 2}[k], line)
        elif k in ("add", "sub", "mul", "div"):
            a = self.eval(node["expr"], line)
            b = self.get(var, line)
            if k == "div" and a == 0:
                fail(line, "splitting across zero. That's not a realistic plan")
            self.assign(var, {"add": b + a, "sub": b - a, "mul": b * a, "div": b // a if a else 0}[k], line)
        elif k == "freeze":
            self.frozen.add(self.resolve(var, line))
        elif k == "unfreeze":
            self.frozen.discard(self.resolve(var, line))
        elif k == "enqueue":
            self.backlogs.setdefault(node["queue"], deque()).append(self.eval(node["expr"], line))
        elif k in ("dequeue", "pop"):
            backlog = self.backlogs.get(node["queue"])
            if not backlog:
                name = f"{node['queue']} backlog" if node["queue"] else "backlog"
                fail(line, f"the {name} is empty. Nothing to pick up, so enjoy the quiet sprint")
            self.assign(var, backlog.popleft() if k == "dequeue" else backlog.pop(), line)
        elif k == "while":
            while True:
                self.subject = self.last_var
                self.tick(line)
                if not self.test(node["cond"], line):
                    break
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
        elif k == "timebox":
            self.meeting["seconds left"] = node["seconds"]
        elif k == "spell":
            code = self.eval(node["expr"], line)
            if not 0 <= code <= 0x10FFFF:
                fail(line, f"{code} isn't a letter, so there's nothing to spell out")
            self.stdout.write(chr(code))
        elif k == "read_letter":
            if self.last_var is None:
                fail(line, "reading between the lines of nothing in particular")
            letter = self.stdin.read(1)
            self.assign(self.last_var, ord(letter) if letter else -1, line)
        elif k == "print_lit":
            self.say(self.merge(node["text"]))
        elif k == "print":
            self.say(self.eval(node["expr"], line))
        elif k == "flush":
            self.stdout.flush()
        elif k == "read":
            if self.last_var is None:
                fail(line, "asking for thoughts on nothing in particular")
            raw = self.stdin.readline()
            try:
                self.assign(self.last_var, int(raw.strip()), line)
                self.last_ok = True
            except ValueError:
                self.last_ok = False
        elif k == "sleep":
            time.sleep(1)
        elif k == "tia":
            if not self.last_ok:
                print(f"warning: line {line}: thanks in advance, but it didn't happen.", file=sys.stderr)


MAX_CALL_DEPTH = 1000
MAX_JARGON_EXPANSIONS = 20
# Each nested call costs several Python frames, and more inside loops and ifs.
PYTHON_RECURSION_LIMIT = 50_000
# Replies run on their own threads, which get a small stack by default.
THREAD_STACK_SIZE = 256 * 1024 * 1024


def run(source, stdin=sys.stdin, stdout=sys.stdout, path=None, rng=None, attachments=None):
    """Run a program. Returns the process exit code.

    `path` is where the program lives; attachments are looked for next to it.
    """
    folder = os.path.dirname(os.path.abspath(path)) if path else "."
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, PYTHON_RECURSION_LIMIT))
    try:
        body, sign_off, people = parse_message(preprocess(unfold_outlook(lex(source))), 0)
        Interpreter(people, stdin, stdout, folder, rng, attachments).run_message(body)
    except NetNet as stray:
        fail(stray.line, "`Net-net` in the original email. There's nobody to report back to")
    except RecursionError:
        raise RegardsError("error: this thread has too many replies. Let's set up a meeting") from None
    finally:
        sys.setrecursionlimit(old_limit)
    return 1 if sign_off in NONZERO_SIGN_OFFS else 0


def main(argv):
    if argv[1:] == ["--version"]:
        print(f"Regards, {__version__}")
        return 0
    if len(argv) != 2:
        print("usage: regards.py <program.rgrd | saved-email.eml | --version>", file=sys.stderr)
        return 2
    path = argv[1]
    saved_email = path.lower().endswith(".eml")
    try:
        if saved_email:
            with open(path, "rb") as f:
                data = f.read()
        else:
            with open(path, encoding="utf-8") as f:
                data = f.read()
    except OSError as e:
        print(f"error: couldn't open `{path}` ({e.strerror}). Can you reattach?", file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print(f"error: `{path}` isn't UTF-8 text. The attachment seems corrupted.", file=sys.stderr)
        return 2
    try:
        source, attachments = load_eml(data) if saved_email else (data, {})
        return run(source, path=path, attachments=attachments)
    except RegardsError as e:
        print(e, file=sys.stderr)
        return 2
    except Exception:
        traceback.print_exc()
        print("internal error: this is a bug in the interpreter, not in your email.", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
