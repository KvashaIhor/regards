# Contributing

Replies to this thread are welcome.

## Running things

```
python3 regards.py examples/fizzbuzz.rgrd      # run a program
python3 -m unittest discover -s tests          # run the tests
```

The interpreter is one file, `regards.py`, with no dependencies. It needs Python 3.9 or newer.

## Changing the language

- Write the test first, in `tests/test_regards.py`, and watch it fail before touching `regards.py`.
- Put every new statement in the README's statement reference. Anything bigger gets its own
  section.
- Programs written for 1.0 have to keep working. A change that would break one waits for 2.0,
  so say so in the pull request.
- Keep error messages in the voice of a corporate email.

## Adding an example

Put it in `examples/`, add a test for its output to the `Examples` class, and list it in the
README's file tree.

## Reporting a bug

Open an issue with the program, or the saved `.eml` file, and what you expected it to print. A
short thread helps, and so does the output of `python3 regards.py --version`.
