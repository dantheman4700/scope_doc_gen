# Scope Document Generator

AI-powered automation for generating technical scope documents from various input materials (PDFs, transcripts, emails, etc.).

## Overview

This tool uses Claude AI (Anthropic) to analyze your input documents and automatically generate professional technical scope documents. Simply drop your meeting notes, email threads, transcripts, or other project materials into a folder, and the system will extract all necessary information and generate a complete scope document.

## Features

- [OK] Multi-format ingestion: Supports PDF, TXT, Markdown, and VTT transcripts
- [OK] AI-powered extraction: Uses Claude to intelligently extract and generate variables
- [OK] Template-based generation: Consistent, professional output every time
- 🔄 **Interactive refinement**: Optional mode to refine specific sections
- 💾 **Intermediate saving**: Saves extracted variables for review and reuse
- ⚡ **Fast processing**: Processes multiple documents in seconds

## Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd scope_doc_gen
```

2. **Create a virtual environment** (recommended):
```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Set up your API key**:
```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your Anthropic API key
# Get your API key from: https://console.anthropic.com/
```

## Quick Start

### Basic Usage

1. **Add your input documents** to the `input_docs/` folder:
   - PDFs of existing scope documents
   - Meeting transcripts
   - Email threads
   - Requirements documents
- Any relevant project materials
- Images (PNG, JPG, TIFF, WebP). These are uploaded directly so Claude can inspect them, while summaries log a placeholder.
- PDFs. Files up to 32 MB and 100 pages are uploaded natively. Larger files fall back to text extraction and, if no text is available, the PDF is split into overlapping page chunks so Claude can analyze each segment.
   - **(Optional but Recommended)** An `instructions.txt` file. This file can be used to provide specific instructions, context, or key details that you want the AI to pay close attention to. For example, you could specify the client's name, project goals, or any "out of scope" items. This helps guide the AI and improves the quality of the generated document.

2. **Run the generator**:
```bash
python -m scope_doc_gen.main
```

3. **Find your generated document** in `generated_scopes/`
4. **Check the console log**. For each input, the generator notes whether it was uploaded natively, extracted as text, or processed via OCR.

### Advanced Usage

**Interactive mode** (refine variables before final generation):
```bash
python -m scope_doc_gen.main --interactive
```

**Custom directories**:
```bash
python -m scope_doc_gen.main --input-dir ./my_docs --output-dir ./my_output
```

**Generate from pre-extracted variables**:
```bash
python -m scope_doc_gen.main --from-variables extracted_variables.json
```

**Enable historical reference estimates** (optional):
```bash
python -m scope_doc_gen.main --history-use --history-dsn "postgresql://user:pass@localhost:5432/history"
```

### Historical reference workflow (optional)

1. **Prepare Postgres with pgvector**
   ```sql
   CREATE DATABASE history;
   \c history
   CREATE EXTENSION vector;
   ```

2. **Import historical scopes** (PDF/MD/TXT) so estimates can be reused:
   ```bash
   python -m scope_doc_gen.history_import ./path/to/past_scopes \
     --dsn "postgresql://user:pass@localhost:5432/history"
   ```

3. **Generate with references enabled**:
   ```bash
   python -m scope_doc_gen.main --history-use \
     --history-dsn "postgresql://user:pass@localhost:5432/history"
   ```

The importer asks Claude to extract key estimation signals (hours, timeline, milestones, services). During generation, similar past projects are retrieved, summarized, and provided to the model as guidance.

## Project Structure

```
scope_doc_gen/
├── scope_doc_gen/          # Main package
│   ├── __init__.py
│   ├── config.py           # Configuration and paths
│   ├── ingest.py           # Document ingestion
│   ├── llm.py              # Claude AI integration
│   ├── renderer.py         # Template rendering
│   └── main.py             # Main orchestration
├── input_docs/             # Put your input documents here
├── generated_scopes/       # Generated documents go here
├── template_scope.md       # Document template
├── temp_var_schema.json    # JSON schema for variables
├── variables.json          # Variable definitions and styles
├── requirements.txt        # Python dependencies
├── .env.example            # Example environment file
└── README.md              # This file
```

## Dependencies

- Python 3.10+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed and on your PATH (required for OCR of scanned PDFs/images)
- The packages listed in `requirements.txt` (install with `pip install -r requirements.txt`)

## How It Works

1. **Document Ingestion**: Reads all documents from `input_docs/` and extracts text
2. **AI Analysis**: Sends combined text to Claude with schema and style guidelines
3. **Variable Extraction**: Claude analyzes content and extracts all required variables
4. **Template Rendering**: Fills in the markdown template with extracted data
5. **Output Generation**: Saves the complete scope document

## Template Customization

The template is defined in `template_scope.md`. You can customize:

- Section structure
- Variable placeholders (use `{{variable_name}}`)
- Static content and headers

The variables are defined in two files:

- `temp_var_schema.json`: JSON Schema defining data types and validation
- `variables.json`: Detailed style guide for each variable

## Workflow Examples

### Example 1: From Meeting Transcripts
```
input_docs/
├── kickoff_meeting_transcript.txt
├── requirements_discussion.pdf
└── email_thread.txt

→ Run generator → 

generated_scopes/
└── ClientName_ProjectName_TechScope_20250122_143022.md
```

### Example 2: Two-Stage Process
```bash
# Stage 1: Extract variables (review before rendering)
python -m scope_doc_gen.main

# Review/edit: generated_scopes/extracted_variables.json

# Stage 2: Generate from edited variables
python -m scope_doc_gen.main --from-variables generated_scopes/extracted_variables.json
```

## Configuration

Edit `scope_doc_gen/config.py` to customize:

- **Claude model**: Change `CLAUDE_MODEL` for different versions
- **Temperature**: Adjust `TEMPERATURE` for more/less creative output
- **Token limits**: Modify `MAX_TOKENS` for longer/shorter responses
- **Paths**: Change default input/output directories

## Troubleshooting

### "ANTHROPIC_API_KEY not found"
- Make sure you've created `.env` file from `.env.example`
- Add your API key: `ANTHROPIC_API_KEY=your_key_here`

### "No documents found to process"
- Check that documents are in `input_docs/` folder
- Verify files have supported extensions (.pdf, .txt, .md)

### PDF extraction issues
- The generator will upload PDFs up to 32 MB / 100 pages directly to Claude. Larger files fall back to text extraction and automatically split into overlapping page batches when native text is missing.
- If you notice gaps in the extracted text for large PDFs, consider keeping the original file name consistent so the chunk artifacts are easier to correlate.

### Generated document has "TBD" fields
- Input documents may not contain all required information
- Use `--interactive` mode to manually fill in missing data
- Or edit `extracted_variables.json` directly and regenerate

## Roadmap

- [ ] Add support for DOCX files
- [ ] Implement OCR for image-based PDFs
- [ ] Add web interface
- [ ] Support for multiple templates
- [ ] Email ingestion via IMAP
- [ ] Variable validation and suggestions
- [ ] Cost estimation calculator
- [ ] Export to PDF format

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

[Specify your license here]

## Support

For issues or questions:
- Open an issue on GitHub
- Check existing documentation
- Review example scope documents in `misc_docs/`

