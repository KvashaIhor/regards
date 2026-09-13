import contextlib
import io
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import unittest
from email.message import EmailMessage

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import regards  # noqa: E402


def run(source, stdin="", **options):
    out = io.StringIO()
    code = regards.run(source, stdin=io.StringIO(stdin), stdout=out, **options)
    return out.getvalue(), code


def email(*body, sign_off="Best,", after="", cc=None):
    header = "Subject: test\n" + (f"Cc: {cc}\n" if cc else "")
    return header + "\nHi team,\n\n" + "\n".join(body) + f"\n\n{sign_off}\nIhor\n" + after


def eml(body, html=None, cc=None, attachments=()):
    """A saved email, as the bytes an email client would write to a .eml file."""
    message = EmailMessage()
    message["Subject"] = "Re: test"
    message["From"] = "Ihor <ihor@example.com>"
    message["To"] = "Team <team@example.com>"
    if cc:
        message["Cc"] = cc
    if body is not None:
        message.set_content(body)
    if html is not None:
        if body is None:
            message.set_content(html, subtype="html")
        else:
            message.add_alternative(html, subtype="html")
    for name, content in attachments:
        message.add_attachment(content, filename=name)
    return bytes(message)


def person(name, *body, cc=None):
    """A quoted message from `name`, to go in the thread below the signature."""
    header = f"> Cc: {cc}\n" if cc else ""
    quoted = "".join(f"> {line}\n" for line in body)
    return (f"\nOn Mon, 7 Sep 2026, {name} Okonkwo <{name.lower()}@example.com> wrote:\n"
            f"{header}> Hi Ihor,\n{quoted}> Best,\n> {name}\n")


