#!/usr/bin/env python3

import io
from os.path import dirname, join
import extern

def get_version(relpath):
  """Read version info from a file without importing it"""
  for line in io.open(join(dirname(__file__), relpath), encoding="cp437"):
    if "__version__" in line:
      if '"' in line:
        return line.split('"')[1]
      elif "'" in line:
        return line.split("'")[1]

if __name__ == "__main__":
    version = get_version('kingfisher/version.py')
    print("version is {}".format(version))

    # Replace version in CITATION.cff
    citations_lines = []
    with open("CITATION.cff", "r") as f:
        import re
        r = re.compile(r"( *version: )")
        r2 = re.compile(r"( *date-released: )")
        for line in f:
            if matches := r.match(line):
                line = matches.group(1) + version + "\n"
            elif matches := r2.match(line):
                from datetime import datetime
                line = matches.group(1) + datetime.today().strftime('%Y-%m-%d') + "\n"
            citations_lines.append(line)
    with open("CITATION.cff", "w") as f:
        f.writelines(citations_lines)

    print("building docs")
    extern.run("python3 build_docs.py")

    print("Checking if repo is clean ..")
    extern.run('if [[ $(git diff --shortstat 2> /dev/null | tail -n1) != "" ]]; then exit 1; fi')

    extern.run('git tag v{}'.format(version))
    print("Now run 'git push && git push --tags' and GitHub actions will build and upload to PyPI".format(version))
    print("Then make a release, adding changelog info, so Zenodo picks it up")
    print('You have to run ./build.sh from the docker directory to build the docker image, once the tag is on GitHub')

