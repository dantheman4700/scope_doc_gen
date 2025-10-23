[INFO] INPUT DOCUMENTS FOLDER
========================

Place your source documents here for the scope generator to analyze.

Supported formats:
- PDF (.pdf)
- Text files (.txt)
- Markdown (.md)

What to include:
- Meeting transcripts
- Email threads
- Requirements documents
- Existing scope documents
- Project notes
- Any relevant project materials

Example:
--------
input_docs/
├── kickoff_meeting_transcript.txt
├── client_email_thread.txt
├── requirements.pdf
└── existing_scope_example.pdf

Then run:
  python -m scope_doc_gen.main

Your generated scope will appear in: generated_scopes/

