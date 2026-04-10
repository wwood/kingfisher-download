#!/usr/bin/env python3

import extern
import re
import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please provide the version number as an argument e.g. 0.19.0")
        sys.exit(1)
    version = sys.argv[1]

    yes_no = input(
        "Did you update CHANGELOG.md?\n\n"
    )
    if yes_no != "y":
        raise Exception("Please update the CHANGELOG.md file")

    yes_no = input(
        "Have all tests been run (including flaky) using 'pixi run -e dev pytest test -m \"\"'?\n\n"
    )
    if yes_no != "y":
        raise Exception("Please run all tests first")

    print("version is {}".format(version))

    # Build dependency definition files from pixi.toml/pixi.lock
    print("Building dependency definition files based on pixi.toml and pixi.lock")
    extern.run('pixi run python3 admin/build_dep_defs_from_pixi.py')

    # Update version in pyproject.toml
    print("Updating version in pyproject.toml")
    pyproject_path = 'pyproject.toml'
    with open(pyproject_path) as f:
        pyproject_content = f.read()
    pyproject_content = re.sub(
        r'^version = ".*"',
        'version = "{}"'.format(version),
        pyproject_content,
        count=1,
        flags=re.MULTILINE,
    )
    with open(pyproject_path, 'w') as f:
        f.write(pyproject_content)

    # Update version in kingfisher/version.py
    print("Updating version in kingfisher/version.py")
    with open('kingfisher/version.py', 'w') as f:
        f.write('__version__ = "{}"\n'.format(version))

    print("building docs")
    extern.run("pixi run python3 admin/build_docs.py")

    print(
        "Checking for unexpected changes. If this fails it might be because the docs have changed from the previous command here? If so you need to remove the git tag with 'git tag -d v{}'".format(version)
    )
    extern.run("if git diff --name-only | grep -qv -e 'kingfisher/version.py' -e 'pyproject.toml' -e 'admin/'; then echo 'Unexpected changed files:'; git diff --name-only; exit 1; fi")

    print("Committing the version file")
    extern.run('git commit -a -m "v{}"'.format(version))

    print("Tagging the release as v{}".format(version))
    extern.run('git tag v{}'.format(version))

    print("Now run 'git push && git push --tags' and GitHub actions will build and upload to PyPI".format(version))
    print('You have to run "pixi run bash ./build.sh" from the docker directory to build the docker image, once the tag is on GitHub')
    print('A release also must be manually made on GitHub')
