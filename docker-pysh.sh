#!/bin/sh
#
# Runs pysh from a docker image mounting the current working directory
#

docker run -it --rm -v $PWD:/pwd drslump80/pysh "$@"

