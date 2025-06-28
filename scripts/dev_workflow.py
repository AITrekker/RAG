#!/usr/bin/env python3
"""
Development Workflow Enforcement

This script helps prevent the "fix one thing, break another" cycle
by enforcing testing and validation at each step.
"""

import subprocess
import sys
import os
from pathlib import Path

class DevWorkflow:
    """Enforces safe development practices"""
    
    def __init__(self):
        self.repo_root = Path(__file__).parent.parent
        os.chdir(self.repo_root)
    
    def run_command(self, cmd: str, description: str) -> bool:
        """Run a command and return success status"""
        print(f"[RUNNING] {description}...")
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  [OK] {description} passed")
                return True
            else:
                print(f"  [FAIL] {description} failed:")
                print(f"     {result.stderr}")
                return False
        except Exception as e:
            print(f"  [FAIL] {description} error: {e}")
            return False
    
    def pre_change_checks(self) -> bool:
        """Run before making any changes"""
        print("PRE-CHANGE VALIDATION")
        print("=" * 40)
        
        checks = [
            ("docker-compose exec backend alembic -c src/backend/migrations/alembic.ini upgrade head && docker-compose exec backend alembic -c src/backend/migrations/alembic.ini downgrade base", "Database migration check"),
            #("python scripts/health_check.py", "System health check"),
            ("python tests/quick_api_test.py", "API endpoint tests"),
            ("python -m pytest tests/test_integration_e2e.py -v", "Integration tests"),
        ]
        
        all_passed = True
        for cmd, desc in checks:
            if not self.run_command(cmd, desc):
                all_passed = False
        
        if all_passed:
            print("\n[OK] All pre-change checks passed - safe to proceed")
        else:
            print("\n[FAIL] Pre-change checks failed - fix issues before proceeding")
        
        return all_passed
    
    def post_change_checks(self) -> bool:
        """Run after making changes"""
        print("\nPOST-CHANGE VALIDATION")
        print("=" * 40)
        
        checks = [
            #("python scripts/health_check.py", "System health check"),
            ("python tests/quick_api_test.py", "API endpoint tests"),
            ("python scripts/explore_data.py 'test query'", "Search functionality"),
        ]
        
        all_passed = True
        for cmd, desc in checks:
            if not self.run_command(cmd, desc):
                all_passed = False
        
        if all_passed:
            print("\n[OK] All post-change checks passed - changes are safe")
        else:
            print("\n[FAIL] Post-change checks failed - rollback recommended")
        
        return all_passed
    
    def safe_refactor_mode(self):
        """Interactive mode for safe refactoring"""
        print("SAFE REFACTORING MODE")
        print("=" * 40)
        print("This mode helps prevent the 'fix one, break another' cycle")
        print()
        
        # Pre-change validation
        if not self.pre_change_checks():
            print("\n[FAIL] System is not in a good state for changes")
            print("   Fix existing issues before refactoring")
            return False
        
        print("\n[OK] System validated - safe to make changes")
        print()
        print("RECOMMENDED CHANGE PROCESS:")
        print("1. Make ONE focused change at a time")
        print("2. Test that specific change immediately")
        print("3. Run post-change validation")
        print("4. Commit changes if all tests pass")
        print("5. Repeat for next change")
        print()
        
        while True:
            response = input("Press Enter when you've made your changes (or 'q' to quit): ")
            if response.lower() == 'q':
                break
            
            if self.post_change_checks():
                print("\n[SUCCESS] Changes validated successfully!")
                commit = input("Commit changes? (y/n): ")
                if commit.lower() == 'y':
                    commit_msg = input("Commit message: ")
                    self.run_command(f'git add -A && git commit -m "{commit_msg}"', "Git commit")
            else:
                print("\n[WARNING] Changes broke something!")
                rollback = input("Rollback changes? (y/n): ")
                if rollback.lower() == 'y':
                    self.run_command("git checkout .", "Rollback changes")
                    print("Changes rolled back")
        
        return True

def main():
    """Main workflow entry point"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/dev_workflow.py pre    # Run pre-change checks")
        print("  python scripts/dev_workflow.py post   # Run post-change checks")
        print("  python scripts/dev_workflow.py safe   # Safe refactoring mode")
        return
    
    workflow = DevWorkflow()
    command = sys.argv[1]
    
    if command == "pre":
        workflow.pre_change_checks()
    elif command == "post":
        workflow.post_change_checks()
    elif command == "safe":
        workflow.safe_refactor_mode()
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main() 