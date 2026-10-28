#!/usr/bin/env bash
# Apply branch protection to main (repo admin only). Verify: gh api repos/$REPO/branches/main/protection
set -euo pipefail
REPO="${REPO:-paruff/Media-Refinery}"
# enforce_admins=false so the sole maintainer is not locked out of their own repo.
gh api -X PUT "repos/$REPO/branches/main/protection" --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Lint, format, types, security hooks",
      "Tests (py3.14, real ffmpeg)",
      "Docker image builds"
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1
  },
  "restrictions": null
}
JSON
