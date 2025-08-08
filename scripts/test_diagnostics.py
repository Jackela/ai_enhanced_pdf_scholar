#!/usr/bin/env python3
"""
AI Enhanced PDF Scholar - Test Diagnostics Utility

Diagnoses common pytest configuration and discovery issues.
"""

import sys
import subprocess
from pathlib import Path
import os
import importlib.util


class TestDiagnostics:
    """Test diagnostics and repair utility."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.tests_dir = self.project_root / "tests"
        self.src_dir = self.project_root / "src"
        self.issues_found = []
        self.recommendations = []
    
    def check_directory_structure(self):
        """Check if all required directories and files exist."""
        print("🔍 Checking directory structure...")
        
        # Check main directories
        required_dirs = ["tests", "src"]
        for dir_name in required_dirs:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                self.issues_found.append(f"Missing directory: {dir_path}")
            else:
                print(f"✅ {dir_name} directory exists")
        
        # Check for __init__.py files in test directories
        test_subdirs = [
            self.tests_dir,
            self.tests_dir / "unit",
            self.tests_dir / "integration", 
            self.tests_dir / "repositories",
            self.tests_dir / "services"
        ]
        
        for test_dir in test_subdirs:
            if test_dir.exists():
                init_file = test_dir / "__init__.py"
                if not init_file.exists():
                    self.issues_found.append(f"Missing {init_file}")
                    self.recommendations.append(f"Create {init_file} with empty content")
                else:
                    print(f"✅ {init_file} exists")
    
    def check_pytest_config(self):
        """Check pytest configuration."""
        print("\n🔍 Checking pytest configuration...")
        
        pytest_ini = self.project_root / "pytest.ini"
        if not pytest_ini.exists():
            self.issues_found.append("Missing pytest.ini configuration file")
            self.recommendations.append("Create pytest.ini with proper test paths")
        else:
            print("✅ pytest.ini exists")
            
            # Check content
            with open(pytest_ini, 'r', encoding='utf-8') as f:
                content = f.read()
                
                if "testpaths" not in content:
                    self.issues_found.append("pytest.ini missing 'testpaths' configuration")
                
                if "python_files" not in content:
                    self.issues_found.append("pytest.ini missing 'python_files' configuration")
                
                print("✅ pytest.ini contains required configurations")
    
    def check_python_path(self):
        """Check if Python can find the source modules."""
        print("\n🔍 Checking Python import paths...")
        
        # Check if src is in Python path
        try:
            import src
            print("✅ src package is importable")
        except ImportError as e:
            self.issues_found.append(f"Cannot import src package: {e}")
            self.recommendations.append("Add src to Python path or install in development mode")
    
    def check_test_discovery(self):
        """Check pytest test discovery."""
        print("\n🔍 Checking test discovery...")
        
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "--collect-only", "-q"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                test_count = len([line for line in lines if line.endswith(' PASSED') or '::' in line])
                print(f"✅ Discovered {test_count} tests")
                
                if test_count == 0:
                    self.issues_found.append("No tests discovered by pytest")
                    self.recommendations.append("Check test file naming patterns")
            else:
                self.issues_found.append(f"Test discovery failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self.issues_found.append("Test discovery timed out")
        except Exception as e:
            self.issues_found.append(f"Error running test discovery: {e}")
    
    def check_dependencies(self):
        """Check if required test dependencies are available."""
        print("\n🔍 Checking test dependencies...")
        
        required_packages = [
            "pytest", "pytest-cov", "pytest-xdist", "pytest-asyncio",
            "pytest-mock", "pytest-benchmark"
        ]
        
        for package in required_packages:
            try:
                importlib.util.find_spec(package.replace("-", "_"))
                print(f"✅ {package} is available")
            except ImportError:
                self.issues_found.append(f"Missing package: {package}")
                self.recommendations.append(f"Install {package}: pip install {package}")
    
    def check_test_file_patterns(self):
        """Check if test files follow naming conventions."""
        print("\n🔍 Checking test file naming patterns...")
        
        test_files = list(self.tests_dir.rglob("*.py"))
        test_files = [f for f in test_files if f.name != "__init__.py"]
        
        valid_patterns = ["test_*.py", "*_test.py"]
        invalid_files = []
        
        for test_file in test_files:
            name = test_file.name
            if not (name.startswith("test_") or name.endswith("_test.py")):
                invalid_files.append(test_file)
        
        if invalid_files:
            self.issues_found.append("Test files not following naming convention")
            for f in invalid_files:
                print(f"⚠️  {f} doesn't match test_*.py pattern")
        else:
            print(f"✅ All {len(test_files)} test files follow naming conventions")
    
    def run_sample_test(self):
        """Run a simple test to verify the setup works."""
        print("\n🔍 Running sample test...")
        
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "tests/test_database_connection.py", "-v", "--no-cov", "--maxfail=1"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                print("✅ Sample test passed successfully")
            else:
                self.issues_found.append(f"Sample test failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self.issues_found.append("Sample test timed out")
        except Exception as e:
            self.issues_found.append(f"Error running sample test: {e}")
    
    def generate_recommendations(self):
        """Generate repair recommendations."""
        if not self.issues_found and not self.recommendations:
            print("\n✅ All diagnostics passed! Your test setup looks good.")
            return
        
        print("\n" + "="*60)
        print("🔧 ISSUES FOUND AND RECOMMENDATIONS")
        print("="*60)
        
        if self.issues_found:
            print("\n❌ Issues Found:")
            for i, issue in enumerate(self.issues_found, 1):
                print(f"  {i}. {issue}")
        
        if self.recommendations:
            print("\n💡 Recommendations:")
            for i, rec in enumerate(self.recommendations, 1):
                print(f"  {i}. {rec}")
        
        print("\n🚀 Quick Fix Commands:")
        print("  # Create missing __init__.py files")
        print("  touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py")
        print("")
        print("  # Run tests without coverage for faster execution")
        print("  python scripts/test_runner.py --quick")
        print("")
        print("  # Run specific test file")
        print("  python scripts/test_runner.py --file tests/test_database_connection.py")
        print("")
        print("  # Install missing dependencies")
        print("  pip install pytest pytest-cov pytest-xdist pytest-asyncio pytest-mock")
    
    def run_full_diagnostics(self):
        """Run all diagnostic checks."""
        print("🏥 AI Enhanced PDF Scholar - Test Diagnostics")
        print("="*60)
        
        self.check_directory_structure()
        self.check_pytest_config()
        self.check_python_path()
        self.check_dependencies()
        self.check_test_file_patterns()
        self.check_test_discovery()
        self.run_sample_test()
        self.generate_recommendations()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Diagnose pytest configuration and test discovery issues"
    )
    parser.add_argument("--fix", action="store_true", 
                       help="Attempt to auto-fix common issues")
    
    args = parser.parse_args()
    
    diagnostics = TestDiagnostics()
    diagnostics.run_full_diagnostics()
    
    # Auto-fix if requested
    if args.fix:
        print("\n🔧 Attempting to auto-fix issues...")
        
        # Create missing __init__.py files
        init_files = [
            diagnostics.tests_dir / "__init__.py",
            diagnostics.tests_dir / "unit" / "__init__.py",
            diagnostics.tests_dir / "integration" / "__init__.py",
            diagnostics.tests_dir / "repositories" / "__init__.py",
            diagnostics.tests_dir / "services" / "__init__.py"
        ]
        
        for init_file in init_files:
            if init_file.parent.exists() and not init_file.exists():
                init_file.touch()
                print(f"✅ Created {init_file}")
        
        print("🔧 Auto-fix completed. Run diagnostics again to verify.")


if __name__ == "__main__":
    main()