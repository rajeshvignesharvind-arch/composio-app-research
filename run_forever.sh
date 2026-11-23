#!/bin/bash
# resumable: re-run until all 100 per-app results exist
cd "$(dirname "$0")"
while [ "$(ls data/pass1 2>/dev/null | wc -l)" -lt 100 ]; do python3 -m agent.run --all --workers 4 >> data/run_pass1.log 2>&1; sleep 5; done
