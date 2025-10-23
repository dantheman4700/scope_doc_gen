"""
Example usage script for scope document generator.

This demonstrates different ways to use the generator.
"""

from pathlib import Path
from scope_doc_gen.main import ScopeDocGenerator

# Example 1: Basic usage with default settings
def basic_generation():
    """Generate a scope document from default input_docs/ folder."""
    print("Example 1: Basic Generation")
    print("-" * 40)
    
    generator = ScopeDocGenerator()
    output_path = generator.generate()
    
    print(f"\nGenerated document: {output_path}")


# Example 2: Custom input/output directories
def custom_directories():
    """Generate with custom input and output directories."""
    print("\nExample 2: Custom Directories")
    print("-" * 40)
    
    generator = ScopeDocGenerator(
        input_dir=Path("./my_custom_inputs"),
        output_dir=Path("./my_custom_outputs")
    )
    
    output_path = generator.generate()
    print(f"\nGenerated document: {output_path}")


# Example 3: Interactive refinement
def interactive_generation():
    """Generate with interactive refinement of variables."""
    print("\nExample 3: Interactive Generation")
    print("-" * 40)
    
    generator = ScopeDocGenerator()
    output_path = generator.generate(interactive=True)
    
    print(f"\nGenerated document: {output_path}")


# Example 4: Two-stage process (extract then render)
def two_stage_generation():
    """Extract variables, review/edit them, then generate document."""
    print("\nExample 4: Two-Stage Generation")
    print("-" * 40)
    
    generator = ScopeDocGenerator()
    
    # Stage 1: Extract variables
    print("\nStage 1: Extracting variables...")
    output_path = generator.generate(save_intermediate=True)
    
    # At this point, you can edit: generated_scopes/extracted_variables.json
    print("\n[Manual Step: Edit extracted_variables.json if needed]")
    
    # Stage 2: Generate from edited variables
    print("\nStage 2: Generating from variables...")
    variables_file = Path("generated_scopes/extracted_variables.json")
    output_path = generator.generate_from_variables(variables_file)
    
    print(f"\nFinal document: {output_path}")


# Example 5: Programmatic variable extraction
def programmatic_usage():
    """Use the components programmatically for custom workflows."""
    print("\nExample 5: Programmatic Usage")
    print("-" * 40)
    
    from scope_doc_gen import DocumentIngester, ClaudeExtractor, TemplateRenderer
    from scope_doc_gen.config import (
        TEMPLATE_PATH,
        VARIABLES_SCHEMA_PATH,
        VARIABLES_GUIDE_PATH,
        INPUT_DOCS_DIR
    )
    import json
    
    # Load schemas
    with open(VARIABLES_SCHEMA_PATH, 'r') as f:
        schema = json.load(f)
    with open(VARIABLES_GUIDE_PATH, 'r') as f:
        guide = json.load(f)
    
    # Step 1: Ingest documents
    ingester = DocumentIngester()
    documents = ingester.ingest_directory(INPUT_DOCS_DIR)
    combined = ingester.combine_documents(documents)
    
    # Step 2: Extract with Claude
    extractor = ClaudeExtractor()
    variables = extractor.extract_variables(combined, schema, guide)
    
    # Step 3: Custom processing of variables
    # (Add your custom logic here)
    print(f"\nExtracted {len(variables)} variables")
    
    # Step 4: Render template
    renderer = TemplateRenderer(TEMPLATE_PATH)
    rendered = renderer.render(variables)
    
    # Step 5: Save
    output_path = Path("generated_scopes/custom_output.md")
    renderer.save(rendered, output_path)
    
    print(f"\nGenerated document: {output_path}")


if __name__ == "__main__":
    """Run examples (uncomment the ones you want to try)."""
    
    # Choose which example to run:
    
    basic_generation()
    # custom_directories()
    # interactive_generation()
    # two_stage_generation()
    # programmatic_usage()