class Examples(unittest.TestCase):
    def example(self, name, stdin=""):
        path = ROOT / "examples" / name
        return run(path.read_text(encoding="utf-8"), stdin=stdin, path=str(path))

    def test_hello(self):
        self.assertEqual(self.example("hello.rgrd"), ("Hello, World\n", 0))

    def test_countdown(self):
        self.assertEqual(self.example("countdown.rgrd"), ("5\n4\n3\n2\n1\n", 0))

    def test_factorial(self):
        self.assertEqual(self.example("factorial.rgrd"), ("120\n", 0))

    def test_fizzbuzz(self):
        expected = []
        for i in range(1, 101):
            expected.append("retro + all-hands" if i % 15 == 0 else "retro" if i % 3 == 0
                            else "all-hands" if i % 5 == 0 else str(i))
        out, code = self.example("fizzbuzz.rgrd")
        self.assertEqual(out.splitlines(), expected)
        self.assertEqual(code, 0)

    def test_dave(self):
        self.assertEqual(self.example("dave.rgrd"), ("the deck is attached\n", 0))

    def test_forecast(self):
        self.assertEqual(self.example("forecast.rgrd"), ("3628800\n", 0))

    def test_ooo(self):
        self.assertEqual(self.example("ooo.rgrd"), ("no teams yet, so no split. Back Monday\n", 0))

    def test_attachment(self):
        self.assertEqual(self.example("attachment.rgrd"), ("250\n", 0))

    def test_reply_all(self):
        self.assertEqual(self.example("reply_all.rgrd"), ("4\n250\n", 0))

    def test_standup(self):
        self.assertEqual(self.example("standup.rgrd"), ("4 engineers, 16 points this sprint\n", 0))

    def test_truth_machine_zero(self):
        self.assertEqual(self.example("truth_machine.rgrd", stdin="0\n"), ("0\n", 0))

    def test_truth_machine_one_goes_on_until_the_meeting_ends(self):
        path = ROOT / "examples" / "truth_machine.rgrd"
        source = path.read_text(encoding="utf-8").replace("Hi Dave,\n", "Hi Dave,\n\nBlocking 1 minute for this.\n")
        out = io.StringIO()
        with self.assertRaises(regards.RegardsError) as ctx:
            regards.run(source, stdin=io.StringIO("1\n"), stdout=out, path=str(path))
        self.assertIn("we're over time", str(ctx.exception))
        self.assertGreater(len(out.getvalue().splitlines()), 10)
        self.assertEqual(set(out.getvalue().split()), {"1"})

    def test_unread_emails(self):
        expected = []
        for n in range(99, 0, -1):
            count = f"{n} unread emails" if n > 1 else "1 unread email"
            left = ("inbox zero" if n == 1 else "1 unread email in the inbox" if n == 2
                    else f"{n - 1} unread emails in the inbox")
            expected += [f"{count} in the inbox, {count}.", f"Archive one, mark it as read, {left}.", ""]
        expected += ["No unread emails in the inbox, no unread emails.",
                     "Check again, and there are 99 unread emails in the inbox."]
        out, code = self.example("unread.rgrd")
        self.assertEqual((out.splitlines(), code), (expected, 0))

    def test_planning_poker(self):
        out, code = self.example("planning_poker.rgrd")
        *stories, total = out.splitlines()
        self.assertEqual(len(stories), 3)
        estimates = []
        for story, line in zip((101, 102, 103), stories):
            m = re.fullmatch(rf"Story {story}: (\d+) points", line)
            self.assertIsNotNone(m, line)
            estimates.append(int(m.group(1)))
        self.assertTrue(all(1 <= estimate <= 13 for estimate in estimates), estimates)
        self.assertEqual((total, code), (f"Total: {sum(estimates)} points, give or take", 0))

    def test_typos(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            result = self.example("typos.rgrd")
        self.assertEqual(result, ("4\nall reqs filled\n", 0))
        self.assertEqual(err.getvalue().count("autocorrected"), 5)

    def test_cat(self):
        self.assertEqual(self.example("cat.rgrd", stdin="Hello,\nworld!\n"), ("Hello,\nworld!\n", 0))

    def test_brainfuck_hello_world(self):
        program = "++++++++[>++++[>++>+++>+++>+<<<<-]>+>+>->>+[<]<-]>>.>---.+++++++..+++.>>.<-.<.+++.------.--------.>>+.>++."
        self.assertEqual(self.example("brainfuck.rgrd", stdin=program + "!"), ("Hello World!\n", 0))

    def test_brainfuck_reads_its_own_input(self):
        self.assertEqual(self.example("brainfuck.rgrd", stdin=",[.,]!office hours"), ("office hours", 0))

    def test_saved_email(self):
        source, attachments = regards.load_eml((ROOT / "examples" / "budget.eml").read_bytes())
        self.assertEqual(run(source, attachments=attachments), ("250\n", 0))


class Semantics(unittest.TestCase):
    def test_arithmetic(self):
        out, _ = run(email(
            "Just to level-set, x is 7.",
            "Just to level-set, y is 3.",
            "Rolling y into x.",          # 10
            "Doubling down on x.",        # 20
            "Backing y out of x.",        # 17
            "Splitting x across y.",      # 5
            "Scaling x by y.",            # 15
            "Let's cut x in half.",       # 7
            "Circling back on x.",
            "Circling back on what's left after splitting x across y.",
            "y is off the table.",
            "Circling back on y.",
        ))
        self.assertEqual(out, "7\n1\n0\n")

    def test_plural_and_multiword_names_resolve(self):
        out, _ = run(email(
            "Just to level-set, we have 2 open reqs.",
            "Good news — we've added another req.",
            "Circling back on Reqs.",
        ))
        self.assertEqual(out, "3\n")

    def test_email_client_punctuation(self):
        out, _ = run(email(
            "Just to level-set, x is 1.",
            "Good news -- we’ve added another x.",
            "Circling back on “hi”.",
            "Circling back on x.",
        ))
        self.assertEqual(out, "hi\n2\n")

    def test_both_quote_styles_nest(self):
        body = ["Just to level-set, x is 3.",
                "Per my last email, while we still have x:",
                "> If there's nothing left after splitting x across 2:",
                ">> Circling back on \"even\".",
                "> That said:",
                "> > Circling back on \"odd\".",
                "> Quick flag: one x is now closed."]
        self.assertEqual(run(email(*body))[0], "odd\neven\nodd\n")

    def test_bumping_resends_the_message(self):
        after = ("\nOn Mon, 7 Sep 2026, Dave Okonkwo <dave@example.com> wrote:\n"
                 "> Hi Ihor,\n"
                 "> Good news — we've added another x.\n"
                 "> If we're under 3 on x:\n"
                 "> > Bumping this.\n"
                 "> Best,\n"
                 "> Dave\n")
        out, _ = run(email("Just to level-set, x is 0.", "As discussed, Dave.",
                           "Circling back on x.", after=after))
        self.assertEqual(out, "3\n")

    def test_read_input(self):
        out, _ = run(email(
            "Just to level-set, budget is 0.",
            "Thoughts?",
            "Doubling down on budget.",
            "Circling back on budget.",
        ), stdin="21\n")
        self.assertEqual(out, "42\n")

    def test_were_at_is_equality(self):
        out, _ = run(email("Just to level-set, x is 43.",
                           "If we're at 43 on x:", '> Circling back on "yes".',
                           "If we're at 44 on x:", '> Circling back on "no".'))
        self.assertEqual(out, "yes\n")

    def test_bare_regards_exits_nonzero(self):
        self.assertEqual(run(email("Circling back on \"ok\".", sign_off="Regards,"))[1], 1)
        self.assertEqual(run(email("Circling back on \"ok\".", sign_off="Warm regards,"))[1], 0)

    def test_nested_people_share_state(self):
        after = ("\nOn Mon, 7 Sep 2026, Dave Okonkwo <dave@example.com> wrote:\n"
                 "> Hi Ihor,\n"
                 "> Doubling down on x.\n"
                 "> Best,\n"
                 "> Dave\n")
        out, _ = run(email("Just to level-set, x is 4.", "As discussed, Dave.",
                           "Circling back on x.", after=after))
        self.assertEqual(out, "8\n")


def self_calling_dave(depth):
    """Dave counts x down to zero by calling himself, so nesting reaches `depth` calls."""
    after = ("\nOn Mon, 7 Sep 2026, Dave Okonkwo <dave@example.com> wrote:\n"
             "> Hi Ihor,\n"
             "> If we still have x:\n"
             "> > Quick flag: one x is now closed.\n"
             "> > As discussed, Dave.\n"
             "> Best,\n"
             "> Dave\n")
    return email(f"Just to level-set, x is {depth - 1}.", "As discussed, Dave.",
                 'Circling back on "done".', after=after)


class DeepCalls(unittest.TestCase):
    def test_1000_nested_calls_succeed(self):
        self.assertEqual(run(self_calling_dave(1000)), ("done\n", 0))

    def test_1001_nested_calls_suggest_a_meeting(self):
        with self.assertRaises(regards.RegardsError) as ctx:
            run(self_calling_dave(1001))
        self.assertIn("Let's set up a meeting", str(ctx.exception))

    def test_cli_exits_2_not_1(self):
        with tempfile.NamedTemporaryFile("w", suffix=".rgrd", delete=False) as f:
            f.write(self_calling_dave(5000))
        try:
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = regards.main(["regards.py", f.name])
        finally:
            pathlib.Path(f.name).unlink()
        self.assertEqual(code, 2)
        self.assertIn("Let's set up a meeting", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())


class CommandLine(unittest.TestCase):
    def main(self, *args):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = regards.main(["regards.py", *args])
        return code, err.getvalue()

    def test_version(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = regards.main(["regards.py", "--version"])
        self.assertEqual((out.getvalue(), code), ("Regards, 1.0.0\n", 0))

    def test_missing_file_exits_2(self):
        code, err = self.main("nope.rgrd")
        self.assertEqual(code, 2)
        self.assertIn("couldn't open `nope.rgrd`", err)
        self.assertNotIn("Traceback", err)

    def test_directory_exits_2(self):
        with tempfile.TemporaryDirectory() as d:
            code, err = self.main(d)
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", err)

    def test_eml_files_run_from_the_command_line(self):
        result = subprocess.run([sys.executable, str(ROOT / "regards.py"), str(ROOT / "examples" / "budget.eml")],
                                capture_output=True, text=True)
        self.assertEqual((result.stdout, result.returncode), ("250\n", 0))

    def test_binary_file_exits_2(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".rgrd", delete=False) as f:
            f.write(b"\xff\xfe\x00bad")
        try:
            code, err = self.main(f.name)
        finally:
            pathlib.Path(f.name).unlink()
        self.assertEqual(code, 2)
        self.assertIn("isn't UTF-8", err)


class ErrorCase(unittest.TestCase):
    def assertError(self, source, fragment, **options):
        with self.assertRaises(regards.RegardsError) as ctx:
            run(source, **options)
        self.assertIn(fragment, str(ctx.exception))


class Errors(ErrorCase):

    def test_no_sign_off(self):
        self.assertError("Hi team,\n\nCircling back on \"x\".\n", "The thread is still open")

    def test_unreachable_after_sign_off(self):
        self.assertError(email("Circling back on \"x\".", after="Circling back on \"y\".\n"),
                         "unreachable code after `Best,`")

    def test_unknown_variable(self):
        self.assertError(email("Circling back on budget."), "nobody told me about `budget`")

    def test_unknown_person(self):
        self.assertError(email("As discussed, Dave."), "Dave isn't on this thread")

    def test_unknown_statement(self):
        self.assertError(email("Let's synergize."), "isn't something I can action")

    def test_block_needs_body(self):
        self.assertError(email("Just to level-set, x is 1.", "If we still have x:"),
                         "needs a reply quoted underneath")


class NetNet(ErrorCase):
    def test_take_is_the_net_net(self):
        out, _ = run(email("Just to level-set, forecast is Dave's take.", "Circling back on forecast.",
                           after=person("Dave", "Net-net, 42.")))
        self.assertEqual(out, "42\n")

    def test_net_net_ends_the_message_early(self):
        out, _ = run(email("As discussed, Dave.", 'Circling back on "after".',
                           after=person("Dave", "Net-net, 1.", 'Circling back on "never".')))
        self.assertEqual(out, "after\n")

    def test_net_net_leaves_loops(self):
        out, _ = run(email("Just to level-set, x is 5.", "Circling back on Dave's take.",
                           after=person("Dave", "Per my last email, while we still have x:",
                                        "> Net-net, x.", "> Quick flag: one x is now closed.")))
        self.assertEqual(out, "5\n")

    def test_take_without_net_net(self):
        self.assertError(email("Circling back on Dave's take.", after=person("Dave", 'Circling back on "hi".')),
                         "Dave signed off without a net-net")

    def test_net_net_in_the_original_email(self):
        self.assertError(email("Net-net, 1."), "nobody to report back to")


class Arguments(ErrorCase):
    def test_re_passes_the_ask(self):
        out, _ = run(email("Just to level-set, budget is 7.", "As discussed, Dave, re: budget.",
                           after=person("Dave", "Circling back on the ask.")))
        self.assertEqual(out, "7\n")

    def test_the_ask_is_a_copy(self):
        out, _ = run(email("Just to level-set, budget is 21.", "Circling back on Dave's take on budget.",
                           "Circling back on budget.",
                           after=person("Dave", "Doubling down on the ask.", "Net-net, the ask.")))
        self.assertEqual(out, "42\n21\n")

    def test_re_takes_the_call_offline(self):
        self.assertError(email("As discussed, Dave, re: 1.", "Circling back on note.",
                               after=person("Dave", "Just to level-set, note is 5.")),
                         "nobody told me about `note`")

    def test_take_with_an_argument_in_a_comparison(self):
        dave = person("Dave", "Net-net, the ask.")
        for comparison, expected in (("under", "yes\n"), ("over", "no\n")):
            with self.subTest(comparison):
                out, _ = run(email("Just to level-set, sprint is 1.", "Just to level-set, budget is 3.",
                                   f"If we're {comparison} Dave's take on budget on sprint:",
                                   '> Circling back on "yes".', "That said:", '> Circling back on "no".',
                                   after=dave))
                self.assertEqual(out, expected)

    def test_plain_call_still_shares_new_variables(self):
        out, _ = run(email("As discussed, Dave.", "Circling back on note.",
                           after=person("Dave", "Just to level-set, note is 5.")))
        self.assertEqual(out, "5\n")

    def test_recursion(self):
        dave = person("Dave",
                      "If the ask is at zero:",
                      "> Net-net, 1.",
                      "Just to level-set, smaller is the ask.",
                      "Quick flag: one smaller is now closed.",
                      "Just to level-set, total is Dave's take on smaller.",
                      "Scaling total by the ask.",
                      "Net-net, total.")
        self.assertEqual(run(email("Circling back on Dave's take on 6.", after=dave)), ("720\n", 0))


class OfflineScopes(ErrorCase):
    def test_declarations_are_private_to_the_block(self):
        out, _ = run(email("Just to level-set, x is 1.",
                           "If we still have x:",
                           "> Happy to take this offline.",
                           "> Just to level-set, x is 99.",
                           "> Circling back on x.",
                           "Circling back on x."))
        self.assertEqual(out, "99\n1\n")

    def test_existing_variables_are_still_shared(self):
        out, _ = run(email("Just to level-set, x is 1.",
                           "If we still have x:",
                           "> Happy to take this offline.",
                           "> Good news — we've added another x.",
                           "Circling back on x."))
        self.assertEqual(out, "2\n")

    def test_scope_ends_with_its_block(self):
        self.assertError(email("Just to level-set, x is 1.",
                               "If we still have x:",
                               "> Happy to take this offline.",
                               "> Just to level-set, note is 5.",
                               "Circling back on note."),
                         "nobody told me about `note`")

    def test_people_cannot_see_the_callers_offline_variables(self):
        self.assertError(email("Happy to take this offline.",
                               "Just to level-set, secret is 1.",
                               "As discussed, Dave.",
                               after=person("Dave", "Circling back on secret.")),
                         "nobody told me about `secret`")


class OutOfOffice(ErrorCase):
    def test_auto_reply_handles_errors_in_the_rest_of_the_block(self):
        out, code = run(email("I am currently OOO, returning Monday:",
                              '> Circling back on "auto-reply".',
                              "Circling back on budget.",
                              'Circling back on "never".'))
        self.assertEqual((out, code), ("auto-reply\n", 0))

    def test_execution_continues_after_the_enclosing_block(self):
        out, _ = run(email("Just to level-set, x is 1.",
                           "If we still have x:",
                           "> I'm currently OOO, returning 14 Sep:",
                           '> > Circling back on "auto-reply".',
                           "> Circling back on budget.",
                           'Circling back on "back".'))
        self.assertEqual(out, "auto-reply\nback\n")

    def test_errors_in_called_people_reach_the_auto_reply(self):
        out, _ = run(email("I am currently OOO, returning Monday:",
                           '> Circling back on "auto-reply".',
                           "As discussed, Dave.",
                           after=person("Dave", "Circling back on budget.")))
        self.assertEqual(out, "auto-reply\n")

    def test_statements_before_the_auto_reply_are_not_covered(self):
        self.assertError(email("Circling back on budget.",
                               "I am currently OOO, returning Monday:",
                               '> Circling back on "auto-reply".'),
                         "nobody told me about `budget`")

    def test_errors_in_the_auto_reply_are_not_caught(self):
        self.assertError(email("I am currently OOO, returning Monday:",
                               "> Circling back on budget.",
                               "Circling back on forecast."),
                         "nobody told me about `budget`")

    def test_catching_too_many_replies_does_not_leak_call_depth(self):
        after = (person("Dave", "If we still have x:", "> Quick flag: one x is now closed.", "> As discussed, Dave.")
                 + person("Priya", "As discussed, Priya."))
        out, _ = run(email("Just to level-set, x is 999.",
                           "If we still have x:",
                           "> I am currently OOO, returning Monday:",
                           '> > Circling back on "meeting".',
                           "> As discussed, Priya.",
                           "As discussed, Dave.",
                           'Circling back on "done".',
                           after=after))
        self.assertEqual(out, "meeting\ndone\n")


class Attachments(ErrorCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = pathlib.Path(tmp.name)
        (folder / "finance.rgrd").write_text(
            email('Circling back on "not me".', after=person("Priya", 'Circling back on "numbers attached".')),
            encoding="utf-8")
        self.main = str(folder / "main.rgrd")

    def test_attachment_brings_its_people_but_not_its_body(self):
        out, _ = run(email("Resending with the attachment: finance.rgrd.", "As discussed, Priya."), path=self.main)
        self.assertEqual(out, "numbers attached\n")

    def test_people_arrive_with_the_attachment(self):
        self.assertError(email("As discussed, Priya.", "Resending with the attachment: finance.rgrd."),
                         "Priya isn't on this thread", path=self.main)

    def test_missing_attachment(self):
        self.assertError(email("Resending with the attachment: nope.rgrd."), "didn't come through", path=self.main)


class ReplyAll(ErrorCase):
    CC = "Dave Okonkwo <dave@example.com>, Priya Okonkwo <priya@example.com>"

    def test_everyone_on_cc_runs_before_the_thread_continues(self):
        after = person("Dave", "Just to level-set, deck is 1.") + person("Priya", "Just to level-set, budget is 2.")
        out, _ = run(email("Replying all.", "Circling back on deck.", "Circling back on budget.",
                           after=after, cc=self.CC))
        self.assertEqual(out, "1\n2\n")

    def test_reply_all_passes_the_ask_to_everyone(self):
        after = person("Dave", "Circling back on the ask.") + person("Priya", "Circling back on the ask.")
        self.assertEqual(run(email("Replying all, re: 7.", after=after, cc=self.CC))[0], "7\n7\n")

    def test_forks_run_at_the_same_time(self):
        after = person("Dave", "Sorry for the delay!") + person("Priya", "Sorry for the delay!")
        start = time.monotonic()
        run(email("Replying all.", after=after, cc=self.CC))
        self.assertLess(time.monotonic() - start, 1.8)

    def test_cc_inside_a_quoted_message(self):
        after = (person("Dave", "Replying all.", cc="Priya Okonkwo <priya@example.com>")
                 + person("Priya", 'Circling back on "from priya".'))
        self.assertEqual(run(email("As discussed, Dave.", after=after))[0], "from priya\n")

    def test_no_one_on_cc(self):
        self.assertError(email("Replying all."), "nobody is cc'd")

    def test_cc_d_person_not_on_the_thread(self):
        self.assertError(email("Replying all.", cc="Dave Okonkwo <dave@example.com>"), "Dave isn't on this thread")

    def test_an_error_in_one_fork_stops_the_program(self):
        after = person("Dave", "Circling back on budget.") + person("Priya", 'Circling back on "fine".')
        self.assertError(email("Replying all.", after=after, cc=self.CC), "nobody told me about `budget`")


class Comments(unittest.TestCase):
    def test_fyi_lines_are_ignored(self):
        out, _ = run(email("FYI, this is just for context.",
                           'Circling back on "ok".',
                           "Just to level-set, x is 1.",
                           "If we still have x:",
                           "> FYI: nothing to see here:",
                           '> Circling back on "still ok".'))
        self.assertEqual(out, "ok\nstill ok\n")

    def test_ps_below_the_sign_off_is_allowed(self):
        out, _ = run(email('Circling back on "ok".', after="P.S. Nobody reads this part either.\n"))
        self.assertEqual(out, "ok\n")


class Jargon(ErrorCase):
    def test_going_forward_defines_a_phrase(self):
        out, _ = run(email("Just to level-set, revenue is 2.",
                           'Going forward, "let\'s synergize" means "Doubling down on revenue".',
                           "Let's synergize.",
                           "Circling back on revenue."))
        self.assertEqual(out, "4\n")

    def test_placeholders_carry_words_across(self):
        out, _ = run(email('Going forward, "let\'s synergize on [thing]" means "Doubling down on [thing]".',
                           "Just to level-set, budget is 5.",
                           "Let's synergize on budget.",
                           "Circling back on budget."))
        self.assertEqual(out, "10\n")

    def test_jargon_only_applies_going_forward(self):
        self.assertError(email("Let's synergize.", 'Going forward, "let\'s synergize" means "Bumping this".'),
                         "`Let's synergize.` isn't something I can action")

    def test_jargon_reaches_the_thread_below(self):
        out, _ = run(email('Going forward, "send the deck" means "Circling back on "deck attached"".',
                           "As discussed, Dave.",
                           after=person("Dave", "Send the deck.")))
        self.assertEqual(out, "deck attached\n")

    def test_jargon_can_rename_a_sign_off(self):
        self.assertEqual(run(email('Going forward, "Best," means "Regards,".', 'Circling back on "x".'))[1], 1)

    def test_circular_jargon(self):
        self.assertError(email('Going forward, "ping" means "pong".', 'Going forward, "pong" means "ping".', "Ping."),
                         "goes in circles")


class MailMerge(unittest.TestCase):
    def test_placeholders_are_filled_from_variables(self):
        out, _ = run(email("Just to level-set, we have 3 open reqs.", 'Circling back on "We have [reqs] open reqs".'))
        self.assertEqual(out, "We have 3 open reqs\n")

    def test_unknown_placeholders_go_out_as_typed(self):
        out, _ = run(email('Circling back on "Hi [First Name], hope you are well".'))
        self.assertEqual(out, "Hi [First Name], hope you are well\n")


class HiringFreeze(unittest.TestCase):
    def test_writes_to_a_frozen_variable_do_nothing(self):
        out, _ = run(email("Just to level-set, we have 2 reqs.",
                           "We have a hiring freeze on reqs.",
                           "Good news — we've added another req.",
                           "Per the attached, reqs is now 10.",
                           "Circling back on reqs.",
                           "The freeze on reqs is lifted.",
                           "Good news — we've added another req.",
                           "Circling back on reqs."))
        self.assertEqual(out, "2\n3\n")


class Autocorrect(ErrorCase):
    def test_sent_from_my_iphone_fixes_typos(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            out, _ = run(email("Just to levle-set, x is 2.", "Circlign back on x.", after="\nSent from my iPhone\n"))
        self.assertEqual(out, "2\n")
        self.assertIn("autocorrected `Circlign` to `circling`", err.getvalue())
        self.assertIn("autocorrect on", err.getvalue())

    def test_typos_inside_conditions(self):
        with contextlib.redirect_stderr(io.StringIO()):
            out, _ = run(email("Just to level-set, x is 1.", "If we stil have x:", '> Circling back on "yes".',
                               after="\nSent from my iPhone\n"))
        self.assertEqual(out, "yes\n")

    def test_typos_are_errors_without_the_iphone(self):
        self.assertError(email('Circlign back on "x".'), "isn't something I can action")


class Backlog(ErrorCase):
    def test_next_item_is_the_oldest(self):
        out, _ = run(email("Adding 1 to the backlog.",
                           "Adding 2 to the backlog.",
                           "Adding 3 to the backlog.",
                           "Per my last email, while we still have a backlog:",
                           "> Picking up the next backlog item as task.",
                           "> Circling back on task."))
        self.assertEqual(out, "1\n2\n3\n")

    def test_most_urgent_item_is_the_newest(self):
        out, _ = run(email("Adding 1 to the backlog.",
                           "Adding 2 to the backlog.",
                           "Picking up the most urgent backlog item as task.",
                           "Circling back on task.",
                           "Circling back on the size of the backlog."))
        self.assertEqual(out, "2\n1\n")

    def test_backlogs_have_names(self):
        out, _ = run(email("Adding 5 to the design backlog.",
                           "If the backlog is empty:",
                           '> Circling back on "main backlog empty".',
                           "Picking up the next design backlog item as task.",
                           "Circling back on task."))
        self.assertEqual(out, "main backlog empty\n5\n")

    def test_empty_backlog(self):
        self.assertError(email("Picking up the next backlog item as task."), "backlog is empty")


class Pronouns(ErrorCase):
    def test_it_is_the_last_variable_mentioned(self):
        out, _ = run(email("Just to level-set, budget is 5.", "Doubling down on it.", "Circling back on that."))
        self.assertEqual(out, "10\n")

    def test_it_needs_something_to_refer_to(self):
        self.assertError(email("Circling back on it."), "not sure what `it` refers to")


class Timebox(ErrorCase):
    def test_running_over_the_meeting(self):
        self.assertError(email("Blocking 1 minute for this.",
                               "Just to level-set, x is 1.",
                               "Per my last email, while we still have x:",
                               "> Good news — we've added another x."),
                         "we're over time")

    def test_short_programs_finish_inside_the_meeting(self):
        out, _ = run(email("Blocking 1 minute for this.",
                           "Just to level-set, x is 20.",
                           "Per my last email, while we still have x:",
                           "> Quick flag: one x is now closed.",
                           "Circling back on x."))
        self.assertEqual(out, "0\n")


class Estimates(ErrorCase):
    def test_somewhere_between_is_inclusive_and_random(self):
        out, _ = run(email("Just to level-set, rounds is 300.",
                           "Per my last email, while we still have rounds:",
                           "> Circling back on somewhere between 3 and 8.",
                           "> Quick flag: one round is now closed."))
        self.assertEqual(set(out.split()), {"3", "4", "5", "6", "7", "8"})

    def test_upside_down_range(self):
        self.assertError(email("Circling back on somewhere between 8 and 3."), "isn't a range")


class HumanResources(ErrorCase):
    HR = "HR <hr@example.com>"

    def test_curt_email_with_hr_on_cc(self):
        self.assertError(email('Circling back on "a".', 'Circling back on "b".', 'Circling back on "c".', cc=self.HR),
                         "too curt")

    def test_sycophantic_email_with_hr_on_cc(self):
        self.assertError(email("Hope you're well.", "Thanks!", 'Circling back on "a".', cc=self.HR), "sycophantic")

    def test_polite_email_with_hr_on_cc(self):
        out, _ = run(email("Hope you're well.", 'Circling back on "a".', 'Circling back on "b".',
                           'Circling back on "c".', cc=self.HR))
        self.assertEqual(out, "a\nb\nc\n")

    def test_hr_never_replies_all(self):
        out, _ = run(email("Hope you're well.", "Replying all.", 'Circling back on "b".', 'Circling back on "c".',
                           after=person("Dave", 'Circling back on "dave here".'),
                           cc="Dave Okonkwo <dave@example.com>, " + self.HR))
        self.assertEqual(out, "dave here\nb\nc\n")

    def test_no_hr_no_politeness_check(self):
        self.assertEqual(run(email('Circling back on "curt".'))[0], "curt\n")


class Letters(ErrorCase):
    def test_spelling_out_prints_a_character_without_a_newline(self):
        out, _ = run(email("Let me spell 72 out.", "Let me spell out 105.", "Just to level-set, bang is 33.",
                           "Let me spell it out."))
        self.assertEqual(out, "Hi!")

    def test_reading_between_the_lines_reads_one_character(self):
        out, _ = run(email("Just to level-set, letter is 0.", "Reading between the lines.", "Circling back on letter.",
                           "Reading between the lines.", "Circling back on letter."), stdin="A")
        self.assertEqual(out, "65\n-1\n")

    def test_spelling_out_a_negative_number(self):
        self.assertError(email("Let me spell -1 out."), "isn't a letter")

    def test_reading_with_nothing_mentioned(self):
        self.assertError(email("Reading between the lines."), "nothing in particular")


class OutlookThreads(ErrorCase):
    REPLY = ("Hi Dave,\n\nAs discussed, Dave.\n\nBest,\nIhor\n\n"
             "________________________________\n"
             "From: Dave Okonkwo <dave@example.com>\n"
             "Sent: Monday, September 7, 2026 9:00 AM\n"
             "To: Ihor <ihor@example.com>\n"
             "Subject: RE: deck\n\n"
             "Hi Ihor,\n\n{dave}\n\nBest,\nDave\n")

    def test_from_and_sent_blocks_define_people(self):
        out, _ = run(self.REPLY.format(dave='Circling back on "the deck is attached".'))
        self.assertEqual(out, "the deck is attached\n")

    def test_older_messages_further_down_are_callable_too(self):
        thread = self.REPLY.format(dave="As discussed, Priya.") + (
            "\n-----Original Message-----\n"
            "From: Raman, Priya <priya@example.com>\n"
            "Date: Friday, September 4, 2026 5:00 PM\n"
            "Subject: deck\n\n"
            'Hi Dave,\n\nCircling back on "from the bottom of the thread".\n\nThanks,\nPriya\n')
        self.assertEqual(run(thread)[0], "from the bottom of the thread\n")

    def test_address_only_sender_and_cc_inside_the_block(self):
        thread = ("Hi Dave,\n\nAs discussed, Dave.\n\nBest,\nIhor\n\n"
                  "From: dave.okonkwo@example.com\n"
                  "Sent: Monday, September 7, 2026 9:00 AM\n"
                  "Cc: Priya Raman <priya@example.com>\n\n"
                  "Hi Ihor,\n\nReplying all.\n\nBest,\nDave\n\n"
                  "From: Priya Raman <priya@example.com>\n"
                  "Sent: Friday, September 4, 2026 5:00 PM\n\n"
                  'Hi Dave,\n\nCircling back on "priya replied".\n\nBest,\nPriya\n')
        self.assertEqual(run(thread)[0], "priya replied\n")

    def test_forwarded_message(self):
        thread = ("Hi Dave,\n\nAs discussed, Priya.\n\nBest,\nIhor\n\n"
                  "---------- Forwarded message ---------\n"
                  "From: Priya Raman <priya@example.com>\n"
                  "Date: Fri, Sep 4, 2026 at 5:00 PM\n"
                  "Subject: numbers\n"
                  "To: Ihor <ihor@example.com>\n\n"
                  'Hi Ihor,\n\nCircling back on "forwarded".\n\nBest,\nPriya\n')
        self.assertEqual(run(thread)[0], "forwarded\n")

    def test_outlook_html_email(self):
        html = ('<div>Hi Dave,</div><div>As discussed, Dave.</div><div>Best,<br>Ihor</div><hr>'
                '<div style="border-top:solid #E1E1E1 1.0pt"><p><b>From:</b> Dave Okonkwo &lt;dave@example.com&gt;<br>'
                '<b>Sent:</b> Monday, September 7, 2026 9:00 AM<br><b>To:</b> Ihor<br><b>Subject:</b> RE: deck</p></div>'
                '<p>Hi Ihor,</p><p>Circling back on &quot;outlook html&quot;.</p><p>Best,<br>Dave</p>')
        source, attachments = regards.load_eml(eml(None, html=html))
        self.assertEqual(run(source, attachments=attachments)[0], "outlook html\n")

    def test_a_from_line_without_headers_is_not_a_thread(self):
        self.assertError("Hi team,\n\nFrom: the desk of Ihor\n\nBest,\nIhor\n", "isn't something I can action")


class SavedEmails(ErrorCase):
    BODY = "Hi team,\n\n{}\n\nBest,\nIhor\n"

    def run_eml(self, data, stdin=""):
        source, attachments = regards.load_eml(data)
        return run(source, stdin=stdin, attachments=attachments)

    def test_plain_text_email(self):
        self.assertEqual(self.run_eml(eml(self.BODY.format('Circling back on "from a saved email".'))),
                         ("from a saved email\n", 0))

    def test_encoded_body_with_curly_quotes_and_dashes(self):
        body = self.BODY.format("Just to level-set, x is 1.\nGood news — we’ve added another x.\nCircling back on x.")
        self.assertEqual(self.run_eml(eml(body))[0], "2\n")

    def test_cc_header_counts(self):
        body = self.BODY.format('Circling back on "a".\nCircling back on "b".\nCircling back on "c".')
        with self.assertRaises(regards.RegardsError) as ctx:
            self.run_eml(eml(body, cc="HR <hr@example.com>"))
        self.assertIn("too curt", str(ctx.exception))

    def test_html_only_email_with_a_quoted_thread(self):
        html = ('<html><head><style>div { color: red }</style></head><body>'
                '<div>Hi team,</div><div><br></div><div>As discussed, <b>Dave</b>.</div><div><br></div>'
                '<div>Best,<br>Ihor</div><br><div class="gmail_quote"><div>On Mon, 7 Sep 2026, Dave Okonkwo '
                '&lt;dave@example.com&gt; wrote:<br></div><blockquote class="gmail_quote">'
                '<div>Hi Ihor,</div><div>Circling back on &quot;from the blockquote&quot;.</div>'
                '<div>Best,<br>Dave</div></blockquote></div></body></html>')
        self.assertEqual(self.run_eml(eml(None, html=html))[0], "from the blockquote\n")

    def test_attachments_inside_the_email(self):
        finance = ("Hi all,\n\nCircling back on \"not me\".\n\nBest,\nPriya\n\n"
                   "On Fri, 4 Sep 2026, Priya Raman <priya@example.com> wrote:\n> Hi team,\n> Net-net, 250.\n> Best,\n> Priya\n")
        body = self.BODY.format("Resending with the attachment: finance.rgrd.\nCircling back on Priya's take.")
        self.assertEqual(self.run_eml(eml(body, attachments=[("finance.rgrd", finance)]))[0], "250\n")

    def test_email_with_no_text(self):
        message = EmailMessage()
        message["Subject"] = "see attached"
        message.add_attachment(b"\x89PNG", maintype="image", subtype="png", filename="chart.png")
        with self.assertRaises(regards.RegardsError) as ctx:
            regards.load_eml(bytes(message))
        self.assertIn("no text", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
