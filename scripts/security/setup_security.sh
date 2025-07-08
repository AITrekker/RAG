#!/bin/bash
"""
Setup Security Tools for RAG Platform
Configures all security scanning and prevention tools.

Usage:
    chmod +x scripts/security/setup_security.sh
    ./scripts/security/setup_security.sh
"""

set -e

echo "🛡️  Setting up RAG Platform Security Tools..."

# Create security directory
mkdir -p scripts/security

# Make scripts executable
chmod +x scripts/security/secret_scanner.py
chmod +x scripts/security/pre_commit_security.sh

# Install pre-commit if not available
if ! command -v pre-commit &> /dev/null; then
    echo "📦 Installing pre-commit..."
    pip install pre-commit
fi

# Install pre-commit hooks
echo "🔗 Installing pre-commit hooks..."
pre-commit install

# Initialize detect-secrets baseline
echo "📊 Initializing secrets baseline..."
pip install detect-secrets
detect-secrets scan --exclude-files 'node_modules/.*' --exclude-files '\.venv/.*' --exclude-files '\.git/.*' > .secrets.baseline

# Setup ESLint security rules for frontend
echo "🔧 Setting up frontend security linting..."
cd src/frontend

# Install ESLint security plugin if not present
if ! npm list eslint-plugin-security &> /dev/null; then
    npm install --save-dev eslint-plugin-security
fi

# Create/update ESLint config with security rules
cat > .eslintrc.security.js << 'EOF'
module.exports = {
  plugins: ['security'],
  extends: ['plugin:security/recommended'],
  rules: {
    'security/detect-hardcoded-credentials': 'error',
    'security/detect-possible-timing-attacks': 'warn',
    'security/detect-eval-with-expression': 'error',
    'security/detect-non-literal-regexp': 'warn',
    'security/detect-non-literal-fs-filename': 'warn',
    'security/detect-unsafe-regex': 'error',
    'security/detect-buffer-noassert': 'error',
    'security/detect-child-process': 'warn',
    'security/detect-disable-mustache-escape': 'error',
    'security/detect-object-injection': 'warn',
    'security/detect-new-buffer': 'error',
    'security/detect-pseudoRandomBytes': 'error'
  }
};
EOF

# Add security lint script to package.json
if command -v jq &> /dev/null; then
    jq '.scripts["lint:security"] = "eslint --config .eslintrc.security.js src/**/*.{js,ts,tsx}"' package.json > package.json.tmp && mv package.json.tmp package.json
else
    echo "⚠️  Manual step required: Add 'lint:security' script to frontend/package.json"
fi

cd ../..

# Create git hooks
echo "🪝 Setting up git hooks..."
cp scripts/security/pre_commit_security.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# Setup VS Code security settings
mkdir -p .vscode
cat > .vscode/settings.json << 'EOF'
{
  "files.watcherExclude": {
    "**/.git/objects/**": true,
    "**/.git/subtree-cache/**": true,
    "**/node_modules/**": true,
    "**/.venv/**": true
  },
  "search.exclude": {
    "**/.git": true,
    "**/node_modules": true,
    "**/.venv": true,
    "**/package-lock.json": true,
    "**/yarn.lock": true
  },
  "eslint.workingDirectories": ["src/frontend"],
  "python.defaultInterpreterPath": ".venv/bin/python",
  "files.associations": {
    "*.env.example": "properties",
    "*.env.template": "properties"
  }
}
EOF

# Create security documentation
cat > SECURITY.md << 'EOF'
# Security Guidelines for RAG Platform

## 🛡️ Pre-commit Security Checks

This repository has automated security scanning to prevent secrets from being committed.

### Quick Commands

```bash
# Run security scan manually
python scripts/security/secret_scanner.py

# Scan including git history
python scripts/security/secret_scanner.py --git-history

# Run all pre-commit checks
pre-commit run --all-files

# Update security tools
./scripts/security/setup_security.sh
```

### What Gets Detected

- ✅ OpenAI API keys (`sk-...`)
- ✅ RAG Platform API keys (`tenant_admin_...`, `tenant_...`)
- ✅ Database passwords in URLs
- ✅ AWS credentials
- ✅ JWT tokens
- ✅ Private keys
- ✅ Generic API keys and secrets
- ✅ X-API-Key headers with values

### If Secrets Are Detected

1. **Remove the secret** from your code
2. **Use environment variables** instead
3. **Regenerate the secret** (assume it's compromised)
4. **Check git history** for the secret in previous commits

### Environment Variables

Always use environment variables for secrets:

```typescript
// ❌ WRONG
const API_KEY = 'tenant_admin_abc123...';

// ✅ CORRECT  
const API_KEY = process.env.VITE_API_KEY;
if (!API_KEY) throw new Error('VITE_API_KEY required');
```

### .env File Management

- ✅ Use `.env.example` for templates
- ✅ Add real `.env` files to `.gitignore`
- ❌ Never commit `.env` files
- ❌ Never commit `.env.local`, `.env.production`, etc.

### If You Need to Remove Secrets from Git History

```bash
# WARNING: This rewrites git history
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch path/to/file' \
  --prune-empty --tag-name-filter cat -- --all

git push origin --force --all
```

### Reporting Security Issues

If you find a security vulnerability, please:
1. Do NOT create a public issue
2. Email the security team directly
3. Include steps to reproduce
4. Allow time for patching before disclosure
EOF

# Test the setup
echo "🧪 Testing security setup..."
python scripts/security/secret_scanner.py --show-all

echo ""
echo "✅ Security setup complete!"
echo ""
echo "🔧 Tools installed:"
echo "   - Secret scanner with custom RAG patterns"
echo "   - Pre-commit hooks for automatic checking"
echo "   - ESLint security rules for frontend"
echo "   - Git hooks for commit-time validation"
echo ""
echo "📚 Documentation created:"
echo "   - SECURITY.md - Security guidelines"
echo "   - .pre-commit-config.yaml - Pre-commit configuration"
echo ""
echo "🚀 Next steps:"
echo "   1. Run: python scripts/security/secret_scanner.py --git-history"
echo "   2. Fix any detected secrets"
echo "   3. Commit changes and test pre-commit hooks"
echo "   4. Train team on security practices"