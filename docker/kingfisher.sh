#!/bin/bash

# This is a wrapper for the kingfisher command that sets the PYTHONPATH to include the kingfisher directory. This is needed to run the command in the docker container, where the kingfisher directory is not in the default PYTHONPATH.
PYTHONPATH=/kingfisher:$PYTHONPATH /kingfisher/bin/kingfisher "$@"