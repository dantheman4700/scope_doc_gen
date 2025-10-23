"""Helper script to create .env file interactively."""

import os
from pathlib import Path

def create_env_file():
    """Interactive script to create .env file with API key."""
    print("="*60)
    print("SCOPE DOCUMENT GENERATOR - Environment Setup")
    print("="*60)
    print()
    
    env_path = Path(".env")
    
    if env_path.exists():
        print("[WARN] .env file already exists!")
        overwrite = input("Do you want to overwrite it? (y/n): ").strip().lower()
        if overwrite != 'y':
            print("Setup cancelled.")
            return
    
    print("\n[INFO] You'll need an Anthropic API key to use this tool.")
    print("   Get one at: https://console.anthropic.com/")
    print()
    
    while True:
        api_key = input("Enter your Anthropic API key: ").strip()
        
        if not api_key:
            print("❌ API key cannot be empty!")
            continue
        
        if not api_key.startswith("sk-ant-"):
            print("[WARN] Anthropic keys usually start with 'sk-ant-'")
            confirm = input("Continue anyway? (y/n): ").strip().lower()
            if confirm != 'y':
                continue
        
        break
    
    # Create .env file
    env_content = f"# Anthropic API Configuration\nANTHROPIC_API_KEY={api_key}\n"
    
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print("\n[OK] .env file created successfully!")
    print(f"   Location: {env_path.absolute()}")
    print()
    print("Next steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Add documents to: input_docs/")
    print("3. Run generator: python -m scope_doc_gen.main")
    print()

if __name__ == "__main__":
    try:
        create_env_file()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")

