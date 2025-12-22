#!/bin/sh

if git diff --cached --name-only | grep -q '^\.env'; then
    echo "Error: .env files cannot be committed! Add them to .gitignore." >&2
    exit 1
fi
exit 0
