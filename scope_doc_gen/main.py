"""Main orchestration script for scope document generation."""

import base64
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from .config import (
    TEMPLATE_PATH,
    VARIABLES_SCHEMA_PATH,
    VARIABLES_GUIDE_PATH,
    INPUT_DOCS_DIR,
    OUTPUT_DIR,
    HISTORY_ENABLED,
    HISTORY_DB_URL,
    HISTORY_EMBEDDING_MODEL,
    HISTORY_TOPN,
)
from .ingest import DocumentIngester
from .llm import ClaudeExtractor
from .renderer import TemplateRenderer
from .summarizer import FileSummarizer
from .aggregate import aggregate_summaries
from .history_retrieval import HistoryRetriever


class ScopeDocGenerator:
    """Main orchestrator for scope document generation."""
    
    def __init__(self, input_dir: Optional[Path] = None, output_dir: Optional[Path] = None, history_retriever: HistoryRetriever | None = None):
        """
        Initialize the generator.
        
        Args:
            input_dir: Directory containing input documents (default: input_docs/)
            output_dir: Directory for generated documents (default: generated_scopes/)
        """
        self.input_dir = input_dir or INPUT_DOCS_DIR
        self.output_dir = output_dir or OUTPUT_DIR
        
        # Initialize components
        self.ingester = DocumentIngester()
        self.extractor = ClaudeExtractor()
        self.renderer = TemplateRenderer(TEMPLATE_PATH)
        self.summarizer = FileSummarizer(self.extractor)
        self.history_retriever = history_retriever
        
        # Load schemas
        self.variables_schema = self._load_json(VARIABLES_SCHEMA_PATH)
        self.variables_guide = self._load_json(VARIABLES_GUIDE_PATH)
    
    def _load_json(self, path: Path) -> dict:
        """Load JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_instructions_file(self, available_filenames: list[str]) -> tuple[str | None, dict | None]:
        """Load casual instructions from input_dir/instructions.txt, if present.

        Expected format (free-form, forgiving):
            Client: Example Client
            Project: Example Solution Build
            notes:
              kickoff_meeting_transcript.txt: Kickoff call notes
              product_api_documentation.pdf: Vendor API docs

        Returns:
            (project_focus_string | None, file_context_dict | None)
        """
        instr_path = self.input_dir / "instructions.txt"
        if not instr_path.exists():
            return None, None

        client = None
        project = None
        notes: dict[str, str] = {}

        try:
            with open(instr_path, 'r', encoding='utf-8') as f:
                lines = [ln.rstrip() for ln in f]
        except Exception as e:
            print(f"[WARN] Could not read instructions.txt: {e}")
            return None, None

        in_notes = False
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            lower = line.lower()

            if lower.startswith('client:'):
                client = line.split(':', 1)[1].strip()
                continue
            if lower.startswith('project:'):
                project = line.split(':', 1)[1].strip()
                continue
            if lower.startswith('notes:'):
                in_notes = True
                continue

            if in_notes:
                # Accept formats:
                # filename: note
                # - filename: note
                # * filename: note
                if line.startswith('- ') or line.startswith('* '):
                    line = line[2:].strip()
                if ':' in line:
                    fname, note = line.split(':', 1)
                    fname = fname.strip()
                    note = note.strip()
                    if fname in available_filenames:
                        notes[fname] = note
                    else:
                        # best-effort fuzzy match by lower
                        match = next((n for n in available_filenames if n.lower() == fname.lower()), None)
                        if match:
                            notes[match] = note

        project_focus = None
        if client or project:
            # Compact focus string for the LLM
            project_focus = f"Client: {client or ''}; Project: {project or ''}".strip('; ')

        file_context = notes if notes else None
        return project_focus, file_context
    
    def generate(
        self,
        save_intermediate: bool = True,
        interactive: bool = False,
        project_identifier: str = None,
        smart_ingest: bool = True,
        context_notes_path: Optional[Path] = None,
        date_override: Optional[str] = None,
    ) -> str:
        """
        Generate a scope document from input documents.
        
        Args:
            save_intermediate: Whether to save intermediate extracted variables
            interactive: Whether to allow interactive refinement
            
        Returns:
            Path to generated document
        """
        print("="*80)
        print("SCOPE DOCUMENT GENERATOR")
        print("="*80)
        
        # Step 1: Ingest documents
        print(f"\n[INFO] Ingesting documents from: {self.input_dir}")
        documents = self.ingester.ingest_directory(self.input_dir)
        
        if not documents:
            print("[ERROR] No documents found to process!")
            print(f"        Please add documents to: {self.input_dir}")
            return None
        
        print(f"\n[OK] Found {len(documents)} document(s)")

        instructions_doc = None
        analysis_docs: list[dict] = []
        for d in documents:
            if d['filename'].lower() == 'instructions.txt':
                instructions_doc = d
                continue
            analysis_docs.append(d)

        for d in analysis_docs:
            size_info = d.get('size_bytes')
            meta_parts = []
            if size_info is not None:
                meta_parts.append(f"{size_info} bytes")
            if d.get('source_type'):
                meta_parts.append(d['source_type'])
            if d.get('upload_via'):
                meta_parts.append(f"via {d['upload_via']}")
            if d.get('page_count'):
                meta_parts.append(f"{d['page_count']} pages")
            print(f"   - {d['filename']} ({', '.join(meta_parts)})")

        if instructions_doc:
            print("   - instructions.txt (used for guidance only; excluded from summarization)")
        
        # Step 2: Combine documents
        combined = self.ingester.combine_documents(analysis_docs)
        attachments = self._collect_attachments(analysis_docs)
        
        # Load optional per-file context notes
        file_context = None
        if context_notes_path:
            try:
                with open(context_notes_path, 'r', encoding='utf-8') as f:
                    file_context = json.load(f)
                if not isinstance(file_context, dict):
                    print(f"[WARN] Context file is not a JSON object; ignoring: {context_notes_path}")
                    file_context = None
                else:
                    print(f"[OK] Loaded file context notes from: {context_notes_path}")
            except Exception as e:
                print(f"[WARN] Could not load context notes from {context_notes_path}: {e}")

        # Load casual instructions from instructions.txt (no flags required)
        try:
            project_focus2, file_notes2 = self._load_instructions_file([d['filename'] for d in documents])
            if project_focus2:
                if file_context is None:
                    file_context = {}
                file_context["PROJECT_FOCUS"] = project_focus2
                print(f"[OK] Loaded project focus from instructions.txt: {project_focus2}")
            if file_notes2:
                if file_context is None:
                    file_context = {}
                file_context.update(file_notes2)
                print(f"[OK] Loaded {len(file_notes2)} file note(s) from instructions.txt")
        except Exception as e:
            print(f"[WARN] Could not parse instructions.txt: {e}")
        
        # If a project identifier is provided, add it as guidance (no pre-filtering)
        if project_identifier:
            if file_context is None:
                file_context = {}
            file_context["PROJECT_FOCUS"] = project_identifier
        print(f"[OK] Combined document length: {len(combined)} characters")
        if getattr(self, 'debug', False):
            snippet = combined[:1200]
            print("\n--- Combined Snippet (first 1200 chars) ---")
            print(snippet)
            print("--- End Snippet ---\n")
            try:
                debug_combined_path = self.output_dir / "combined_debug.txt"
                with open(debug_combined_path, 'w', encoding='utf-8') as f:
                    f.write(combined)
                print(f"[OK] Saved combined corpus to: {debug_combined_path}")
            except Exception as e:
                print(f"[WARN] Could not save combined corpus: {e}")
        
        # Step 3: Two-pass summarization → global context
        print("\n" + "="*80)
        print("SUMMARIZING FILES")
        print("="*80)

        file_notes = {}
        if file_context:
            # Pull only per-file notes (ignore PROJECT_FOCUS key)
            file_notes = {k: v for k, v in file_context.items() if k != "PROJECT_FOCUS"}
        project_focus_hint = None
        if file_context and "PROJECT_FOCUS" in file_context:
            project_focus_hint = file_context["PROJECT_FOCUS"]

        summaries = []
        for d in analysis_docs:
            fname = d['filename']
            note = file_notes.get(fname)
            fs = self.summarizer.summarize_document(
                document=d,
                project_focus=project_focus_hint,
                file_note=note,
            )
            summaries.append(fs.summary)
            print(f"[OK] Summarized: {fname}")

        context_pack = aggregate_summaries(summaries)

        # Save artifacts
        artifacts_dir = OUTPUT_DIR / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        context_path = artifacts_dir / "context_pack.json"
        with open(context_path, 'w', encoding='utf-8') as f:
            json.dump(context_pack, f, indent=2)
        print(f"[OK] Saved context pack: {context_path}")

        # Step 4: Extract variables using Claude
        print("\n" + "="*80)
        print("EXTRACTING VARIABLES")
        print("="*80)
        
        # Build compact extraction input: instructions + context_pack + top-K evidence quotes per file
        reference_block = None
        if self.history_retriever:
            try:
                reference_block = self.history_retriever.fetch_reference_block(context_pack)
                if reference_block:
                    print("[OK] Loaded reference estimates from historical scopes")
            except Exception as history_err:
                print(f"[WARN] Failed to fetch historical references: {history_err}")

        compact_input = self._build_compact_input(
            analysis_docs,
            context_pack,
            max_quotes_per_file=5,
            instructions_doc=instructions_doc,
            reference_block=reference_block,
        )

        if getattr(self, 'debug', False):
            variables, raw = self.extractor.extract_variables_with_raw(
                compact_input,
                self.variables_schema,
                self.variables_guide,
                file_context=file_context,
                attachments=attachments,
            )
            # Persist raw model output for debugging
            debug_raw_path = self.output_dir / "claude_raw_output.json"
            try:
                with open(debug_raw_path, 'w', encoding='utf-8') as f:
                    f.write(raw)
                print(f"[OK] Saved raw model output to: {debug_raw_path}")
            except Exception as e:
                print(f"[WARN] Could not save raw output: {e}")
        else:
            variables = self.extractor.extract_variables(
                compact_input,
                self.variables_schema,
                self.variables_guide,
                file_context=file_context,
                attachments=attachments,
            )

        # Force date_created to a known value (avoid LLM guessing)
        try:
            variables['date_created'] = date_override or datetime.now().date().isoformat()
        except Exception:
            pass
        
        # Save intermediate results
        if save_intermediate:
            intermediate_path = self.output_dir / "extracted_variables.json"
            with open(intermediate_path, 'w', encoding='utf-8') as f:
                json.dump(variables, f, indent=2)
            print(f"[OK] Saved extracted variables to: {intermediate_path}")
        
        # Step 4: Interactive refinement (optional)
        if interactive:
            variables = self._interactive_refinement(variables)
        
        # Step 5: Render template
        print("\n" + "="*80)
        print("GENERATING DOCUMENT")
        print("="*80)
        
        rendered = self.renderer.render(variables)
        
        # Step 6: Save output
        output_filename = self.renderer.generate_filename(variables)
        output_path = self.output_dir / output_filename
        self.renderer.save(rendered, output_path)
        
        print("\n" + "="*80)
        print("GENERATION COMPLETE")
        print("="*80)
        print(f"[OK] Document saved to: {output_path}")
        
        return str(output_path)
    
    def _interactive_refinement(self, variables: dict) -> dict:
        """
        Allow user to interactively refine variables.
        
        Args:
            variables: Current variable values
            
        Returns:
            Refined variables
        """
        print("\n" + "="*80)
        print("INTERACTIVE REFINEMENT")
        print("="*80)
        print("\nYou can now refine specific variables.")
        print("Enter variable name to refine (or 'done' to continue):")
        
        while True:
            var_name = input("\nVariable name (or 'done'): ").strip()
            
            if var_name.lower() == 'done':
                break
            
            if var_name not in variables:
                print(f"❌ Variable '{var_name}' not found")
                print(f"Available variables: {', '.join(variables.keys())}")
                continue
            
            print(f"\nCurrent value:")
            print(json.dumps(variables[var_name], indent=2))
            print("\nEnter refinement instructions:")
            instructions = input("> ").strip()
            
            if instructions:
                refined = self.extractor.refine_variable(
                    var_name,
                    variables[var_name],
                    instructions,
                    self.variables_guide
                )
                variables[var_name] = refined
                print(f"✓ Updated {var_name}")
        
        return variables
    
    def generate_from_variables(self, variables_file: Path) -> str:
        """
        Generate document from pre-extracted variables JSON file.
        
        Args:
            variables_file: Path to JSON file with variables
            
        Returns:
            Path to generated document
        """
        print(f"[INFO] Loading variables from: {variables_file}")
        
        with open(variables_file, 'r', encoding='utf-8') as f:
            variables = json.load(f)
        
        print("[INFO] Rendering template...")
        rendered = self.renderer.render(variables)
        
        output_filename = self.renderer.generate_filename(variables)
        output_path = self.output_dir / output_filename
        self.renderer.save(rendered, output_path)
        
        print(f"[OK] Document saved to: {output_path}")
        return str(output_path)

    def _build_compact_input(
        self,
        documents,
        context_pack: dict,
        max_quotes_per_file: int = 5,
        instructions_doc: dict | None = None,
        reference_block: str | None = None,
    ) -> str:
        """Construct a compact input payload for extraction.

        Includes instructions.txt content if present, the aggregated context pack,
        and a limited number of evidence quotes per file to reduce token load.
        """
        parts = []

        if reference_block:
            parts.append(reference_block)

        parts.append(
            "RESEARCH_GUIDANCE:\n"
            "- Use the web_search tool when critical API, integration, compliance, or timeline details are missing or ambiguous.\n"
            "- Prefer official vendor documentation, pricing pages, and reputable technical sources.\n"
            "- Incorporate verified findings into estimates (timeline, effort, risks) and call out any assumptions resolved by research.\n"
            "- In the final document, add an 'Appendix - External References' section with bullet points: Title – URL, summarizing the key insight from each researched source."
        )

        # Include instructions.txt raw content verbatim if present
        if instructions_doc:
            parts.append("INSTRUCTIONS.TXT:\n" + instructions_doc['content'].strip())

        # Include compact context pack
        parts.append("CONTEXT_PACK:\n" + json.dumps(context_pack, indent=2))

        # Include limited evidence quotes grouped by source file
        quotes_by_file = {}
        for q in context_pack.get('evidence_quotes', []) or []:
            src = q.get('source') or 'unknown'
            quotes_by_file.setdefault(src, []).append(q)

        parts.append("EVIDENCE_QUOTES (limited):")
        for src, quotes in quotes_by_file.items():
            parts.append(f"- {src}:")
            for q in quotes[:max_quotes_per_file]:
                quote = q.get('quote', '')
                rationale = q.get('rationale', '')
                approx = q.get('approx_location', '')
                parts.append(f"  * \"{quote}\" (why: {rationale}; where: {approx})")

        return "\n\n".join(parts)

    def _collect_attachments(self, documents: List[Dict]) -> List[Dict[str, str]]:
        attachments: List[Dict[str, str]] = []

        for doc in documents:
            if not doc.get('can_upload') or doc.get('upload_via') != 'attachment':
                continue

            path = doc.get('path')
            if not path:
                continue

            media_type = doc.get('media_type', 'application/octet-stream')
            attachment_type = 'document'
            if media_type.startswith('image/'):
                attachment_type = 'image'

            try:
                with open(path, 'rb') as f:
                    data_b64 = base64.standard_b64encode(f.read()).decode('utf-8')
                attachments.append({
                    'type': attachment_type,
                    'source': {
                        'type': 'base64',
                        'media_type': media_type,
                        'data': data_b64,
                    }
                })
            except Exception as exc:
                print(f"[WARN] Could not prepare attachment for {doc.get('filename')}: {exc}")

        return attachments


def main():
    """Command-line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate technical scope documents from input materials using AI"
    )
    parser.add_argument(
        '--input-dir',
        type=Path,
        help=f"Directory containing input documents (default: {INPUT_DOCS_DIR})"
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        help=f"Directory for output documents (default: {OUTPUT_DIR})"
    )
    parser.add_argument(
        '--from-variables',
        type=Path,
        help="Generate from existing variables JSON file"
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help="Enable interactive refinement mode"
    )
    parser.add_argument(
        '--project',
        type=str,
        help="Project focus hint to guide extraction (no pre-filtering)"
    )
    parser.add_argument(
        '--no-smart-ingest',
        action='store_true',
        help="Disable smart ingestion helpers (e.g., special transcript parsing)"
    )
    parser.add_argument(
        '--context-file',
        type=Path,
        help="Path to JSON mapping of { filename: context_note } for per-file guidance"
    )
    parser.add_argument(
        '--no-save-intermediate',
        action='store_true',
        help="Don't save intermediate extracted variables"
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help="Enable debug logging and save raw LLM output"
    )
    parser.add_argument(
        '--date',
        type=str,
        help="Override date_created (YYYY-MM-DD); defaults to today's date"
    )
    parser.add_argument(
        '--history-use',
        action='store_true',
        help="Enable historical scope retrieval for reference estimates"
    )
    parser.add_argument(
        '--history-dsn',
        type=str,
        help="PostgreSQL DSN for historical scope storage"
    )
    parser.add_argument(
        '--history-model',
        type=str,
        help="Embedding model for historical profiles"
    )
    parser.add_argument(
        '--history-topn',
        type=int,
        help="Number of similar historical scopes to retrieve"
    )
    
    args = parser.parse_args()
    
    try:
        history_retriever = None
        if args.history_use or HISTORY_ENABLED:
            history_dsn = args.history_dsn or HISTORY_DB_URL
            if history_dsn:
                history_model = args.history_model or HISTORY_EMBEDDING_MODEL
                history_topn = args.history_topn or HISTORY_TOPN
                try:
                    history_retriever = HistoryRetriever(
                        dsn=history_dsn,
                        model_name=history_model,
                        top_n=history_topn,
                        extractor=None,  # temporary, replaced after generator init
                    )
                    print("[OK] Historical retrieval enabled")
                except Exception as err:
                    print(f"[WARN] Could not initialize historical retrieval: {err}")
            else:
                print("[WARN] History retrieval requested but no DSN provided")

        generator = ScopeDocGenerator(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            history_retriever=history_retriever,
        )

        # If history retriever exists, attach the live Claude extractor so it can build the query phrase via Claude
        if history_retriever is not None:
            try:
                # generator.extractor is the live ClaudeExtractor
                history_retriever.extractor = generator.extractor
            except Exception:
                pass
        # Attach debug flag to instance
        setattr(generator, 'debug', args.debug)
        
        if args.from_variables:
            generator.generate_from_variables(args.from_variables)
        else:
            generator.generate(
                save_intermediate=not args.no_save_intermediate,
                interactive=args.interactive,
                project_identifier=args.project,
                smart_ingest=not args.no_smart_ingest,
                context_notes_path=args.context_file,
                date_override=args.date,
            )
    
    except KeyboardInterrupt:
        print("\n\n[WARN] Generation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()

