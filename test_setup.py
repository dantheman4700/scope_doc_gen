"""Test script to verify setup is complete and working."""

import sys
from pathlib import Path

def test_setup():
    """Run setup verification tests."""
    print("="*60)
    print("SCOPE DOCUMENT GENERATOR - Setup Verification")
    print("="*60)
    print()
    
    issues = []
    warnings = []
    
    # Test 1: Python version
    print("[*] Checking Python version...")
    if sys.version_info < (3, 8):
        issues.append("Python 3.8 or higher required")
    else:
        print(f"  Python {sys.version_info.major}.{sys.version_info.minor} [OK]")
    
    # Test 2: Required packages
    print("\n[*] Checking required packages...")
    required_packages = ['anthropic', 'PyPDF2', 'dotenv', 'jinja2', 'pydantic']
    
    for package in required_packages:
        try:
            __import__(package if package != 'dotenv' else 'dotenv')
            print(f"  {package} [OK]")
        except ImportError:
            issues.append(f"Package '{package}' not installed")
    
    # Test 3: Environment file
    print("\n[*] Checking .env file...")
    env_path = Path(".env")
    if not env_path.exists():
        warnings.append(".env file not found (run create_env.py)")
        print("  .env file: [WARN] Not found")
    else:
        print("  .env file: [OK]")
        
        # Check if API key is set
        try:
            from dotenv import load_dotenv
            import os
            load_dotenv()
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                warnings.append("ANTHROPIC_API_KEY not set in .env")
                print("  API key: [WARN] Not set")
            elif api_key == "your_api_key_here":
                warnings.append("ANTHROPIC_API_KEY is still placeholder")
                print("  API key: [WARN] Placeholder value")
            else:
                print("  API key: [OK] Set")
        except:
            pass
    
    # Test 4: Required directories
    print("\n[*] Checking directories...")
    required_dirs = ['input_docs', 'generated_scopes', 'scope_doc_gen']
    
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            issues.append(f"Directory '{dir_name}' not found")
            print(f"  {dir_name}/: [FAIL]")
        else:
            print(f"  {dir_name}/: [OK]")
    
    # Test 5: Required files
    print("\n[*] Checking required files...")
    required_files = [
        'template_scope.md',
        'temp_var_schema.json',
        'variables.json',
        'scope_doc_gen/config.py',
        'scope_doc_gen/ingest.py',
        'scope_doc_gen/llm.py',
        'scope_doc_gen/renderer.py',
        'scope_doc_gen/main.py'
    ]
    
    for file_name in required_files:
        file_path = Path(file_name)
        if not file_path.exists():
            issues.append(f"File '{file_name}' not found")
            print(f"  {file_name}: [FAIL]")
        else:
            print(f"  {file_name}: [OK]")
    
    # Test 6: Check if input_docs has files
    print("\n[*] Checking input documents...")
    input_docs = Path("input_docs")
    doc_count = len([f for f in input_docs.iterdir() if f.is_file() and f.suffix in ['.pdf', '.txt', '.md']])
    if doc_count == 0:
        warnings.append("No documents in input_docs/ folder")
        print(f"  Documents: [WARN] None found")
    else:
        print(f"  Documents: [OK] {doc_count} found")
    
    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if not issues and not warnings:
        print("\n[SUCCESS] All checks passed! You're ready to generate scope documents.")
        print("\nTo get started:")
        print("  python -m scope_doc_gen.main")
    else:
        if issues:
            print("\n[ISSUES FOUND]")
            for issue in issues:
                print(f"  - {issue}")
            print("\nPlease fix these issues before running the generator.")
            print("Run: pip install -r requirements.txt")
        
        if warnings:
            print("\n[WARNINGS]")
            for warning in warnings:
                print(f"  - {warning}")
            
            if ".env" in str(warnings):
                print("\nTo set up your API key:")
                print("  python create_env.py")
            
            if "input_docs" in str(warnings):
                print("\nAdd documents to input_docs/ folder to start generating.")
    
    print()

if __name__ == "__main__":
    test_setup()

