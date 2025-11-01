"""Main orchestration script for scope document generation."""
from __future__ import annotations

import base64
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Callable


StepCallback = Callable[[str, str, Optional[str]], None]

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
    ENABLE_WEB_RESEARCH,
)
from .ingest import DocumentIngester
from .llm import ClaudeExtractor
from .renderer import TemplateRenderer
from .history_retrieval import HistoryRetriever
from .research import ResearchManager, ResearchMode


class ScopeDocGenerator:
    """Main orchestrator for scope document generation."""

    def __init__(
        self,
        input_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        history_retriever: Optional[HistoryRetriever] = None,
        project_dir: Optional[Path] = None,
    ):
        """
        Initialize the generator.

        Args:
            input_dir: Directory containing input documents (default: input_docs/)
            output_dir: Directory for generated documents (default: generated_scopes/)
            project_dir: Base directory for project-scoped artifacts (optional)
        """
        self.project_dir = Path(project_dir).resolve() if project_dir else None

        if self.project_dir:
            self.project_dir.mkdir(parents=True, exist_ok=True)

        def _resolve(value: Optional[Path], fallback: Path) -> Path:
            if value is not None:
                return Path(value).resolve()
            return fallback.resolve()

        self.input_dir = _resolve(
            input_dir,
            (self.project_dir / "input") if self.project_dir else INPUT_DOCS_DIR,
        )
        self.output_dir = _resolve(
            output_dir,
            (self.project_dir / "outputs") if self.project_dir else OUTPUT_DIR,
        )
        self.working_dir = (
            (self.project_dir / "working") if self.project_dir else (self.output_dir / "working")
        ).resolve()
        self.cache_dir = (self.working_dir / "cache").resolve()
        self.artifacts_dir = (self.working_dir / "artifacts").resolve()

        for path in [self.input_dir, self.output_dir, self.working_dir, self.cache_dir, self.artifacts_dir]:
            path.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.ingester = DocumentIngester()
        self.extractor = ClaudeExtractor()
        self.renderer = TemplateRenderer(TEMPLATE_PATH)
        self.history_retriever = history_retriever
        
        # Load schemas
        self.variables_schema = self._load_json(VARIABLES_SCHEMA_PATH)
        self.variables_guide = self._load_json(VARIABLES_GUIDE_PATH)
    
    def _load_json(self, path: Path) -> dict:
        """Load JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_instructions_file(self, available_filenames: List[str]) -> tuple[Optional[str], Optional[dict]]:
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
        interactive: bool = False,
        project_identifier: str = None,
        smart_ingest: bool = True,
        context_notes_path: Optional[Path] = None,
        date_override: Optional[str] = None,
        research_mode: str = "quick",
        run_mode: str = "full",
        step_callback: Optional[StepCallback] = None,
        allow_web_search: bool = True,
        instructions: Optional[str] = None,
    ) -> str:
        """
        Generate a scope document from input documents.
        
        Args:
            interactive: Whether to allow interactive refinement
            
        Returns:
            Path to generated document
        """
        print("="*80)
        print("SCOPE DOCUMENT GENERATOR")
        print("="*80)

        run_mode_normalized = (run_mode or "full").strip().lower()
        if run_mode_normalized not in {"fast", "full"}:
            print(f"[WARN] Unknown run mode '{run_mode}', defaulting to 'full'")
            run_mode_normalized = "full"
        fast_mode_requested = run_mode_normalized == "fast"

        def notify(step: str, event: str, detail: Optional[str] = None) -> None:
            if step_callback is None:
                return
            try:
                step_callback(step, event, detail)
            except Exception as callback_exc:  # pragma: no cover - defensive log
                print(f"[WARN] Step callback error for '{step}': {callback_exc}")
        
        # Step 1: Ingest documents
        print(f"\n[INFO] Ingesting documents from: {self.input_dir}")
        notify("ingest", "started", None)
        try:
            documents = self.ingester.ingest_directory(self.input_dir)
        except Exception as ingest_exc:
            notify("ingest", "failed", str(ingest_exc))
            raise
        
        if not documents:
            notify("ingest", "failed", "No documents found")
            print("[ERROR] No documents found to process!")
            print(f"        Please add documents to: {self.input_dir}")
            return None
        
        notify("ingest", "completed", f"{len(documents)} document(s)")

        print(f"\n[OK] Found {len(documents)} document(s)")

        # All documents are analysis docs (no special handling for instructions.txt)
        analysis_docs = documents

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
                debug_combined_path = self.working_dir / "combined_debug.txt"
                with open(debug_combined_path, 'w', encoding='utf-8') as f:
                    f.write(combined)
                print(f"[OK] Saved combined corpus to: {debug_combined_path}")
            except Exception as e:
                print(f"[WARN] Could not save combined corpus: {e}")
        
        file_notes: Dict[str, str] = {}
        if file_context:
            file_notes = {k: v for k, v in file_context.items() if k != "PROJECT_FOCUS"}
        project_focus_hint = file_context.get("PROJECT_FOCUS") if file_context else None

        context_pack = None

        notify("prepare_context", "started", "fast" if fast_mode_requested else None)
        if fast_mode_requested:
            context_pack = self._load_cached_context_pack()
            if context_pack is not None:
                print("[OK] Loaded existing context pack for fast mode")
                notify("prepare_context", "completed", "Reused cached context pack")
            else:
                print("[WARN] No cached context pack found; rebuilding context from source documents")

        if context_pack is None:
            print("\n" + "="*80)
            print("PREPARING CONTEXT FROM SOURCE DOCUMENTS")
            print("="*80)
            context_pack = self._build_context_pack(analysis_docs, file_notes)
            notify("prepare_context", "completed", f"{len(analysis_docs)} document(s)")

        if context_pack is None:
            notify("prepare_context", "failed", "Context pack unavailable")
            print("[ERROR] Unable to prepare context pack; aborting run")
            return None

        # Research augmentation
        try:
            mode = ResearchMode(research_mode)
        except ValueError:
            print(f"[WARN] Unknown research mode '{research_mode}', defaulting to 'quick'")
            mode = ResearchMode.QUICK

        research_manager = ResearchManager(mode)
        if mode is ResearchMode.FULL:
            notify("research", "started", None)
        research_findings = research_manager.gather_research(context_pack, project_focus_hint)
        notify("research", "completed", f"mode={mode.value}; findings={len(research_findings)}")

        # Save artifacts
        artifacts_dir = self.artifacts_dir
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
            instructions=instructions,
            reference_block=reference_block,
            research_findings=research_findings,
        )

        input_size = len(compact_input)
        if input_size > 120_000:
            print(
                f"[WARN] Claude extraction payload is very large ({input_size:,} characters). "
                "Consider reducing document size or summarizing additional files to avoid malformed responses."
            )

        use_web_search = (
            allow_web_search
            and research_manager.allows_web_search_tool()
            and self.extractor.supports_web_search
        )
        notify("extract", "started", None)

        try:
            if getattr(self, 'debug', False):
                variables, raw = self.extractor.extract_variables_with_raw(
                    compact_input,
                    self.variables_schema,
                    self.variables_guide,
                    file_context=file_context,
                    attachments=attachments,
                    use_web_search=use_web_search,
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
                    use_web_search=use_web_search,
                )
        except Exception as extract_exc:
            detail = str(extract_exc)
            notify("extract", "failed", detail)
            print("[ERROR] Variable extraction failed:", detail)
            if "No JSON object found" in detail:
                print(
                    "[HINT] Claude returned malformed JSON. "
                    "Large inputs or unexpected model output can cause this. Check logs and consider minimizing the prompt."
                )
            raise

        notify("extract", "completed", None)

        # Force date_created to a known value (avoid LLM guessing)
        try:
            variables['date_created'] = date_override or datetime.now().date().isoformat()
        except Exception:
            pass
        
        # Persist extracted variables for downstream use
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
        
        notify("render", "started", None)
        try:
            rendered = self.renderer.render(variables)
            output_filename = self.renderer.generate_filename(variables)
            output_path = self.output_dir / output_filename
            self.renderer.save(rendered, output_path)
        except Exception as render_exc:
            notify("render", "failed", str(render_exc))
            raise
        notify("render", "completed", output_filename)
        
        # Step 6: Save output
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
        instructions: Optional[str] = None,
        reference_block: Optional[str] = None,
        research_findings: Optional[List] = None,
    ) -> str:
        """Construct a compact input payload for extraction.

        Includes instructions if provided, the aggregated context pack,
        and a limited number of evidence quotes per file to reduce token load.
        
        Note: This only includes TEXT content. Binary files (PDFs, images) that are
        natively uploaded are NOT included here - they're sent as attachments.
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

        # Include instructions if provided
        if instructions and instructions.strip():
            parts.append("INSTRUCTIONS:\n" + instructions.strip())

        # Include compact context pack
        parts.append("CONTEXT_PACK:\n" + json.dumps(context_pack, indent=2))

        # Include external research findings
        if research_findings:
            parts.append("EXTERNAL_RESEARCH:")
            for finding in research_findings:
                summary = getattr(finding, "summary", "")
                refs = getattr(finding, "references", [])
                parts.append(f"- Provider: {finding.provider}; Query: {finding.query}")
                if summary:
                    parts.append(f"  Summary: {summary}")
                if refs:
                    parts.append(f"  References: {', '.join(refs)}")

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

        # Only include TEXT-based documents here (not native attachments like PDFs/images)
        # Native attachments are sent separately as binary content blocks
        text_docs = [
            doc for doc in documents
            if doc.get('upload_via') not in ('attachment', 'skipped')
        ]
        
        if text_docs:
            parts.append("DOCUMENTS_FULL_TEXT:")
            for doc in text_docs:
                content = doc.get('content')
                if not content:
                    continue
                metadata = doc.get('metadata') or {}
                filename = metadata.get('original_filename') or doc.get('filename', 'unknown')
                parts.append(f"--- {filename} ---")
                parts.append(content.strip())

        return "\n\n".join(parts)

    def _build_context_pack(self, documents: List[dict], file_notes: Optional[Dict[str, str]] = None) -> dict:
        """Build a lightweight context pack from ingested documents without re-summarizing."""

        context_pack: Dict[str, List] = {
            "documents": [],
            "pain_points": [],
            "risks": [],
            "effort_multipliers": [],
            "integration_notes": [],
            "unknowns": [],
            "must_read_sections": [],
            "evidence_quotes": [],
        }

        for doc in documents:
            metadata = doc.get('metadata') or {}
            original_filename = metadata.get("original_filename", doc.get("filename"))
            context_pack["documents"].append(
                {
                    "filename": doc.get("filename"),
                    "path": doc.get("path"),
                    "source_type": doc.get("source_type"),
                    "media_type": doc.get("media_type"),
                    "size_bytes": doc.get("size_bytes"),
                    "summary_mode": bool(metadata.get("summary_mode")),
                    "original_filename": original_filename,
                    "note": (file_notes or {}).get(original_filename),
                }
            )

        return context_pack

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

    def _load_cached_context_pack(self) -> Optional[dict]:
        path = self.artifacts_dir / "context_pack.json"
        if not path.exists():
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as exc:
            print(f"[WARN] Failed to load cached context pack: {exc}")
            return None


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
    parser.add_argument(
        '--mode',
        type=str,
        choices=['full', 'fast'],
        default='full',
        help="Run mode: 'full' rebuilds context from source documents; 'fast' reuses cached context when available",
    )
    parser.add_argument(
        '--research-mode',
        type=str,
        choices=[mode.value for mode in ResearchMode],
        default=ResearchMode.QUICK.value,
        help="Research strategy: none, quick (Claude web search), or full (Perplexity)",
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
                interactive=args.interactive,
                project_identifier=args.project,
                smart_ingest=not args.no_smart_ingest,
                context_notes_path=args.context_file,
                date_override=args.date,
                research_mode=args.research_mode,
                run_mode=args.mode,
                allow_web_search=ENABLE_WEB_RESEARCH,
            )
    
    except KeyboardInterrupt:
        print("\n\n[WARN] Generation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()

