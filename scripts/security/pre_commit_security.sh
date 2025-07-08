#!/bin/bash
"""
Pre-commit Security Hook for RAG Platform
Prevents commits containing secrets from reaching GitHub.

Installation:
    chmod +x scripts/security/pre_commit_security.sh
    cp scripts/security/pre_commit_security.sh .git/hooks/pre-commit

Or use with pre-commit framework:
    pip install pre-commit
    pre-commit install
"""

set -e

echo "🛡️  Running pre-commit security checks..."

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Not in a git repository"
    exit 1
fi

# Run the secret scanner
python3 scripts/security/secret_scanner.py --pre-commit

# Additional security checks
echo "🔍 Running additional security validations..."

# Check for environment file leaks
if git diff --cached --name-only | grep -E "\\.env$|\\.env\\." | grep -v "\\.env\\.example$"; then
    echo "❌ BLOCKED: Attempting to commit .env files"
    echo "   Use .env.example for templates instead"
    exit 1
fi

# Check for large files that might contain secrets
git diff --cached --name-only | while read file; do
    if [ -f "$file" ] && [ $(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo 0) -gt 1048576 ]; then
        echo "⚠️  WARNING: Large file detected: $file (>1MB)"
        echo "   Review for embedded secrets or binary data"
    fi
done

# Check for common secret file patterns
DANGEROUS_FILES=$(git diff --cached --name-only | grep -E "(keys?|secrets?|credentials?|tokens?)\\.(json|txt|csv)$" || true)
if [ ! -z "$DANGEROUS_FILES" ]; then
    echo "❌ BLOCKED: Suspicious filename detected:"
    echo "$DANGEROUS_FILES"
    echo "   These filenames commonly contain secrets"
    exit 1
fi

# Check for database dumps
DB_DUMPS=$(git diff --cached --name-only | grep -E "\\.(sql|dump|backup)$" || true)
if [ ! -z "$DB_DUMPS" ]; then
    echo "⚠️  WARNING: Database file detected:"
    echo "$DB_DUMPS"
    echo "   Ensure no production data or credentials are included"
fi

echo "✅ Pre-commit security checks passed!"
exit 0