import logging
import sys
from rich.logging import RichHandler
from rich.console import Console

# Shared console instance to ensure consistent output handling
console = Console()

def setup_logging():
    """
    Configure global logging with RichHandler for beautiful timestamps and formatting.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console, 
                rich_tracebacks=True, 
                show_time=True, 
                show_path=False
            )
        ],
        force=True
    )
    
    # Optional: Adjust third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
