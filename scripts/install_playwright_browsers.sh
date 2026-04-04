#!/usr/bin/env bash
set -e
playwright install chromium
playwright install-deps chromium
echo "Playwright Chromium installed."
