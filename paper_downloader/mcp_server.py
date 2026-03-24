import os
import sys

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("mcp package is not installed. Please install it via `pip install mcp`", file=sys.stderr)
    sys.exit(1)

from .downloader import BatchDownloader
from .utils import logger

# Initialize FastMCP Server
mcp = FastMCP("Academic Paper Downloader MCP")

@mcp.tool()
def download_academic_papers(query: str, email: str, outdir: str = "./mcp_papers", threads: int = 5, retmax: int = 30) -> str:
    """
    Search and download academic papers using PubMed, Crossref, and OpenAlex.
    Retrieves Open Access PDFs automatically.
    
    Args:
        query: The Boolean search string (e.g., '(tomato) AND (disease resistance)').
        email: Your email address for the Unpaywall / Crossref polite pool.
        outdir: The directory to save the downloaded PDFs and CSV metadata.
        threads: Concurrency level.
        retmax: Max hits per API source.
    """
    logger.info(f"MCP Tool Triggered: Downloading papers for '{query}'...")
    
    downloader = BatchDownloader(
        outdir=outdir,
        email=email,
        threads=threads,
        retmax=retmax,
        institutional=False
    )
    
    # Run the orchestrator
    downloader.run([query])
    
    report_path = os.path.abspath(os.path.join(outdir, "download_report.txt"))
    csv_path = os.path.abspath(os.path.join(outdir, "papers_metadata.csv"))
    
    return f"Execution finished successfully. Reports and metadata exported to:\n- {report_path}\n- {csv_path}\nPlease review the CSV file to inform the user of the literature downloaded."

if __name__ == "__main__":
    import logging
    # FastMCP takes over stdio, so we must limit our custom logger stdout interference
    logger.setLevel(logging.CRITICAL)
    mcp.run()
