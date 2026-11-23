#!/bin/bash
cd "$(dirname "$0")"
while [ "$(ls data/pass2 2>/dev/null | wc -l)" -lt 100 ]; do python3 -m agent.run --all --pass2 --workers 6 >> data/run_pass2.log 2>&1; sleep 5; done
