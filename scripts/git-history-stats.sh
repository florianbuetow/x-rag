#!/usr/bin/env bash
# Git History Statistics
# Computes and displays repository statistics from git history

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'  # No Color

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Not a git repository${NC}"
    exit 1
fi

# Get repository root
REPO_ROOT=$(git rev-parse --show-toplevel)

echo -e "${CYAN}Repository:${NC} $(basename "$REPO_ROOT")"
echo ""

# === Commit Statistics ===
echo -e "${YELLOW}Commit Statistics:${NC}"
TOTAL_COMMITS=$(git rev-list --count HEAD 2>/dev/null || echo "0")
echo -e "  Total commits:        ${GREEN}$TOTAL_COMMITS${NC}"

FIRST_COMMIT_HASH=$(git rev-list --max-parents=0 HEAD)
FIRST_COMMIT_DATE=$(git log -1 --format="%ai" "$FIRST_COMMIT_HASH" | cut -d ' ' -f 1)
LAST_COMMIT_DATE=$(git log -1 --format="%ai" | cut -d ' ' -f 1)
echo -e "  First commit:         $FIRST_COMMIT_DATE"
echo -e "  Last commit:          $LAST_COMMIT_DATE"

# Calculate days between first and last commit
if command -v gdate > /dev/null 2>&1; then
    # Use GNU date if available (via brew install coreutils on macOS)
    DAYS_ACTIVE=$(( ($(gdate -d "$LAST_COMMIT_DATE" +%s) - $(gdate -d "$FIRST_COMMIT_DATE" +%s)) / 86400 ))
elif date --version 2>&1 | grep -q "GNU"; then
    # GNU date (Linux)
    DAYS_ACTIVE=$(( ($(date -d "$LAST_COMMIT_DATE" +%s) - $(date -d "$FIRST_COMMIT_DATE" +%s)) / 86400 ))
else
    # BSD date (macOS default)
    DAYS_ACTIVE=$(( ($(date -j -f "%Y-%m-%d" "$LAST_COMMIT_DATE" +%s) - $(date -j -f "%Y-%m-%d" "$FIRST_COMMIT_DATE" +%s)) / 86400 ))
fi
echo -e "  Days active:          $DAYS_ACTIVE days"

# Commits per day (average)
if [ "$DAYS_ACTIVE" -gt 0 ]; then
    AVG_COMMITS_PER_DAY=$(echo "scale=2; $TOTAL_COMMITS / $DAYS_ACTIVE" | bc)
    echo -e "  Avg commits/day:      $AVG_COMMITS_PER_DAY"
fi

echo ""

# === Code Change Statistics ===
echo -e "${YELLOW}Code Change Statistics:${NC}"
# Get insertions and deletions
STATS=$(git log --pretty=tformat: --numstat --all | awk '
{
    insertions += $1
    deletions += $2
}
END {
    print insertions " " deletions
}')
INSERTIONS=$(echo "$STATS" | awk '{print $1}')
DELETIONS=$(echo "$STATS" | awk '{print $2}')
NET_LINES=$((INSERTIONS - DELETIONS))

echo -e "  Total insertions:     ${GREEN}+$INSERTIONS${NC}"
echo -e "  Total deletions:      ${RED}-$DELETIONS${NC}"
if [ "$NET_LINES" -ge 0 ]; then
    echo -e "  Net lines:            ${GREEN}+$NET_LINES${NC}"
else
    echo -e "  Net lines:            ${RED}$NET_LINES${NC}"
fi

# Total files changed
TOTAL_FILES_CHANGED=$(git log --pretty=format: --name-only --all | sort -u | grep -v '^$' | wc -l | tr -d ' ')
echo -e "  Files changed:        $TOTAL_FILES_CHANGED"

echo ""

# === Contributor Statistics ===
echo -e "${YELLOW}Contributor Statistics:${NC}"
TOTAL_CONTRIBUTORS=$(git log --format="%aN" | sort -u | wc -l | tr -d ' ')
echo -e "  Total contributors:   $TOTAL_CONTRIBUTORS"
echo ""

# Top 10 contributors by commit count
echo -e "${YELLOW}Top Contributors (by commits):${NC}"
git shortlog -sn --all | head -n 10 | awk '{
    printf "  %s%-5s %s", "'$CYAN'", $1, "'$NC'"
    $1=""
    print $0
}'
echo ""

