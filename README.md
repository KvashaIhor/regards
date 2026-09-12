# `Regards,`

An esoteric programming language whose source code is a passive-aggressive corporate email thread.

```
Subject: Q3 headcount — quick sync?

Hi Priya,

Just to level-set, we have 5 open reqs.

Per my last email, while we still have open reqs:
> Circling back on open reqs.
> Quick flag: one req is now closed.

+Leadership for visibility.

Best,
Ihor
```

Output:

```
5
4
3
2
1
```

Run it with `python3 regards.py examples/countdown.rgrd`.

---

## 1. Design thesis

Most themed languages fail because the premise donates only **vocabulary**. Renaming
`print` to `SHOUT` or `call` to `cast` gives you a skin, not a language.

A premise earns its place only if the genre already supplies, in its own natural idiom:

1. named persistent things → variables
2. conditional phrasing → branches
3. a way to refer back to an earlier point → jumps and calls
4. something that looks like output → I/O

Chef passes because a mixing bowl is genuinely a stack. Shakespeare passes because two
characters on stage are genuinely two registers.

`Regards,` passes on all four, and it has one structural gift the others don't:

> **Quote depth is block depth.** `>` and `>>` are indentation that no reader would
> question, because that is already what they mean in an email client.

Every block-structured esolang has to invent a delimiter and pay for it in awkwardness.
`Regards,` gets one free, and gets it from the most-despised artifact in office life.

The second gift is the terminator. A message ends when it is signed off, so the language
is named after its halt instruction.

---

## 2. Anatomy of a program

A `.rgrd` file is **one email message**, optionally quoting a thread beneath it.

```
Subject: <program name>              ← program name, ignored by the interpreter

Hi <name>,                           ← entry point

<body>                               ← statements; `>` depth is block depth

Best,                                ← HALT
Ihor                                 ← ignored

Sent from my iPhone                  ← pragma (optional)

On Tue, 8 Sep 2026, Priya Raman <priya@…> wrote:
> <the quoted thread below the signature is the standard library>
> <each quoted message defines a person you can call>
```

Three regions, in order:

| Region | Role |
|---|---|
| Subject line | Program name. Decorative. |
| Body, from `Hi …,` to the sign-off | The program. |
| Quoted thread below the signature | **The past.** Previously-defined messages, available to call. |

That last one is the part I like most: the history you keep dragging along below your
signature is the library you are importing, and nobody ever reads it.

Below the sign-off, only three things are allowed: the signature name, the
`Sent from my iPhone` pragma, and `On …, <Name> wrote:` blocks. Anything else is
unreachable code and an error.

### Quote depth inside the thread

A quoted message's own text sits at one level of `>`. Its blocks are counted from there, so
a loop body inside Dave's message is at `> >`. Messages quoted inside Dave's message are
one level deeper again, and everyone in the thread, however deep, is callable.

`>>` and `> >` are the same depth. Email clients rewrite one into the other, so both are
accepted.

---

## 3. Statement reference

The idiom table *is* the language. Everything below is matched case-insensitively with
normalized whitespace.

Email clients rewrite text as you type, so the lexer undoes it: curly quotes become
straight quotes, and `—`, `–` and `--` are all the same dash. A program pasted out of
Outlook still runs.

### Variable names

People never refer to the same thing the same way twice, so a variable is named by its
**last word, lowercased, with a trailing `s` dropped**. `open reqs`, `req` and `Reqs` are
one variable. This is what lets you declare `5 open reqs` and then close `one req`.

The corollary is that `open reqs` and `closed reqs` are also one variable. Pick distinct
nouns.

Numbers are integers with no upper limit. Halving and splitting round down, toward
negative infinity.

Wherever a table below says `<n>` or `<a>`, you can write either a number or a variable.

### Declaration and assignment

| Idiom | Semantics |
|---|---|
| `Just to level-set, we have <n> <var>.` | declare `var`, assign `n` |
| `Just to level-set, <var> is <n>.` | declare `var`, assign `n` |
| `Looping in <Name>.` / `+<Name>` | no effect; everyone in the quoted thread is already callable |
| `Per the attached, <var> is now <expr>.` | reassign |
| `<var> is off the table.` | `var = 0` |

### Arithmetic

