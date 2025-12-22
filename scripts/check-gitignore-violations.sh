#!/bin/sh
# Pre-commit hook to prevent staging files that match .gitignore patterns
# Uses git ls-files -i --exclude-standard to find files matching .gitignore

# ============================================================================
# CHECK A: All tracked files (already committed) that match .gitignore
# ============================================================================
tracked_violations=$(git ls-files -c -i --exclude-standard | grep -v '\.gitkeep$')

# ============================================================================
# CHECK B: All staged files (being committed now) that match .gitignore
# ============================================================================
# Get all staged files
staged_files=$(git diff --cached --name-only)

# Check each staged file against .gitignore
staged_violations=""
for file in $staged_files; do
  # Skip .gitkeep files
  if echo "$file" | grep -q '\.gitkeep$'; then
    continue
  fi

  # Check if file matches .gitignore
  if git check-ignore -q "$file" 2>/dev/null; then
    staged_violations="${staged_violations}${file}\n"
  fi
done

# ============================================================================
# REPORT: Show violations from both checks separately
# ============================================================================
has_violations=false

if [ -n "$tracked_violations" ]; then
  echo "❌ ERROR: Already-tracked files matching .gitignore:" >&2
  echo "$tracked_violations" | while IFS= read -r file; do
    [ -n "$file" ] && echo "  - $file" >&2
  done
  echo "" >&2
  has_violations=true
fi

if [ -n "$staged_violations" ]; then
  echo "❌ ERROR: Staged files matching .gitignore:" >&2
  echo "$staged_violations" | while IFS= read -r file; do
    [ -n "$file" ] && echo "  - $file" >&2
  done
  echo "" >&2
  has_violations=true
fi

if [ "$has_violations" = true ]; then
  echo "💡 Tip: Use 'git reset HEAD <file>' to unstage, or 'git rm --cached <file>' to untrack" >&2
  exit 1
fi

exit 0
