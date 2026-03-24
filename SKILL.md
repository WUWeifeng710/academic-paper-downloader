---
name: academic-paper-downloader
description: Use when the user asks to find papers, download literature, collect references, or build a literature library. This is a powerful multi-source CLI downloader supporting PMC, PubMed, Crossref, OpenAlex, Unpaywall, and Publisher scraping.
---

# Academic Paper Batch Downloader

A highly concurrent, resilient CLI tool for downloading academic literature PDFs from multiple sources (PMC, PubMed, Crossref, OpenAlex, etc.) and aggregating open-access links via Unpaywall.

## Agent Usage Instructions

When the user asks you to download papers or do a literature search:

1. **Clarify Requirements (if needed)**:
    - Keywords / Boolean Search Query (e.g., `(tomato) AND (disease resistance breeding) AND (review)`)
    - Their Email (Required for Unpaywall). Tell them exactly why it's needed (fair-use polite pool). Do not use `@example.com`.
    - Whether they have Institutional PDF Access (optional, defaults to false)
    - Target output directory (where the files and report CSV will be saved)

2. **Installation (First Time Only)**:
   Navigate to the project root where `project_downloader` resides and run:
   ```bash
   pip install -r requirements.txt
   ```

3. **Execution**:
   Run the module programmatically:
   ```bash
   python -m paper_downloader.cli --queries "<USER_QUERY>" --email <USER_EMAIL> --outdir <OUTPUT_PATH> --threads 5
   ```

   **CLI Arguments**:
   - `--queries`: Search query (PubMed Boolean style).
   - `--email`: Valid email string for API cross-requests.
   - `--outdir`: Absolute path to export PDFs and CSV report.
   - `--threads`: (Optional) concurrency level 1-10.
   - `--retmax`: (Optional) max search results per engine (default 30).
   - `--institutional`: (Optional) flag if user has publisher PDF institutional access.

4. **Monitoring**:
   The script manages state (via local JSON cache) and automatically skips successfully downloaded PDFs on rerun. Read the generated `download_report.txt` and `papers_metadata.csv` to format a nice summary response for the user after the command completes.

## Limitations
- Chinese local databases (CNKI/Wanfang) are not supported.
- `mdpi`/`wiley` anti-bot measures might block a tiny fraction of PDFs without institutional networks or proxy.
