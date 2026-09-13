"""Runs one Regards program in a throwaway process, then exits with a status code.

The parent sends {"source" or "eml", "stdin"} as JSON on standard input. The program's own
output goes to standard output as it happens, so a program that times out still shows what it
printed. Warnings and errors go to standard error.
"""

import base64
import io
import json
import sys
import traceback

import regards

OUTPUT_LIMIT = 100_000
EXIT_OUTPUT_LIMIT = 4
MEMORY_LIMIT = 1024 * 1024 * 1024
# Reply-all threads reserve their stack up front, which would not fit under the memory limit.
REPLY_STACK_SIZE = 32 * 1024 * 1024


class OutputLimit(Exception):
    pass


class CappedOutput:
    def __init__(self, stream, limit):
        self.stream = stream
        self.left = limit

    def write(self, text):
        if len(text) > self.left:
            self.stream.write(text[:self.left])
            self.stream.flush()
            self.left = 0
            raise OutputLimit()
        self.left -= len(text)
        self.stream.write(text)
        self.stream.flush()
        return len(text)

    def flush(self):
        self.stream.flush()


def limit_memory():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT, MEMORY_LIMIT))
    except (ImportError, ValueError, OSError):
        pass  # not every platform lets a process cap its own address space


def attachments_only_from_the_email():
    """On a shared server, `Resending with the attachment:` must never read the server's own files."""
    original = regards.Interpreter.attach

    def attach(self, name, line):
        if name not in self.attachments:
            regards.fail(line, f"the attachment `{name}` didn't come through. Can you resend?")
        return original(self, name, line)

    regards.Interpreter.attach = attach


def main():
    request = json.load(sys.stdin)
    limit_memory()
    attachments_only_from_the_email()
    regards.THREAD_STACK_SIZE = REPLY_STACK_SIZE
    stdout = CappedOutput(sys.stdout, OUTPUT_LIMIT)
    try:
        if request.get("eml"):
            source, attachments = regards.load_eml(base64.b64decode(request["eml"]))
        else:
            source, attachments = request.get("source", ""), {}
        return regards.run(source, stdin=io.StringIO(request.get("stdin", "")), stdout=stdout,
                           attachments=attachments)
    except regards.RegardsError as e:
        print(e, file=sys.stderr)
        return 2
    except OutputLimit:
        return EXIT_OUTPUT_LIMIT
    except Exception:
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    sys.exit(main())
