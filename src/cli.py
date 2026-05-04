"""CLI interface for Creative Automation Pipeline."""
import click
import json
import asyncio
from pathlib import Path
from src import __version__
from src.pipeline import CreativeAutomationPipeline
from src.models import CampaignBrief
from src.config import get_config


@click.group()
@click.version_option(version=__version__)
def cli():
    """Creative Automation Pipeline - Reference Implementation

    Generate localized social media advertising assets using GenAI.
    """
    pass


@cli.command()
@click.option('--brief', '-b', required=True, type=click.Path(exists=True), help='Path to campaign brief JSON file')
@click.option('--backend', type=click.Choice(['firefly', 'openai', 'gemini', 'dalle', 'imagen'], case_sensitive=False), help='Override image generation backend')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--dry-run', is_flag=True, help='Validate brief without processing')
def process(brief: str, backend: str, verbose: bool, dry_run: bool):
    """Process campaign brief and generate creative assets.
    
    Example:
        python -m src.cli process --brief examples/campaign_brief.json
    """
    try:
        # Load campaign brief
        click.echo(f"\n📄 Loading campaign brief from {brief}...")
        with open(brief, 'r') as f:
            brief_data = json.load(f)
        
        # Validate with Pydantic
        campaign_brief = CampaignBrief(**brief_data)
        
        if verbose:
            click.echo(f"✓ Brief validated successfully")
            click.echo(f"  Campaign: {campaign_brief.campaign_name}")
            click.echo(f"  Products: {len(campaign_brief.products)}")
            click.echo(f"  Locales: {', '.join(campaign_brief.target_locales)}")
        
        if dry_run:
            click.echo("\n✓ Dry run complete - brief is valid")
            return
        
        # Process campaign
        pipeline = CreativeAutomationPipeline(image_backend=backend)
        output = asyncio.run(pipeline.process_campaign(campaign_brief, brief_path=brief))
        
        # Display summary
        click.echo("\n" + "="*60)
        click.echo("📊 CAMPAIGN SUMMARY")
        click.echo("="*60)
        click.echo(f"Campaign ID: {output.campaign_id}")
        click.echo(f"Total Assets: {output.total_assets}")
        click.echo(f"Processing Time: {output.processing_time_seconds:.1f}s")
        click.echo(f"Success Rate: {output.success_rate * 100:.1f}%")
        
        if output.errors:
            click.echo(f"\n⚠️  Errors encountered: {len(output.errors)}")
            for error in output.errors:
                click.echo(f"  - {error}")
        
        click.echo(f"\n✅ Output directory: {get_config().OUTPUT_DIR}/{output.campaign_id}")
        
    except json.JSONDecodeError as e:
        click.echo(f"❌ Error: Invalid JSON in brief file - {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        raise click.Abort()


@cli.command()
def validate_config():
    """Validate API keys and configuration."""
    click.echo("\n🔍 Validating configuration...")

    config = get_config()
    is_valid, errors = config.validate()

    # Show available backends
    available_backends = config.get_available_backends()

    if is_valid:
        click.echo("✅ Configuration is valid\n")
        click.echo("📡 Image Generation Backends:")
        click.echo(f"  Adobe Firefly: {'✓' if config.FIREFLY_API_KEY else '✗'}")
        click.echo(f"  OpenAI DALL-E: {'✓' if config.OPENAI_API_KEY else '✗'}")
        click.echo(f"  Google Gemini: {'✓' if config.GEMINI_API_KEY else '✗'}")
        click.echo(f"\n  Available: {', '.join(set([b.split('-')[0] for b in available_backends]))}")
        click.echo(f"  Default: {config.DEFAULT_IMAGE_BACKEND}")
        click.echo(f"\n🔤 Text Processing:")
        click.echo(f"  Claude API: {'✓' if config.CLAUDE_API_KEY else '✗'}")
        click.echo(f"\n📁 Paths:")
        click.echo(f"  Output Dir: {config.OUTPUT_DIR}")
    else:
        click.echo("❌ Configuration errors:")
        for error in errors:
            click.echo(f"  - {error}")
        raise click.Abort()


@cli.command()
def list_examples():
    """List available example campaign briefs."""
    examples_dir = Path("examples")
    
    if not examples_dir.exists():
        click.echo("❌ Examples directory not found")
        return
    
    click.echo("\n📋 Available Examples:\n")
    
    for example_file in examples_dir.glob("*.json"):
        try:
            with open(example_file, 'r') as f:
                data = json.load(f)
                click.echo(f"  • {example_file.name}")
                if 'campaign_name' in data:
                    click.echo(f"    {data['campaign_name']}")
        except (json.JSONDecodeError, KeyError, OSError):
            pass
    
    click.echo(f"\nUsage: python -m src.cli process --brief examples/campaign_brief.json\n")


@cli.command()
@click.option('--campaign-id', required=True, help='Unique campaign identifier (e.g., FALL2024)')
@click.option('--campaign-name', required=True, help='Human-readable campaign name')
@click.option('--interactive', '-i', is_flag=True, help='Interactive mode - prompt for all values')
@click.option('--output', '-o', help='Output file path (default: examples/{campaign_id}_campaign.json)')
@click.option('--brand-name', help='Brand name')
@click.option('--headline', help='Campaign headline')
@click.option('--subheadline', help='Campaign subheadline')
@click.option('--cta', help='Call to action')
def new_campaign(campaign_id, campaign_name, interactive, output, **kwargs):
    """Generate a new campaign brief from template."""
    from src.campaign_generator import CampaignGenerator

    try:
        generator = CampaignGenerator()

        # Filter out None values from kwargs
        params = {k: v for k, v in kwargs.items() if v is not None}

        output_path = generator.generate(
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            output_path=output,
            interactive=interactive,
            **params
        )

        click.echo(f"\n✅ Campaign brief created: {output_path}")
        click.echo(f"\n📝 Next steps:")
        click.echo(f"   1. Edit the file to customize products and settings")
        click.echo(f"   2. Run: python -m src.cli process --brief {output_path}")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Abort()


if __name__ == '__main__':
    cli()
