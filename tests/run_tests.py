#!/usr/bin/env python3
"""
Test runner for Knowledge Map Tool
"""
import subprocess
import sys
import argparse
from pathlib import Path

def run_unit_tests():
    """Run unit tests"""
    print("🧪 Running unit tests...")
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/unit/", 
        "-v", 
        "--tb=short"
    ], cwd=Path(__file__).parent.parent)
    return result.returncode == 0

def run_integration_tests():
    """Run integration tests"""
    print("🔗 Running integration tests...")
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/integration/", 
        "-v", 
        "--tb=short"
    ], cwd=Path(__file__).parent.parent)
    return result.returncode == 0

def run_load_tests():
    """Run load tests"""
    print("⚡ Running load tests...")
    result = subprocess.run([
        sys.executable, 
        "tests/load/test_server_load.py"
    ], cwd=Path(__file__).parent.parent)
    return result.returncode == 0

def run_all_tests():
    """Run all tests"""
    print("🚀 Running all tests...")
    success = True
    
    success &= run_unit_tests()
    success &= run_integration_tests()
    success &= run_load_tests()
    
    if success:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    
    return success

def main():
    parser = argparse.ArgumentParser(description="Run Knowledge Map Tool tests")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--load", action="store_true", help="Run load tests only")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    
    args = parser.parse_args()
    
    if args.unit:
        success = run_unit_tests()
    elif args.integration:
        success = run_integration_tests()
    elif args.load:
        success = run_load_tests()
    elif args.all:
        success = run_all_tests()
    else:
        # Default: run unit tests
        success = run_unit_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
