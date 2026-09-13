import io
import pathlib
import sys
import unittest

PLAYGROUND = pathlib.Path(__file__).resolve().parent.parent
ROOT = PLAYGROUND.parent
sys.path.insert(0, str(PLAYGROUND))

from app import app  # noqa: E402


def email(*body, sign_off="Best,"):
    return "Hi team,\n\n" + "\n".join(body) + f"\n\n{sign_off}\nIhor\n"


class Playground(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, RUN_TIMEOUT=2)
        self.client = app.test_client()

    def run_program(self, source, stdin=""):
        response = self.client.post("/api/run", json={"source": source, "stdin": stdin})
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def test_page_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Does your email compile?", response.data)

    def test_runs_a_program(self):
        result = self.run_program(email('Circling back on "Hello, World".'))
        self.assertEqual((result["stdout"], result["exit_code"], result["status"]), ("Hello, World\n", 0, "sent"))

    def test_bare_regards(self):
        result = self.run_program(email('Circling back on "fine".', sign_off="Regards,"))
        self.assertEqual((result["exit_code"], result["status"]), (1, "regards"))

    def test_errors_come_back_in_character(self):
        result = self.run_program(email("Let's synergize."))
        self.assertEqual((result["exit_code"], result["status"]), (2, "error"))
        self.assertIn("isn't something I can action", result["stderr"])

    def test_warnings_come_back_too(self):
        result = self.run_program(email('Circling back on "x".') + "\nSent from my iPhone\n")
        self.assertEqual(result["status"], "sent")
        self.assertIn("autocorrect on", result["stderr"])

    def test_input_reaches_the_program(self):
        result = self.run_program(email("Just to level-set, x is 0.", "Thoughts?", "Doubling down on x.",
                                        "Circling back on x."), stdin="21\n")
        self.assertEqual(result["stdout"], "42\n")

    def test_endless_program_times_out_but_keeps_what_it_printed(self):
        result = self.run_program(email('Circling back on "started".',
                                        "Just to level-set, x is 1.",
                                        "Per my last email, while we still have x:",
                                        "> Good news — we've added another x."))
        self.assertEqual((result["status"], result["stdout"]), ("timeout", "started\n"))

    def test_output_is_capped(self):
        result = self.run_program(email("Just to level-set, x is 1.",
                                        "Per my last email, while we still have x:",
                                        '> Circling back on "spam".'))
        self.assertEqual(result["status"], "output_limit")
        self.assertTrue(result["stdout"].startswith("spam\n"))
        self.assertLessEqual(len(result["stdout"]), 100_000)

    def test_attachments_never_come_from_the_server_disk(self):
        result = self.run_program(email("Resending with the attachment: ../../../../../../etc/passwd."))
        self.assertEqual(result["status"], "error")
        self.assertIn("didn't come through", result["stderr"])
        self.assertNotIn("root", result["stdout"] + result["stderr"])

    def test_saved_email_upload(self):
        data = {"eml": (io.BytesIO((ROOT / "examples" / "budget.eml").read_bytes()), "budget.eml")}
        response = self.client.post("/api/run", data=data, content_type="multipart/form-data")
        result = response.get_json()
        self.assertEqual((result["stdout"], result["status"]), ("250\n", "sent"))

    def test_examples_are_listed_and_served(self):
        examples = {e["name"]: e for e in self.client.get("/api/examples").get_json()}
        self.assertIn("hello.rgrd", examples)
        self.assertEqual(examples["budget.eml"]["kind"], "eml")
        self.assertTrue(examples["brainfuck.rgrd"]["stdin"].endswith("!"))
        with self.client.get("/api/examples/hello.rgrd") as response:
            served = response.get_data(as_text=True)
        self.assertEqual(served, (ROOT / "examples" / "hello.rgrd").read_text(encoding="utf-8"))

    def test_unknown_or_sneaky_example_names(self):
        self.assertEqual(self.client.get("/api/examples/nope.rgrd").status_code, 404)
        self.assertEqual(self.client.get("/api/examples/..%2Fregards.py").status_code, 404)

    def test_oversized_program_is_rejected(self):
        response = self.client.post("/api/run", json={"source": "x" * 300_000})
        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
