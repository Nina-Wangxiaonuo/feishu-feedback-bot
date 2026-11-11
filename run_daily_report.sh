#!/bin/sh
set -eu
cd "$(dirname "$0")"
PYTHONPATH=src /Users/jyxc-dz-0100189/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/bin/python3 -m feedback_bot.main >> bot.log 2>&1
