import contextlib
import io
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import regards  # noqa: E402


def run(source, stdin=""):
    out = io.StringIO()
    code = regards.run(source, stdin=io.StringIO(stdin), stdout=out)
    return out.getvalue(), code


def email(*body, sign_off="Best,", after=""):
    return "Subject: test\n\nHi team,\n\n" + "\n".join(body) + f"\n\n{sign_off}\nIhor\n" + after


class Examples(unittest.TestCase):
    def example(self, name):
        return run((ROOT / "examples" / name).read_text(encoding="utf-8"))

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

    def test_binary_file_exits_2(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".rgrd", delete=False) as f:
            f.write(b"\xff\xfe\x00bad")
        try:
            code, err = self.main(f.name)
        finally:
            pathlib.Path(f.name).unlink()
        self.assertEqual(code, 2)
        self.assertIn("isn't UTF-8", err)


class Errors(unittest.TestCase):
    def assertError(self, source, fragment):
        with self.assertRaises(regards.RegardsError) as ctx:
            run(source)
        self.assertIn(fragment, str(ctx.exception))

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


if __name__ == "__main__":
    unittest.main()
