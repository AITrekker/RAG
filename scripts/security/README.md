# Security Tools

## Secret Scanning with Gitleaks

This directory contains tools for scanning the repository for secrets and sensitive information before commits and pushes.

### Files

- **`check_secrets.py`** - Main secret scanning script using gitleaks
- **`setup_hooks.py`** - Configure git hooks for automatic scanning
- **`.gitleaks.toml`** (in project root) - Gitleaks configuration with custom rules

### Usage

#### Manual Scanning

```bash
# Scan for secrets before pushing
python scripts/security/check_secrets.py
```

#### Set Up Git Hooks

```bash
# Enable automatic pre-push secret scanning
python scripts/security/setup_hooks.py
```

#### Bypass Hooks (Emergency)

```bash
# Skip hooks for emergency pushes (use with caution!)
git push --no-verify
```

### Configuration

The scanner is configured to detect:

- **RAG Platform API Keys**: `tenant_*` and `admin_*` patterns
- **Database Connection Strings**: PostgreSQL URLs with credentials
- **Generic Secrets**: API keys, tokens, secret keys
- **High Entropy Strings**: Potential cryptographic material

### Allowlisted Items

The following are automatically allowed (configured in `.gitleaks.toml`):

- Development database credentials (`rag_user:rag_password`)
- Placeholder values (`your_*_here`, `example_*`, etc.)
- Test files and documentation
- Demo data directories

### Adding New Rules

Edit `.gitleaks.toml` in the project root:

```toml
[[rules]]
id = "custom-secret"
description = "Custom Secret Pattern"
regex = '''your-pattern-here'''
keywords = ["keyword1", "keyword2"]
```

### Troubleshooting

**False Positives**: Add patterns to the `allowlist.regexes` section in `.gitleaks.toml`

**Missing Secrets**: Add new rules or keywords to catch specific patterns

**Hook Issues**: Check that python3 is available and git hooks are enabled:
```bash
git config core.hooksPath
# Should show: .githooks
```