| Idiom | Semantics |
|---|---|
| `Good news — we've added another <var>.` | `var += 1` |
| `Quick flag: one <var> is now closed.` | `var -= 1` |
| `Doubling down on <var>.` | `var *= 2` |
| `Let's cut <var> in half.` | `var //= 2` |
| `Rolling <a> into <b>.` | `b += a` |
| `Backing <a> out of <b>.` | `b -= a` |
| `Scaling <b> by <a>.` | `b *= a` |
| `Splitting <b> across <a>.` | `b //= a` |
| `what's left after splitting <b> across <a>` | `b % a` (expression) |

`what's left after splitting X across Y` being exactly modulo, in unmodified corporate
English, is the single best argument for this language existing.

### Conditions

| Idiom | Semantics |
|---|---|
| `we still have <var>` | `var > 0` |
| `<var> is at zero` | `var == 0` |
| `we're under <n> on <var>` | `var < n` |
| `we're over <n> on <var>` | `var > n` |
| `there's nothing left after splitting <var> across <n>` | `var % n == 0` |

### Control flow

| Idiom | Semantics |
|---|---|
| `If <cond>:` | `if` — body is the next quote level |
| `That said, if <cond>:` | `else if` |
| `That said:` | `else` |
| `Per my last email, while <cond>:` | `while` |
| `Bumping this.` | re-send the current message: restart the program, or the person being called, from the top |
| `As discussed, <Name>.` | call person `<Name>` |

`Bumping this.` does not remember anything about the first attempt. Variables keep their
values, but every statement runs again, including the ones that set them up. Put your
setup in the caller and your bump in the person.

### I/O

| Idiom | Semantics |
|---|---|
| `Circling back on <var>.` | print `var` (or any expression), then a newline |
| `Circling back on "<literal>".` | print literal |
| `+Leadership for visibility.` | flush stdout |
| `Thoughts?` / `Please advise.` | read a value into the last-mentioned variable |

### Meta and pragmas

| Idiom | Semantics |
|---|---|
| `Best,` / `Thanks,` / `Cheers,` / `Warm regards,` / `Kind regards,` / `Best regards,` / `Many thanks,` / `Sincerely,` | **HALT**, exit 0 |
| `Regards,` | **HALT**, exit 1 |
| `Sent from my iPhone` | disable all optimizations |
| `Sorry for the delay!` | sleep 1s |
| `Thanks in advance.` | warn if the previous `Thoughts?` didn't get a number back |

A bare `Regards,` is not a happy sign-off, and anyone who has received one knows it. It
halts with exit code 1. `Warm regards,` is fine.

`Thanks in advance.` is coercive but not binding, so it is a warning, not an assert, and
there is no way to turn the warning off.

---

## 4. People are functions

A person becomes callable by being defined in the quoted thread below the signature. Their
name is the first name in the `On …, <Name> wrote:` line. Calling is `As discussed, Dave.`

There is one shared set of variables. Dave reads and changes the same variables the caller
does, which is how he gets information in and out. Nobody on a thread has private state.

```
As discussed, Dave.

Best,
Ihor

On Mon, 7 Sep 2026, Dave Okonkwo <dave@…> wrote:
> Hi Ihor,
>
> Circling back on "the deck is attached".
>
> Best,
> Dave
```

Dave halts on his own sign-off and control returns to the caller. A person who never
signs off is a parse error, because the thread is still open.

A person can call themselves. After 1000 nested calls the interpreter gives up and
suggests a meeting.

---

## 5. Examples

### Hello World

```
Subject: quick one

Hi team,

Circling back on "Hello, World".

Best,
Ihor
```

### FizzBuzz

```
Subject: Sprint cadence — recurring invite

Hi all,

Just to level-set, we have 1 sprint.

Per my last email, while we're under 101 on sprint:
> If there's nothing left after splitting sprint across 15:
> > Circling back on "retro + all-hands".
> That said, if there's nothing left after splitting sprint across 3:
> > Circling back on "retro".
> That said, if there's nothing left after splitting sprint across 5:
> > Circling back on "all-hands".
> That said:
> > Circling back on sprint.
> Good news — we've added another sprint.

+Leadership for visibility.

Best,
Ihor

Sent from my iPhone
```

### Factorial of 5

