#!/usr/bin/env python3
"""
Comprehensive Secret Scanner for RAG Platform
Catches hardcoded secrets in current files AND git history.

Usage:
    python scripts/security/secret_scanner.py
    python scripts/security/secret_scanner.py --git-history
    python scripts/security/secret_scanner.py --pre-commit
"""

import os
import re
import sys
import json
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass
from enum import Enum

class SeverityLevel(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH" 
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

@dataclass
class SecretMatch:
    file_path: str
    line_number: int
    line_content: str
    secret_type: str
    severity: SeverityLevel
    confidence: float
    git_commit: str = ""
    
    def to_dict(self):
        return {
            "file": self.file_path,
            "line": self.line_number,
            "content": self.line_content[:100] + "..." if len(self.line_content) > 100 else self.line_content,
            "type": self.secret_type,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "commit": self.git_commit
        }

class SecretScanner:
    def __init__(self):
        self.patterns = self._load_patterns()
        self.whitelist = self._load_whitelist()
        self.found_secrets: List[SecretMatch] = []
        
    def _load_patterns(self) -> Dict[str, Dict]:
        """Load secret detection patterns with confidence scores."""
        return {
            # OpenAI API Keys
            "openai_api_key": {
                "pattern": r"sk-[a-zA-Z0-9]{20}T3BlbkFJ[a-zA-Z0-9]{20}",
                "description": "OpenAI API Key",
                "severity": SeverityLevel.CRITICAL,
                "confidence": 0.95
            },
            "openai_api_key_new": {
                "pattern": r"sk-proj-[a-zA-Z0-9]{20}T3BlbkFJ[a-zA-Z0-9]{20}",
                "description": "OpenAI Project API Key", 
                "severity": SeverityLevel.CRITICAL,
                "confidence": 0.95
            },
            
            # Custom RAG Platform Keys (the one we missed!)
            "rag_tenant_key": {
                "pattern": r"tenant_[a-zA-Z0-9_]+_[a-f0-9]{32}",
                "description": "RAG Platform Tenant API Key",
                "severity": SeverityLevel.CRITICAL,
                "confidence": 0.90
            },
            "rag_admin_key": {
                "pattern": r"tenant_admin_[a-f0-9]{32}",
                "description": "RAG Platform Admin API Key",
                "severity": SeverityLevel.CRITICAL,
                "confidence": 0.95
            },
            
            # Generic API Keys
            "generic_api_key": {
                "pattern": r"api[_-]?key['\"]?\s*[:=]\s*['\"][a-zA-Z0-9_\-]{20,}['\"]",
                "description": "Generic API Key Assignment",
                "severity": SeverityLevel.HIGH,
                "confidence": 0.80
            },
            "bearer_token": {
                "pattern": r"[Bb]earer\s+[a-zA-Z0-9_\-\.]{20,}",
                "description": "Bearer Token",
                "severity": SeverityLevel.HIGH,
                "confidence": 0.75
            },
            
            # Database Passwords
            "postgres_url": {
                "pattern": r"postgresql://[^:]+:[^@]+@[^/]+/\w+",
                "description": "PostgreSQL Connection String with Password",
                "severity": SeverityLevel.HIGH,
                "confidence": 0.85
            },
            
            # AWS Keys
            "aws_access_key": {
                "pattern": r"AKIA[0-9A-Z]{16}",
                "description": "AWS Access Key ID",
                "severity": SeverityLevel.CRITICAL,
                "confidence": 0.90
            },
            "aws_secret_key": {
                "pattern": r"aws[_-]?secret[_-]?access[_-]?key['\"]?\s*[:=]\s*['\"][a-zA-Z0-9/+=]{40}['\"]",
                "description": "AWS Secret Access Key",
                "severity": SeverityLevel.CRITICAL,
                "confidence": 0.85
            },
            
            # JWT Tokens
            "jwt_token": {
                "pattern": r"eyJ[a-zA-Z0-9_\-]*\.eyJ[a-zA-Z0-9_\-]*\.[a-zA-Z0-9_\-]*",
                "description": "JWT Token",
                "severity": SeverityLevel.MEDIUM,
                "confidence": 0.80
            },
            
            # Private Keys
            "private_key": {
                "pattern": r"-----BEGIN [A-Z ]+PRIVATE KEY-----",
                "description": "Private Key",
                "severity": SeverityLevel.CRITICAL,
                "confidence": 0.95
            },
            
            # Generic Secrets
            "secret_assignment": {
                "pattern": r"secret['\"]?\s*[:=]\s*['\"][a-zA-Z0-9_\-]{10,}['\"]",
                "description": "Secret Assignment",
                "severity": SeverityLevel.MEDIUM,
                "confidence": 0.70
            },
            "password_assignment": {
                "pattern": r"password['\"]?\s*[:=]\s*['\"][^'\"]{8,}['\"]",
                "description": "Password Assignment", 
                "severity": SeverityLevel.HIGH,
                "confidence": 0.75
            },
            
            # X-API-Key Headers (the exact pattern that caught us!)
            "x_api_key_header": {
                "pattern": r"['\"]X-API-Key['\"]:\s*['\"][a-zA-Z0-9_\-]{20,}['\"]",
                "description": "X-API-Key Header with Value",
                "severity": SeverityLevel.CRITICAL,
                "confidence": 0.90
            },
            
            # GitHub Tokens
            "github_token": {
                "pattern": r"gh[ops]_[A-Za-z0-9_]{36}",
                "description": "GitHub Token",
                "severity": SeverityLevel.HIGH,
                "confidence": 0.85
            },
            
            # Slack Tokens
            "slack_token": {
                "pattern": r"xox[baprs]-[0-9]{12}-[0-9]{12}-[a-zA-Z0-9]{24}",
                "description": "Slack Token",
                "severity": SeverityLevel.MEDIUM,
                "confidence": 0.85
            }
        }
    
    def _load_whitelist(self) -> Set[str]:
        """Load patterns to ignore (false positives)."""
        return {
            # Documentation examples
            "your-api-key",
            "your_api_key", 
            "api_key_here",
            "YOUR_API_KEY",
            "sk-...",
            "sk-abc123",
            "sk-demo...",
            "tenant_api_key_here",
            "example.com",
            "localhost",
            
            # Test values
            "test_key",
            "dummy_key",
            "fake_key",
            "mock_key",
            "placeholder",
            
            # Environment variable names
            "OPENAI_API_KEY",
            "API_KEY",
            "ADMIN_API_KEY",
            "POSTGRES_PASSWORD",
        }
    
    def scan_file(self, file_path: str) -> List[SecretMatch]:
        """Scan a single file for secrets."""
        matches = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    line_matches = self._scan_line(line, file_path, line_num)
                    matches.extend(line_matches)
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            
        return matches
    
    def _scan_line(self, line: str, file_path: str, line_num: int) -> List[SecretMatch]:
        """Scan a single line for secret patterns."""
        matches = []
        
        for pattern_name, pattern_info in self.patterns.items():
            regex = re.compile(pattern_info["pattern"], re.IGNORECASE)
            
            for match in regex.finditer(line):
                matched_text = match.group(0)
                
                # Check whitelist
                if self._is_whitelisted(matched_text, line):
                    continue
                    
                # Additional validation
                confidence = self._calculate_confidence(matched_text, pattern_info, line, file_path)
                
                if confidence >= 0.5:  # Minimum confidence threshold
                    secret_match = SecretMatch(
                        file_path=file_path,
                        line_number=line_num,
                        line_content=line.strip(),
                        secret_type=pattern_info["description"],
                        severity=pattern_info["severity"],
                        confidence=confidence
                    )
                    matches.append(secret_match)
        
        return matches
    
    def _is_whitelisted(self, matched_text: str, line: str) -> bool:
        """Check if the match should be ignored."""
        # Direct whitelist match
        if matched_text.lower() in [w.lower() for w in self.whitelist]:
            return True
            
        # File path indicators
        if any(indicator in line.lower() for indicator in [
            'example', 'demo', 'test', 'mock', 'placeholder', 'template',
            'your_key', 'api_key_here', 'replace_with'
        ]):
            return True
            
        # Environment variable assignments (these are OK)
        if re.match(r'^\s*[A-Z_]+\s*=\s*', line):
            return True
            
        # Comments
        if line.strip().startswith('#') or line.strip().startswith('//'):
            return True
            
        return False
    
    def _calculate_confidence(self, matched_text: str, pattern_info: Dict, line: str, file_path: str) -> float:
        """Calculate confidence score for a match."""
        base_confidence = pattern_info["confidence"]
        
        # Boost confidence for suspicious contexts
        if any(keyword in line.lower() for keyword in ['api_key', 'secret', 'token', 'password']):
            base_confidence += 0.1
            
        # Reduce confidence for documentation files
        if file_path.endswith(('.md', '.txt', '.rst')):
            base_confidence -= 0.2
            
        # Reduce confidence for test files
        if 'test' in file_path.lower() or 'spec' in file_path.lower():
            base_confidence -= 0.15
            
        # Boost confidence for actual secret assignment patterns
        if '=' in line or ':' in line:
            base_confidence += 0.05
            
        return min(1.0, max(0.0, base_confidence))
    
    def scan_git_history(self, max_commits: int = 100) -> List[SecretMatch]:
        """Scan git history for secrets."""
        print(f"🔍 Scanning git history (last {max_commits} commits)...")
        matches = []
        
        try:
            # Get recent commits
            result = subprocess.run(
                ['git', 'log', '--oneline', f'-{max_commits}'],
                capture_output=True, text=True, check=True
            )
            
            commits = [line.split(' ', 1)[0] for line in result.stdout.strip().split('\n') if line]
            
            for commit in commits:
                commit_matches = self._scan_commit(commit)
                matches.extend(commit_matches)
                
        except subprocess.CalledProcessError as e:
            print(f"Warning: Could not scan git history: {e}")
            
        return matches
    
    def _scan_commit(self, commit_hash: str) -> List[SecretMatch]:
        """Scan a specific git commit for secrets."""
        matches = []
        
        try:
            # Get commit diff
            result = subprocess.run(
                ['git', 'show', commit_hash],
                capture_output=True, text=True, check=True
            )
            
            lines = result.stdout.split('\n')
            current_file = ""
            line_num = 0
            
            for line in lines:
                # Track current file
                if line.startswith('+++'):
                    current_file = line[6:] if line.startswith('+++ b/') else line[4:]
                    line_num = 0
                elif line.startswith('@@'):
                    # Extract line number from diff header
                    match = re.search(r'\+(\d+)', line)
                    line_num = int(match.group(1)) if match else 0
                elif line.startswith('+') and not line.startswith('+++'):
                    # This is an added line
                    line_num += 1
                    added_content = line[1:]  # Remove the '+' prefix
                    
                    line_matches = self._scan_line(added_content, current_file, line_num)
                    for match in line_matches:
                        match.git_commit = commit_hash
                        matches.append(match)
                        
        except subprocess.CalledProcessError:
            pass  # Skip problematic commits
            
        return matches
    
    def scan_current_files(self) -> List[SecretMatch]:
        """Scan all current files in the repository."""
        print("🔍 Scanning current files...")
        matches = []
        
        # Get git-tracked files
        try:
            result = subprocess.run(
                ['git', 'ls-files'],
                capture_output=True, text=True, check=True
            )
            files = result.stdout.strip().split('\n')
        except subprocess.CalledProcessError:
            # Fallback to all files if not in git repo
            files = []
            for root, dirs, filenames in os.walk('.'):
                # Skip common ignore directories
                dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', '.venv', '__pycache__'}]
                for filename in filenames:
                    files.append(os.path.join(root, filename))
        
        # Filter to relevant file types
        relevant_extensions = {
            '.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.yaml', '.yml',
            '.env', '.config', '.conf', '.ini', '.txt', '.md', '.sh', '.sql'
        }
        
        for file_path in files:
            if not file_path:
                continue
                
            # Check extension
            if not any(file_path.endswith(ext) for ext in relevant_extensions):
                continue
                
            # Skip certain directories
            if any(ignore in file_path for ignore in ['node_modules', '.git', '.venv', '__pycache__']):
                continue
                
            file_matches = self.scan_file(file_path)
            matches.extend(file_matches)
        
        return matches
    
    def run_scan(self, include_git_history: bool = False, max_commits: int = 100) -> List[SecretMatch]:
        """Run complete security scan."""
        print("🛡️  Starting comprehensive secret scan...")
        all_matches = []
        
        # Scan current files
        current_matches = self.scan_current_files()
        all_matches.extend(current_matches)
        
        # Scan git history if requested
        if include_git_history:
            history_matches = self.scan_git_history(max_commits)
            all_matches.extend(history_matches)
        
        # Remove duplicates and sort by severity
        unique_matches = self._deduplicate_matches(all_matches)
        unique_matches.sort(key=lambda x: (x.severity.value, -x.confidence))
        
        self.found_secrets = unique_matches
        return unique_matches
    
    def _deduplicate_matches(self, matches: List[SecretMatch]) -> List[SecretMatch]:
        """Remove duplicate matches."""
        seen = set()
        unique = []
        
        for match in matches:
            # Create a key for deduplication
            key = (match.file_path, match.line_number, match.secret_type)
            if key not in seen:
                seen.add(key)
                unique.append(match)
                
        return unique
    
    def print_results(self, show_all: bool = False):
        """Print scan results in a readable format."""
        if not self.found_secrets:
            print("✅ No secrets detected!")
            return
            
        print(f"\n🚨 Found {len(self.found_secrets)} potential secrets:")
        print("=" * 80)
        
        critical_count = sum(1 for s in self.found_secrets if s.severity == SeverityLevel.CRITICAL)
        high_count = sum(1 for s in self.found_secrets if s.severity == SeverityLevel.HIGH)
        
        if critical_count > 0:
            print(f"🔥 CRITICAL: {critical_count} secrets found")
        if high_count > 0:
            print(f"⚠️  HIGH: {high_count} secrets found")
        
        print()
        
        for secret in self.found_secrets:
            if not show_all and secret.severity in [SeverityLevel.LOW, SeverityLevel.INFO]:
                continue
                
            severity_emoji = {
                SeverityLevel.CRITICAL: "🔥",
                SeverityLevel.HIGH: "⚠️",
                SeverityLevel.MEDIUM: "⚡",
                SeverityLevel.LOW: "ℹ️",
                SeverityLevel.INFO: "📝"
            }
            
            print(f"{severity_emoji[secret.severity]} {secret.severity.value} - {secret.secret_type}")
            print(f"   📁 File: {secret.file_path}:{secret.line_number}")
            if secret.git_commit:
                print(f"   📝 Commit: {secret.git_commit}")
            print(f"   🎯 Confidence: {secret.confidence:.0%}")
            print(f"   📄 Content: {secret.line_content[:100]}{'...' if len(secret.line_content) > 100 else ''}")
            print()
    
    def generate_report(self, output_file: str = "security_report.json"):
        """Generate a JSON report of findings."""
        report = {
            "scan_timestamp": subprocess.run(['date', '-u'], capture_output=True, text=True).stdout.strip(),
            "total_secrets": len(self.found_secrets),
            "critical_count": sum(1 for s in self.found_secrets if s.severity == SeverityLevel.CRITICAL),
            "high_count": sum(1 for s in self.found_secrets if s.severity == SeverityLevel.HIGH),
            "secrets": [s.to_dict() for s in self.found_secrets]
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"📊 Report saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Comprehensive Secret Scanner for RAG Platform")
    parser.add_argument('--git-history', action='store_true', help='Scan git history for secrets')
    parser.add_argument('--max-commits', type=int, default=100, help='Max commits to scan in history')
    parser.add_argument('--pre-commit', action='store_true', help='Run as pre-commit hook (exit 1 if secrets found)')
    parser.add_argument('--report', type=str, help='Generate JSON report to file')
    parser.add_argument('--show-all', action='store_true', help='Show all findings including low severity')
    
    args = parser.parse_args()
    
    scanner = SecretScanner()
    secrets = scanner.run_scan(
        include_git_history=args.git_history,
        max_commits=args.max_commits
    )
    
    scanner.print_results(show_all=args.show_all)
    
    if args.report:
        scanner.generate_report(args.report)
    
    # Exit with error code for pre-commit hooks
    critical_or_high = [s for s in secrets if s.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]]
    
    if args.pre_commit and critical_or_high:
        print(f"\n❌ Pre-commit check FAILED: {len(critical_or_high)} high-severity secrets found")
        sys.exit(1)
    elif critical_or_high:
        print(f"\n⚠️  WARNING: {len(critical_or_high)} high-severity secrets found")
        sys.exit(1)
    else:
        print("\n✅ Pre-commit check PASSED: No high-severity secrets detected")
        sys.exit(0)

if __name__ == "__main__":
    main()