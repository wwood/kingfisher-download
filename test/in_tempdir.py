import os
import contextlib
from pathlib import Path
import tempfile

@contextlib.contextmanager
def in_working_directory(path):
    """Changes working directory and returns to previous on exit."""
    prev_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)

@contextlib.contextmanager
def in_tempdir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        with in_working_directory(tmpdirname):
            yield