# === Recent Activity ===
echo -e "${YELLOW}Recent Activity:${NC}"
echo -e "  Last 7 days:          $(git log --since='7 days ago' --oneline | wc -l | tr -d ' ') commits"
echo -e "  Last 30 days:         $(git log --since='30 days ago' --oneline | wc -l | tr -d ' ') commits"
echo -e "  Last 90 days:         $(git log --since='90 days ago' --oneline | wc -l | tr -d ' ') commits"
echo ""

# === Most Modified Files ===
echo -e "${YELLOW}Most Modified Files (top 10):${NC}"
git log --pretty=format: --name-only --all | \
    grep -v '^$' | \
    sort | \
    uniq -c | \
    sort -rn | \
    head -n 10 | \
    awk '{printf "  %s%-5s %s%s%s\n", "'$CYAN'", $1, "'$NC'", $2, ""}'
echo ""

# === Commit Type Distribution (if using conventional commits) ===
echo -e "${YELLOW}Commit Type Distribution:${NC}"
FEAT_COUNT=$(git log --oneline --all | grep -c "^[a-f0-9]\+ feat" || echo "0")
FIX_COUNT=$(git log --oneline --all | grep -c "^[a-f0-9]\+ fix" || echo "0")
DOCS_COUNT=$(git log --oneline --all | grep -c "^[a-f0-9]\+ docs" || echo "0")
TEST_COUNT=$(git log --oneline --all | grep -c "^[a-f0-9]\+ test" || echo "0")
REFACTOR_COUNT=$(git log --oneline --all | grep -c "^[a-f0-9]\+ refactor" || echo "0")
CHORE_COUNT=$(git log --oneline --all | grep -c "^[a-f0-9]\+ chore" || echo "0")
INFRA_COUNT=$(git log --oneline --all | grep -c "^[a-f0-9]\+ infra" || echo "0")
CI_COUNT=$(git log --oneline --all | grep -c "^[a-f0-9]\+ ci" || echo "0")

echo -e "  feat:                 $FEAT_COUNT"
echo -e "  fix:                  $FIX_COUNT"
echo -e "  docs:                 $DOCS_COUNT"
echo -e "  test:                 $TEST_COUNT"
echo -e "  refactor:             $REFACTOR_COUNT"
echo -e "  chore:                $CHORE_COUNT"
echo -e "  infra:                $INFRA_COUNT"
echo -e "  ci:                   $CI_COUNT"

OTHER_COUNT=$((TOTAL_COMMITS - FEAT_COUNT - FIX_COUNT - DOCS_COUNT - TEST_COUNT - REFACTOR_COUNT - CHORE_COUNT - INFRA_COUNT - CI_COUNT))
if [ "$OTHER_COUNT" -gt 0 ]; then
    echo -e "  other:                $OTHER_COUNT"
fi

echo ""

# === Branch Statistics ===
echo -e "${YELLOW}Branch Statistics:${NC}"
TOTAL_BRANCHES=$(git branch -a | wc -l | tr -d ' ')
LOCAL_BRANCHES=$(git branch | wc -l | tr -d ' ')
REMOTE_BRANCHES=$((TOTAL_BRANCHES - LOCAL_BRANCHES))
echo -e "  Local branches:       $LOCAL_BRANCHES"
echo -e "  Remote branches:      $REMOTE_BRANCHES"
echo -e "  Current branch:       $(git branch --show-current)"
echo ""

