# `Regards,`

[![tests](https://github.com/KvashaIhor/regards/actions/workflows/tests.yml/badge.svg)](https://github.com/KvashaIhor/regards/actions/workflows/tests.yml)

An esoteric programming language whose source code is a passive-aggressive corporate email thread.

**Try it in your browser: [Does your email compile?](https://regards-pearl.vercel.app)**

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

Run it with `python3 regards.py examples/countdown.rgrd`. Or install it with
`pip install regards`, which gives you a `regards` command for any `.rgrd` program or saved
`.eml` email. Either way it needs Python 3.9 or newer and nothing else.

This is `Regards,` 1.0. Programs written for 1.0 will keep running on every 1.x version, and
anything that would break them waits for 2.0. The
[changelog](https://github.com/KvashaIhor/regards/blob/main/CHANGELOG.md) lists what's in each
version.

---

## 1. Why email

Corporate email turns out to be a programming language that nobody bothered to write down.
Everything a language needs is already in there:

1. things people keep bringing up (`open reqs`) → variables
2. `If we still have budget:` → branches
3. `Per my last email` and `As discussed, Dave.` → loops and calls
4. `Circling back on …` → output

`Regards,` follows a proud esolang tradition of finding a language somewhere nobody was
looking. Chef found stacks in mixing bowls, and Shakespeare found registers in two
characters sharing a stage. This one found one in your inbox.

Email even brings its own indentation, which is generous of the most-despised artifact in
office life:

> **Quote depth is block depth.** `>` and `>>` already mean "this belongs to that" in every
> email client, so there is no new delimiter to learn.

It brings its own ending, too. A message is over when it is signed off, so the language is
named after its halt instruction.

---

## 2. Anatomy of a program

A `.rgrd` file is **one email message**, optionally quoting a thread beneath it.

```
Subject: <program name>              ← program name, ignored by the interpreter
Cc: <Name>, <Name>                   ← who `Replying all.` reaches (optional)

Hi <name>,                           ← entry point (Hello, Hey and Dear work too)

<body>                               ← statements; `>` depth is block depth

Best,                                ← HALT
Ihor                                 ← ignored
P.S. …                               ← also ignored (optional)

Sent from my iPhone                  ← turns on autocorrect (optional)

On Tue, 8 Sep 2026, Priya Raman <priya@…> wrote:
> <the quoted thread below the signature is the standard library>
> <each quoted message defines a person you can call>
```

Three regions, in order:

| Region | Role |
|---|---|
| Header lines | `Subject:` is the program name, and decorative. `Cc:` lists who `Replying all.` reaches. |
| Body, from `Hi …,` to the sign-off | The program. |
| Quoted thread below the signature | **The past.** Previously-defined messages, available to call. |

That last one is the part I like most: the history you keep dragging along below your
signature is the library you are importing, and nobody ever reads it.

Below the sign-off, only four things are allowed: the signature name, `P.S.` lines, the
`Sent from my iPhone` pragma, and `On …, <Name> wrote:` blocks. Anything else is
unreachable code and an error. Nobody reads a P.S., so the interpreter doesn't either.

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

Words of three letters or fewer, and words ending in `ss`, keep their `s`, so `gas` and
`business` stay as they are.

`it` and `that` stand for whichever variable was mentioned last before the current
statement, so `Doubling down on it.` right after `Just to level-set, budget is 5.` doubles
the budget.

Numbers are integers with no upper limit. Halving and splitting round down, toward
negative infinity.

Wherever a table below says `<n>`, `<a>` or `<expr>`, you can write a number, a variable,
`what's left after splitting …`, or someone's take (section 4). The one exception is
`Just to level-set, we have <n> <var>.`, where `<n>` has to be a plain number.

The backlog has its own statements in section 8, and you can add phrases of your own with
jargon (section 9).

### Declaration and assignment

| Idiom | Semantics |
|---|---|
| `Just to level-set, we have <n> <var>.` | declare `var`, assign `n` |
| `Just to level-set, <var> is <n>.` | declare `var`, assign `n` |
| `Looping in <Name>.` / `+<Name>` | no effect; everyone in the quoted thread is already callable |
| `Per the attached, <var> is now <expr>.` | reassign |
| `<var> is off the table.` | `var = 0` |
| `Happy to take this offline.` | variables declared from here to the end of the block are private |
| `We have a hiring freeze on <var>.` | writes to `var` silently do nothing from here on |
| `The freeze on <var> is lifted.` | writes to `var` work again |

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
| `somewhere between <a> and <b>` | a random integer from `a` to `b`, both included (expression) |

`what's left after splitting X across Y` being exactly modulo, in unmodified corporate
English, is the single best argument for this language existing.

`somewhere between 3 and 8` is also how estimates work: you get a whole number in that range,
and nobody can tell you in advance which one.

### Conditions

| Idiom | Semantics |
|---|---|
| `we still have <var>` | `var > 0` |
| `<var> is at zero` | `var == 0` |
| `we're under <n> on <var>` | `var < n` |
| `we're over <n> on <var>` | `var > n` |
| `we're at <n> on <var>` | `var == n` |
| `there's nothing left after splitting <var> across <n>` | `var % n == 0` |

### Control flow

| Idiom | Semantics |
|---|---|
| `If <cond>:` | `if`; the body is the next quote level |
| `That said, if <cond>:` | `else if` |
| `That said:` | `else` |
| `Per my last email, while <cond>:` | `while` |
| `Bumping this.` | re-send the current message: restart the program, or the person being called, from the top |
| `As discussed, <Name>.` | call person `<Name>` |
| `As discussed, <Name>, re: <a>.` | call `<Name>` with `<a>` as the ask |
| `<Name>'s take` | call `<Name>` and use their net-net (expression) |
| `<Name>'s take on <a>` | the same, with `<a>` as the ask (expression) |
| `Net-net, <a>.` | end the current person's message and report `<a>` back |
| `I am currently OOO, returning <date>:` | error handler for the rest of the block |
| `Resending with the attachment: <file>.` | import the people quoted in another program |
| `Replying all.` / `Replying all, re: <a>.` | call everyone on the `Cc:` line at once |
| `Going forward, "<phrase>" means "<statement>".` | define jargon (section 9) |

`Bumping this.` does not remember anything about the first attempt. Variables keep their
values, but every statement runs again, including the ones that set them up. Put your
setup in the caller and your bump in the person.

### I/O

| Idiom | Semantics |
|---|---|
| `Circling back on <var>.` | print `var` (or any expression), then a newline |
| `Circling back on "<literal>".` | print literal, filling in `[placeholders]` |
| `+Leadership for visibility.` | flush stdout |
| `Thoughts?` / `Please advise.` | read a value into the last-mentioned variable |
| `Let me spell <a> out.` / `Let me spell out <a>.` | print the character with code `a`, no newline |
| `Reading between the lines.` | read one character's code into the last-mentioned variable, or -1 at the end of input |

Literals work like a mail merge. Each `[placeholder]` is filled from the variable of that
name, and one that doesn't match any variable goes out exactly as typed:

```
Circling back on "Hi [First Name], we have [reqs] open reqs".
```

With `reqs` at 3 and no variable called `name`, that prints
`Hi [First Name], we have 3 open reqs`.

`Let me spell it out.` is the passive-aggressive way to print one character. Together with
`Reading between the lines.` it is enough for a
[cat program](https://esolangs.org/wiki/Cat_program) and a Brainfuck interpreter, both in
section 12.

### Meta and pragmas

| Idiom | Semantics |
|---|---|
| `Best,` / `Thanks,` / `Cheers,` / `Warm regards,` / `Kind regards,` / `Best regards,` / `Many thanks,` / `Sincerely,` | **HALT**, exit 0 |
| `Regards,` | **HALT**, exit 1 |
| `Sent from my iPhone` | disable all optimizations (there aren't any) and turn on autocorrect |
| `Sorry for the delay!` | sleep 1s |
| `Thanks in advance.` | warn if the previous `Thoughts?` didn't get a number back |
| `Hope you're well.`, `Thanks!` and other pleasantries | nothing, unless HR is cc'd (section 10) |
| `Blocking <n> minutes for this.` (or hours) | start a timebox |
| `FYI …` | a comment; the whole line is ignored |

A bare `Regards,` is not a happy sign-off, and anyone who has received one knows it. It
halts with exit code 1. `Warm regards,` is fine. Only the original email's sign-off sets the
exit code. When Dave signs off with a bare `Regards,`, the call returns normally and nobody
mentions it.

`Thanks in advance.` is coercive but not binding, so it is a warning, not an assert, and
there is no way to turn the warning off.

With `Sent from my iPhone` in the message, a line that doesn't parse gets a second chance.
Misspelled words are matched against the language's own vocabulary, one word at a time
before several at once, so a name you made up only changes if nothing else works. Every fix
prints a warning, such as ``autocorrected `Circlign` to `circling` ``.

`Blocking 30 minutes for this.` starts a timebox. Every statement after it costs one second
of the meeting, and so does every loop check, which means 30 minutes buys 1,800 statements.
Once time is up the program stops with `we're over time`. An out-of-office can't save it,
because the auto-reply is over time too. Everyone on a reply-all shares the same clock.

---

## 4. People are functions

A person becomes callable by being defined in the quoted thread below the signature. Their
name is the first name in the `On …, <Name> wrote:` line. Calling is `As discussed, Dave.`

There is one shared set of variables. Dave reads and changes the same variables the caller
does, unless someone takes the conversation offline. Values can also travel on purpose: the
ask goes in and a net-net comes back out (both below).

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

When Dave signs off, control returns to the caller. A person who never signs off is a parse
error, because the thread is still open.

A person can call themselves. After 1000 nested calls the interpreter gives up and
suggests a meeting.

### Net-net

`Net-net, <a>.` ends the person's message on the spot and reports `<a>` back. To use that
value, ask for their take:

```
Just to level-set, budget is Priya's take.
Circling back on Dave's take on budget.
```

A take calls the person and evaluates to their net-net. Signing off without one is an error
when someone asked for a take. `As discussed, Dave.` still works on a person who gives a
net-net; the net-net ends Dave's message early and the value goes nowhere. A net-net in the
original email is an error, because there is nobody to report back to.

### The ask

`As discussed, Dave, re: <a>.` and `Dave's take on <a>` both pass Dave one value, which Dave
reads as `the ask`. It is a copy, so Dave can double it without touching anything of yours.

Passing an argument takes the call offline. Dave gets a private scope that holds `the ask`,
and anything Dave declares with `Just to level-set` stays in it. A plain
`As discussed, Dave.` shares everything, as before.

Private variables are what make recursion possible. This is `examples/forecast.rgrd`, which
prints 3628800:

```
Subject: Re: 10-year forecast — can Dave run the numbers?

Hi Dave,

Circling back on Dave's take on 10.

Best,
Ihor

On Mon, 7 Sep 2026, Dave Okonkwo <dave@example.com> wrote:
> Hi Ihor,
>
> If the ask is at zero:
> > Net-net, 1.
>
> Just to level-set, prior year is the ask.
> Quick flag: one year is now closed.
> Just to level-set, forecast is Dave's take on prior year.
> Scaling forecast by the ask.
> Net-net, forecast.
>
> Best,
> Dave
```

### Taking it offline

`Happy to take this offline.` makes the rest of its block private. Anything declared after
it with `Just to level-set` disappears when the block ends, and so does anything created by
assigning to a name nobody had declared. Variables that already existed are still shared:
`Good news — we've added another req.` inside the block changes the same `req` as outside.

People never see the caller's offline variables, only the shared ones.

---

## 5. Out of office

```
Just to level-set, we have 12 open reqs.
Just to level-set, we have 0 teams.

I am currently OOO, returning Monday:
> Circling back on "no teams yet, so no split. Back Monday".

Splitting reqs across teams.
Circling back on reqs.
```

`I am currently OOO, returning <date>:` (or `I'm currently OOO`) covers the rest of the
block it sits in. When a statement after it fails at runtime, even deep inside a person it
called, the reply quoted underneath runs in its place and the program continues after that
block. The date is for whoever reads the program. The interpreter ignores it.

Nothing before the auto-reply is covered, and an error inside the auto-reply itself goes
straight through. Parse errors in the program itself are never caught, since the program
hasn't started yet when they happen. A broken attachment is different (see below). `Net-net`
and `Bumping this.` pass through untouched, because they are not errors.

---

## 6. Attachments

`Resending with the attachment: finance.rgrd.` reads another program and makes everyone
quoted in its thread callable from then on. The attachment's own body never runs. File names
are relative to the program you ran, and anyone in the attachment with the same name as
someone already on the thread replaces them.

```
Subject: Fwd: budget owner

Hi Dave,

Resending with the attachment: finance.rgrd.

Just to level-set, budget is Priya's take.
Circling back on budget.

Best,
Ihor
```

This prints 250, which is Priya's net-net in `examples/finance.rgrd`. If the file is missing
or doesn't parse, that is an error at the line that asked for it, so an out-of-office can
catch it.

---

## 7. Reply-all

A `Cc:` line above the greeting lists people by name. `Replying all.` calls all of them at
once, each on its own Python thread (the other kind), and waits for every one to sign off
before moving on.
`Replying all, re: <a>.` gives each of them the same `the ask`.

```
Subject: Q4 planning — please add your numbers
Cc: Dave Okonkwo <dave@example.com>, Priya Raman <priya@example.com>
```

Replies share variables and nothing locks them. If two replies change the same variable,
updates get lost, which is both the easiest implementation and the accurate one. In one run
where Dave and Priya each added 1 to a shared counter 20,000 times, the counter finished at
23,187. Lines printed by different people can also arrive in any order.

When a reply fails, the program stops with that error after the other replies finish, unless
an out-of-office around `Replying all.` catches it. A quoted message can carry its own `Cc:`
line, which is the list for any `Replying all.` in that message. HR is never called, because
HR is only cc'd for visibility (section 10).

---

## 8. The backlog

| Idiom | Semantics |
|---|---|
| `Adding <a> to the backlog.` | add `a` to the backlog |
| `Picking up the next backlog item as <var>.` | take the oldest item |
| `Picking up the most urgent backlog item as <var>.` | take the newest item |
| `we still have a backlog` | the backlog isn't empty (condition) |
| `the backlog is empty` | the backlog is empty (condition) |
| `the size of the backlog` | how many items it holds (expression) |

The next item is the one that has waited longest. The most urgent one is whatever came in
last, which is how urgency usually works. Picking up from an empty backlog is an error.

A word in front names a separate backlog: `Adding 5 to the design backlog.` and
`we still have a design backlog`. Backlogs belong to the whole thread. Offline scopes don't
hide them, and every reply to a reply-all sees the same ones.

---

## 9. Jargon

```
Going forward, "let's action [ticket]" means "Adding [ticket] to the backlog".

Let's action 3.
Let's action 5.
```

`Going forward, "<phrase>" means "<statement>".` teaches the thread a new phrase. Before
anything runs, every later line that matches the phrase is replaced with the statement,
including lines in the quoted thread below. Lines above the definition keep their old
meaning, since it only applies going forward.

A word in `[brackets]` matches anything and carries it across. When the statement doesn't end
in punctuation, it takes the phrase's, so `Let's action 3.` becomes `Adding 3 to the backlog.`
Jargon can be defined in terms of other jargon, and it can take over a built-in phrase,
sign-offs included. Jargon that keeps expanding into itself is an error.

---

## 10. When HR is cc'd

With `HR` on the `Cc:` line, the email has to stay professional. Between a fifth and a third
of its statements, counting the ones inside blocks, must be pleasantries:

- `Hope you're well.` or `Hope you are doing well.`
- `Hope this helps.` or `Hope you had a great weekend.`
- `Thanks!`, `Thank you.`, `Appreciate it.` or `Much appreciated.`
- `Thanks in advance.` or `Sorry for the delay!`

Too few is `this email is too curt`, and too many is `this email is sycophantic`. Both are
errors before anything runs. FYI lines and jargon definitions don't count either way. The
rule comes from INTERCAL, which rejects a program that doesn't say PLEASE often enough, and
also one that says it too often.

Without HR, pleasantries do nothing and nobody is counting. `Replying all.` never calls HR,
because HR never replies.

---

## 11. Saved emails

```
python3 regards.py examples/budget.eml
```

A program can be a real email saved as an `.eml` file, which is what Gmail's "Download
message" gives you. Email encodings are decoded first, and the `Subject:` and `Cc:` headers
count, so reply-all and HR politeness work as usual.

The plain-text version of the email is used when there is one. An HTML-only email is
flattened to text, and its quoted replies (`<blockquote>`, which is how Gmail quotes) become
`>` quoting, so the thread below the signature still defines people.

`Resending with the attachment: finance.rgrd.` looks inside the email before it looks on
disk. If a file called `finance.rgrd` is attached, that is the one it reads, so a thread with
its attachments is self-contained. `examples/budget.eml` is one of those: it attaches
`finance.rgrd`, cc's HR, and prints 250.

Outlook doesn't quote replies with `>`. It stacks earlier messages under `From:`, `Sent:`, `To:`
and `Subject:` lines instead, and that works too, in any program: each header block counts as
`On …, <Name> wrote:`, and the message under it counts as quoted. Forwarded messages work the
same way. The sender can be written `Dave Okonkwo <dave@example.com>`, `Okonkwo, Dave` or just
`dave.okonkwo@example.com`, and in every case the person is Dave. A `Cc:` line in the block is
the cc list for that message.

---

## 12. Examples

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

### Async standup

A backlog, jargon, a hiring freeze, a pronoun and a mail merge, with HR watching. It prints
`4 engineers, 16 points this sprint`.

```
Subject: Async standup — no call today
Cc: HR <hr@example.com>

Hi team,

Hope you're well.
FYI, this replaces the 9am call.
Going forward, "let's action [ticket]" means "Adding [ticket] to the backlog".

Just to level-set, we have 4 engineers.
We have a hiring freeze on engineers.
Good news — we've added another engineer.

Let's action 3.
Let's action 5.
Let's action 8.

Just to level-set, points is 0.
Per my last email, while we still have a backlog:
> Picking up the next backlog item as ticket.
> Rolling it into points.

Circling back on "[engineers] engineers, [points] points this sprint".
Thanks!
Hope this helps.

Best,
Ihor
```

### Truth-machine

The [esolangs truth-machine](https://esolangs.org/wiki/Truth-machine): read a number, print 0
once, or print 1 forever. Here "forever" is Dave bumping the thread. Put
`Blocking 1 minute for this.` under the greeting and forever lasts 28 ones, then
`we're over time`.

```
Subject: Quick yes/no — need an answer

Hi Dave,

Just to level-set, answer is 0.
Please advise.
Thanks in advance.

If answer is at zero:
> Circling back on answer.
That said:
> As discussed, Dave.

Best,
Ihor

On Tue, 8 Sep 2026, Dave Okonkwo <dave@example.com> wrote:
> Hi Ihor,
>
> Circling back on answer.
> Bumping this.
>
> Best,
> Dave
```

### 99 unread emails

[99 bottles of beer](https://esolangs.org/wiki/99_bottles_of_beer), adapted for the office.
It starts with `99 unread emails in the inbox, 99 unread emails.` and ends at inbox zero, which
never lasts.

```
Subject: Re: Re: Re: inbox zero initiative

Hi all,

Just to level-set, we have 99 unread emails.

Per my last email, while we still have unread emails:
> If we're over 1 on emails:
> > Circling back on "[emails] unread emails in the inbox, [emails] unread emails.".
> That said:
> > Circling back on "1 unread email in the inbox, 1 unread email.".
> Quick flag: one email is now closed.
> If we're over 1 on it:
> > Circling back on "Archive one, mark it as read, [emails] unread emails in the inbox.".
> That said, if we're over 0 on it:
> > Circling back on "Archive one, mark it as read, 1 unread email in the inbox.".
> That said:
> > Circling back on "Archive one, mark it as read, inbox zero.".
> Circling back on "".

Circling back on "No unread emails in the inbox, no unread emails.".
Circling back on "Check again, and there are 99 unread emails in the inbox.".

Best,
Ihor
```

### Planning poker

Each story in the backlog gets a random estimate. The round is offline, so `story` and
`estimate` vanish after each vote, while `total` keeps adding up. One run printed:

```
Story 101: 8 points
Story 102: 12 points
Story 103: 6 points
Total: 26 points, give or take
```

```
Subject: Planning poker — async, please vote by EOD

Hi team,

Adding 101 to the backlog.
Adding 102 to the backlog.
Adding 103 to the backlog.

Just to level-set, total is 0.

Per my last email, while we still have a backlog:
> Happy to take this offline.
> Picking up the next backlog item as story.
> Just to level-set, estimate is somewhere between 1 and 13.
> Circling back on "Story [story]: [estimate] points".
> Rolling estimate into total.

Circling back on "Total: [total] points, give or take".

Best,
Ihor
```

### Sent from my iPhone

Five typos, and it still prints `4` and then `all reqs filled`, with a warning for every fix.

```
Subject: Re: quick update on hiring

Hi Priya,

Just to levl-set, we have 3 open reqs.
Good news — we've addded another req.
Circlign back on reqs.

Per my last emaill, while we still have reqs:
> Quick flag: one req is now closedd.

Circling back on "all reqs filled".

Best,
Ihor

Sent from my iPhone
```

### Cat program

Everything that comes in goes back out, exactly as received.

```
Subject: Fwd: Fwd: Fwd: FW: read this

Hi all,

FYI, forwarding this exactly as I received it.

Just to level-set, letter is 0.
Reading between the lines.

Per my last email, while we're over -1 on letter:
> Let me spell it out.
> Reading between the lines.

Best,
Ihor
```

### Brainfuck interpreter

Send it a Brainfuck program, then a `!`, then whatever the program should read:

```
printf '%s!' '++++++++[>++++[>++>+++>+++>+<<<<-]>+>+>->>+[<]<-]>>.>---.+++++++..+++.>>.<-.<.+++.------.--------.>>+.>++.' \
  | python3 regards.py examples/brainfuck.rgrd
```

The program sits in two backlogs used as stacks, one for what's ahead and one for what's
behind, and the tape is two more. Cells wrap at 256, and reading past the end of the input
gives 0.

```
Subject: Re: Fwd: Brainfuck — can someone from IT take a look?

Hi IT,

FYI, send the Brainfuck program first, then a !, then whatever it should read.
FYI, the program sits in two backlogs, what's ahead and what's behind. So does the tape.

Just to level-set, letter is 0.
Reading between the lines.
Per my last email, while we're over -1 on letter:
> If we're at 33 on letter:
> > Per the attached, letter is now -1.
> That said:
> > Adding letter to the intake backlog.
> > Reading between the lines.

Per my last email, while we still have an intake backlog:
> Picking up the most urgent intake backlog item as instruction.
> Adding instruction to the ahead backlog.

Just to level-set, cell is 0.

Per my last email, while we still have an ahead backlog:
> Picking up the most urgent ahead backlog item as instruction.
> Adding instruction to the behind backlog.
> If we're at 43 on instruction:
> > Good news — we've added another cell.
> > If we're at 256 on cell:
> > > cell is off the table.
> That said, if we're at 45 on instruction:
> > Quick flag: one cell is now closed.
> > If we're at -1 on cell:
> > > Per the attached, cell is now 255.
> That said, if we're at 62 on instruction:
> > Adding cell to the left backlog.
> > cell is off the table.
> > If we still have a right backlog:
> > > Picking up the most urgent right backlog item as cell.
> That said, if we're at 60 on instruction:
> > Adding cell to the right backlog.
> > cell is off the table.
> > If we still have a left backlog:
> > > Picking up the most urgent left backlog item as cell.
> That said, if we're at 46 on instruction:
> > Let me spell cell out.
> That said, if we're at 44 on instruction:
> > cell is off the table.
> > Reading between the lines.
> > If we're at -1 on cell:
> > > cell is off the table.
> That said, if we're at 91 on instruction:
> > If cell is at zero:
> > > Just to level-set, we have 1 layers.
> > > Per my last email, while we still have layers:
> > > > Picking up the most urgent ahead backlog item as instruction.
> > > > Adding instruction to the behind backlog.
> > > > If we're at 91 on instruction:
> > > > > Good news — we've added another layer.
> > > > That said, if we're at 93 on instruction:
> > > > > Quick flag: one layer is now closed.
> That said, if we're at 93 on instruction:
> > If we still have cell:
> > > Picking up the most urgent behind backlog item as instruction.
> > > Adding instruction to the ahead backlog.
> > > Just to level-set, we have 1 layers.
> > > Per my last email, while we still have layers:
> > > > Picking up the most urgent behind backlog item as instruction.
> > > > Adding instruction to the ahead backlog.
> > > > If we're at 93 on instruction:
> > > > > Good news — we've added another layer.
> > > > That said, if we're at 91 on instruction:
> > > > > Quick flag: one layer is now closed.

Best,
IT
```

---

## 13. Errors

Diagnostics are written in register. An error that no out-of-office catches stops the program
with exit code 2.

```
warning: `Sent from my iPhone` present; optimizations disabled, autocorrect on.

warning: autocorrected `Circlign` to `circling` (line 6)

error: Dave isn't on this thread. Happy to resend (line 3)

error: nobody told me about `budget`. Can you send it over? (line 3)

error: `Let's synergize.` isn't something I can action (line 3)

error: unreachable code after `Best,`. (line 8)
       Nothing below a sign-off is read. This is true of email generally.

error: splitting across zero. That's not a realistic plan (line 5)

error: this thread has too many replies. Let's set up a meeting (line 4)

error: Dave signed off without a net-net. What's the takeaway? (line 4)

error: `Net-net` in the original email. There's nobody to report back to (line 6)

error: the attachment `finance.rgrd` didn't come through. Can you resend? (line 5)

error: nobody is cc'd. Reply-all to whom? (line 7)

error: HR is cc'd and this email is too curt. Maybe open with `Hope you're well.` (line 2)

error: the backlog is empty. Nothing to pick up, so enjoy the quiet sprint (line 9)

error: we're over time. Let's continue next week (line 12)

error: somewhere between 8 and 3 isn't a range. Did you mean between 3 and 8? (line 5)

error: not sure what `it` refers to. Can you be more specific? (line 5)

error: this jargon goes in circles. Can someone say it in plain English? (line 7)

error: -1 isn't a letter, so there's nothing to spell out (line 5)

error: reading between the lines of nothing in particular (line 5)

error: this email has no text in it. Was it all screenshots?

error: no sign-off. The thread is still open.
```

The last one has no line number, because the problem is everything after the last line.

---

## 14. Computational class

`Regards,` is Turing complete, because it can simulate a two-counter
[Minsky machine](https://esolangs.org/wiki/Minsky_machine), and those are known to be
Turing complete.

Integers have no upper limit, so two variables can hold the counters.
`Good news — we've added another` increments one and `Quick flag: one … is now closed`
decrements it. A third variable holds the machine's current state. The program is a single
`Per my last email, while` loop with an `If` / `That said, if` branch for each state, and a
state that jumps on zero tests its counter with `is at zero` before setting the next state.

The Brainfuck interpreter in section 12 is a more direct demonstration: Brainfuck with an
unbounded tape is Turing complete, and the backlogs holding the tape have no size limit.

---

## 15. Design decisions

### Settled

- **`Per my last email` is a `while` loop.** The faithful unconditional backward jump
  already exists as `Bumping this.`, and control flow gets one idiom per job. Sign-offs are
  another matter, because email has a lot of ways to say goodbye.
- **`Bumping this.` re-sends the current message.** It restarts the program, or the person
  being called, from the top. It does not target labels, because email has none.
- **`Thanks in advance.` is a warning that cannot be suppressed.**
- **Sign-offs carry exit codes.** Bare `Regards,` exits 1. Everything warmer exits 0.
- **Passing an argument takes the call offline.** Recursion needs private variables, and a
  plain call keeps sharing everything, so programs written before `re:` existed still work.
- **Reply-all has no locking.** Replies share variables and updates can be lost. Nobody
  coordinates a real reply-all either.
- **`Sent from my iPhone` turns on autocorrect.** A tree-walking interpreter has no
  optimizations to disable, and excusing typos is what that signature is for anyway.
- **Politeness is only checked when HR is cc'd.** Otherwise every two-line email would need
  a pleasantry, and nobody writes those unless someone is watching.
- **`we're at` joined `we're under` and `we're over`.** Writing the Brainfuck interpreter
  showed that the language had no equality test, and the phrase for one was already there.

### Still open

Nothing right now. Suggestions are welcome, ideally without a meeting.

---

## 16. Implementation

The reference interpreter is a tree-walking interpreter written in Python. It needs Python 3.9
or newer and nothing else.

```
python3 regards.py examples/fizzbuzz.rgrd      # run a program
python3 regards.py examples/budget.eml         # run a saved email
python3 regards.py --version                   # prints the version
pip install regards                            # installs the same thing as a `regards` command
python3 -m unittest discover -s tests          # run the tests
```

Exit codes: 0 for a warm sign-off, 1 for a bare `Regards,`, 2 for an error in the program,
3 for a bug in the interpreter itself.

```
regards/
  README.md              this file
  CHANGELOG.md           what's in each version
  CONTRIBUTING.md        how to change the language without breaking anyone's email
  LICENSE                CC0 1.0
  regards.py             lexer, parser, interpreter
  examples/
    hello.rgrd
    countdown.rgrd
    fizzbuzz.rgrd
    factorial.rgrd
    dave.rgrd            calling a person from the quoted thread
    forecast.rgrd        recursion with a net-net and the ask
    ooo.rgrd             an auto-reply catching a division by zero
    attachment.rgrd      calling Priya from finance.rgrd
    finance.rgrd
    reply_all.rgrd       Dave and Priya replying at once
    standup.rgrd         backlog, jargon, a freeze and a mail merge, with HR on cc
    truth_machine.rgrd   read a number, then bump the thread forever
    unread.rgrd          99 bottles of beer, as 99 unread emails
    planning_poker.rgrd  random estimates for a backlog of stories
    typos.rgrd           five typos, fixed by Sent from my iPhone
    cat.rgrd             a cat program: input goes straight back out
    brainfuck.rgrd       a Brainfuck interpreter
    budget.eml           a saved email with an attachment, cc'ing HR
  tests/
    test_regards.py
  playground/            the web playground at regards-pearl.vercel.app
    app.py               Flask routes
    sandbox.py           runs each program in its own process, with a time limit
    runner.py            what runs inside that process
    templates/ static/   the page
    build_vercel.py      assembles the folder that Vercel deploys
    tests/
```

A saved `.eml` file is turned into plain text first, with Python's own `email` package. The
lexer then works line by line. It counts the leading `>` markers to get the quote depth and
matches the rest of the line against the idiom table, after dropping FYI lines and expanding
jargon. Quote depth then becomes a tree of
blocks, much as Python turns indentation into INDENT and DEDENT tokens, and the interpreter
walks that tree. Variables live in a stack of scopes, with the shared ones at the bottom and
any offline ones above. Each reply to a reply-all runs on its own Python thread.

The parser is the interesting part, and it is small. The idiom table is where the work is,
and the idiom table is also the joke, so the work and the joke are the same work.

### Playground

[regards-pearl.vercel.app](https://regards-pearl.vercel.app) is a small Flask app in
`playground/`. Every program runs in a separate process that gets 5 seconds, 100,000
characters of output and 1 GB of memory where the operating system allows a limit.
`Resending with the attachment:` only reads files attached inside an uploaded email, never
files on the server.

```
python3 -m venv .venv
.venv/bin/pip install -r playground/requirements.txt
.venv/bin/flask --app playground/app run --port 8321     # http://127.0.0.1:8321
python3 playground/build_vercel.py                         # then, from build/vercel:
vercel deploy --prod
```

---

## 17. License

Everything in this repository, including this specification, is dedicated to the public
domain under [CC0 1.0](https://github.com/KvashaIhor/regards/blob/main/LICENSE). Feel free to
reply-all.
