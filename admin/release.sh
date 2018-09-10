#!/usr/bin/env bash

set -ex

# Perform a release.
# See the release process documentation for details.
cd "$(mktemp -d)"
git clone git@github.com:"${GITHUB_OWNER}"/vws-python-mock.git
cd vws-python-mock
virtualenv -p python3 release
source release/bin/activate
pip install --editable .[dev]
python admin/release.py