```
Subject: Re: Re: Fwd: modelling assumptions (was: quick q)

Hi Priya,

Just to level-set, runway is 1.
Just to level-set, we have 5 quarters.

Per my last email, while we still have quarters:
> Scaling runway by quarters.
> Quick flag: one quarter is now closed.

Circling back on runway.
+Leadership for visibility.

Best,
Ihor
```

---

## 6. Errors

Diagnostics are written in register. All errors stop the program with exit code 2.

```
warning: `Sent from my iPhone` present; optimizations disabled.

error: Dave isn't on this thread. Happy to resend (line 3)

error: nobody told me about `budget`. Can you send it over? (line 3)

error: `Let's synergize.` isn't something I can action (line 3)

error: unreachable code after `Best,`. (line 8)
       Nothing below a sign-off is read. This is true of email generally.

error: splitting across zero. That's not a realistic plan (line 5)

error: this thread has too many replies. Let's set up a meeting (line 4)

error: no sign-off. The thread is still open.
```

The last one has no line number, because the problem is everything after the last line.

---

## 7. Computational class

`Regards,` is Turing complete.

Integers have no upper limit, and the language has a `while` loop, add one
(`Good news — we've added another`), subtract one (`Quick flag: one … is now closed`) and a
zero test (`is at zero`). That is enough to run a two-counter Minsky machine, which is a
known Turing-complete model: two variables hold the counters, a third holds the machine's
current state, and one `Per my last email, while` loop dispatches on that state with
`If` / `That said, if`.

---

## 8. Design decisions

### Settled

- **`Per my last email` is a `while` loop.** The faithful unconditional backward jump
  already exists as `Bumping this.`, and two idioms should not do one job.
- **`Bumping this.` re-sends the current message.** It restarts the program, or the person
  being called, from the top. It does not target labels, because email has none.
- **`Thanks in advance.` is a warning that cannot be suppressed.**
- **Sign-offs carry exit codes.** Bare `Regards,` exits 1. Everything warmer exits 0.

### Still open

- **What `Sent from my iPhone` should actually do.** A tree-walking interpreter has no
  optimizations to disable, so for now it only prints its warning. The better use is typo
  tolerance: fuzzy-match idioms, because that is what the signature excuses.

---

## 9. Proposed extensions

**None of this is part of the language.** These statements are not implemented, and the
interpreter rejects them as unknown statements.

| Idiom | Proposed semantics |
|---|---|
| `Net-net, <expr>.` | return a value from a person |
| `As discussed, <Name>, re: <var>.` | call a person with an argument |
| `Happy to take this offline.` | open a private (lexical) scope. Quote depth already gives blocks, so this needs a way to end that doesn't duplicate it. |
| `Resending with the attachment.` | re-import the quoted thread |
| `I am currently OOO, returning <date>.` | exception handler for the enclosing block |
| a reply-all | `fork()`. Forks would share memory with last-write-wins and no synchronization, which is both the easiest implementation and the accurate one. Needs a syntax first, since a single file has no recipient list. |

---

## 10. Implementation

Reference interpreter in Python 3, tree-walking, no dependencies.

```
python3 regards.py examples/fizzbuzz.rgrd      # run a program
python3 -m unittest discover -s tests          # run the tests
```

Exit codes: 0 for a warm sign-off, 1 for a bare `Regards,`, 2 for an error in the program,
3 for a bug in the interpreter itself.

```
regards/
  README.md          this file
  regards.py         lexer, parser, interpreter
  examples/
    hello.rgrd
    countdown.rgrd
    fizzbuzz.rgrd
    factorial.rgrd
    dave.rgrd        calling a person from the quoted thread
  tests/
    test_regards.py
```

Lexing is line-oriented: strip leading `>` to get the quote depth, then match the
remaining text against the idiom table. Parsing is a straight indentation-to-tree
transform over quote depth, identical to Python's INDENT/DEDENT handling. The interpreter
is a walk over the resulting tree with a single environment and a call stack.

The parser is the interesting part, and it is small. The idiom table is where the work is,
and the idiom table is also the joke, so the work and the joke are the same work.

---

## 11. License

`Regards,` — the specification, the interpreter, the examples and the tests — is dedicated to
the public domain under [CC0 1.0](LICENSE). Copy it, fork it, paste it onto a wiki, reply-all.
