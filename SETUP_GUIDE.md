# Setup Guide

## Quick Start (5 minutes)

### 1. Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Get Your Anthropic API Key

1. Go to [https://console.anthropic.com/](https://console.anthropic.com/)
2. Sign up or log in
3. Navigate to API Keys
4. Create a new API key
5. Copy the key (starts with `sk-ant-`)

### 3. Configure Environment

Create a `.env` file in the project root:

```bash
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

Or on Windows PowerShell:
```powershell
@"
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
"@ | Out-File -FilePath .env -Encoding UTF8
```

### 4. Add Your Documents

Place your source materials in `input_docs/`:
- Meeting transcripts (.txt)
- Email threads
- PDF documents
- Requirements docs
- Any project materials

### 5. Run the Generator

```bash
python -m scope_doc_gen.main
```

That's it! Your generated scope document will be in `generated_scopes/`.

## Troubleshooting

### "ANTHROPIC_API_KEY not found"
- Check that `.env` file exists in project root
- Verify the file contains: `ANTHROPIC_API_KEY=your_key_here`
- Make sure there are no spaces around the `=`

### "No module named 'anthropic'"
- Run: `pip install -r requirements.txt`
- Make sure your virtual environment is activated

### "No documents found to process"
- Add documents to `input_docs/` folder
- Supported formats: .pdf, .txt, .md
- Check file extensions are correct

### PDF extraction returns empty text
- Some PDFs are image-based and need OCR
- Try converting PDF to text first
- Or copy-paste text into a .txt file

## Next Steps

1. **Review the output**: Check `generated_scopes/` for your document
2. **Refine if needed**: Edit `extracted_variables.json` and regenerate
3. **Customize template**: Edit `template_scope.md` for your needs
4. **Adjust variables**: Modify `variables.json` for different styles

## Advanced Configuration

Edit `scope_doc_gen/config.py` to customize:

```python
# Use different Claude model
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"

# Adjust creativity (0.0 = consistent, 1.0 = creative)
TEMPERATURE = 0.3

# Change token limits
MAX_TOKENS = 8000
```

## Testing

Try with example documents from `misc_docs/`:

```bash
# Copy an example to input_docs
cp "misc_docs/Project_ AI-Powered Technical Scope Automation.pdf" input_docs/

# Generate
python -m scope_doc_gen.main
```

## Cost Estimation

Approximate costs using Claude Sonnet 3.5:
- Input: ~$3 per million tokens
- Output: ~$15 per million tokens

Typical scope generation:
- Input: ~20K-50K tokens (documents)
- Output: ~5K-10K tokens (scope)
- **Cost per generation: $0.15 - $0.50**

Batch processing is more economical!

## Support

- Check the main [README.md](README.md) for full documentation
- Review [example_usage.py](example_usage.py) for code examples
- Examine `misc_docs/` for sample scope documents

