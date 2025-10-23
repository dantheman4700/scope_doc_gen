"""
Quick Start Script for Scope Document Generator

This script guides you through the entire setup and first run.
"""

import sys
import subprocess
from pathlib import Path


def print_header(text):
    """Print a formatted header."""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")


def print_step(number, text):
    """Print a step number."""
    print(f"\n{'─'*70}")
    print(f"  STEP {number}: {text}")
    print('─'*70 + "\n")


def check_python():
    """Check Python version."""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required!")
        print(f"   Current version: {sys.version_info.major}.{sys.version_info.minor}")
        return False
    print(f"[OK] Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True


def install_dependencies():
    """Install required packages."""
    print("Installing dependencies...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"
        ])
        print("[OK] Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        print("   Try manually: pip install -r requirements.txt")
        return False


def setup_api_key():
    """Guide user through API key setup."""
    env_path = Path(".env")
    
    if env_path.exists():
        with open(env_path, 'r') as f:
            content = f.read()
            if "your_api_key_here" not in content and "ANTHROPIC_API_KEY=" in content:
                print("[OK] API key already configured!")
                return True
    
    print("[INFO] API Key Setup")
    print()
    print("You need an Anthropic API key to use Claude AI.")
    print("Get one at: https://console.anthropic.com/")
    print()
    
    choice = input("Do you have an API key ready? (y/n): ").strip().lower()
    
    if choice != 'y':
        print()
        print("No problem! Here's what to do:")
        print("1. Go to https://console.anthropic.com/")
        print("2. Sign up or log in")
        print("3. Create an API key")
        print("4. Come back and run this script again")
        return False
    
    api_key = input("\nEnter your API key: ").strip()
    
    if not api_key:
        print("❌ API key cannot be empty")
        return False
    
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(f"# Anthropic API Configuration\nANTHROPIC_API_KEY={api_key}\n")
    
    print("[OK] API key saved to .env file!")
    return True


def check_input_docs():
    """Check if there are input documents."""
    input_dir = Path("input_docs")
    docs = [f for f in input_dir.iterdir() if f.is_file() and f.suffix in ['.pdf', '.txt', '.md']]
    
    if not docs:
        print("[INFO] No input documents found")
        print()
        print("Add your documents to: input_docs/")
        print("Supported formats: .pdf, .txt, .md")
        print()
        print("Examples:")
        print("  - Meeting transcripts")
        print("  - Email threads")
        print("  - Requirements documents")
        print("  - Project notes")
        print()
        
        choice = input("Do you want to copy example docs from misc_docs/? (y/n): ").strip().lower()
        
        if choice == 'y':
            misc_dir = Path("misc_docs")
            if misc_dir.exists():
                import shutil
                copied = 0
                for doc in misc_dir.glob("*.pdf"):
                    shutil.copy(doc, input_dir)
                    print(f"  Copied: {doc.name}")
                    copied += 1
                    if copied >= 1:  # Copy just one example
                        break
                
                if copied > 0:
                    print(f"[OK] Copied {copied} example document(s)")
                    return True
        
        return False
    
    print(f"[OK] Found {len(docs)} document(s) in input_docs/")
    for doc in docs[:3]:  # Show first 3
        print(f"   • {doc.name}")
    if len(docs) > 3:
        print(f"   ... and {len(docs) - 3} more")
    return True


def run_generator():
    """Run the scope generator."""
    print("🚀 Running scope generator...")
    print()
    
    try:
        subprocess.check_call([sys.executable, "-m", "scope_doc_gen.main"])
        return True
    except subprocess.CalledProcessError:
        print("❌ Generation failed")
        return False
    except KeyboardInterrupt:
        print("\n\n[WARN] Cancelled by user")
        return False


def main():
    """Main quick start flow."""
    print_header("🚀 SCOPE DOCUMENT GENERATOR - Quick Start")
    
    print("This script will guide you through:")
    print("  1. Installing dependencies")
    print("  2. Setting up your API key")
    print("  3. Preparing input documents")
    print("  4. Running your first generation")
    print()
    
    input("Press Enter to continue...")
    
    # Step 1: Check Python
    print_step(1, "Checking Python Version")
    if not check_python():
        return
    
    # Step 2: Install dependencies
    print_step(2, "Installing Dependencies")
    choice = input("Install required packages? (y/n): ").strip().lower()
    if choice == 'y':
        if not install_dependencies():
            return
    else:
        print("[WARN] Skipped. Make sure to run: pip install -r requirements.txt")
    
    # Step 3: API Key setup
    print_step(3, "API Key Configuration")
    if not setup_api_key():
        print("\n⏸️  Setup paused. Run this script again once you have your API key.")
        return
    
    # Step 4: Input documents
    print_step(4, "Input Documents")
    has_docs = check_input_docs()
    
    if not has_docs:
        print("\n⏸️  Setup paused. Add documents to input_docs/ and run this script again.")
        return
    
    # Step 5: Run generator
    print_step(5, "Generate Scope Document")
    
    choice = input("Ready to generate your first scope document? (y/n): ").strip().lower()
    
    if choice == 'y':
        run_generator()
        
        print_header("🎉 QUICK START COMPLETE!")
        print("Check the generated_scopes/ folder for your document!")
        print()
        print("Next steps:")
        print("  • Review the generated document")
        print("  • Edit extracted_variables.json if needed")
        print("  • Regenerate: python -m scope_doc_gen.main --from-variables generated_scopes/extracted_variables.json")
        print()
    else:
        print("\nNo problem! When you're ready, run:")
        print("  python -m scope_doc_gen.main")
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Quick start cancelled. Come back anytime!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        print("Please check the error message and try again.")

