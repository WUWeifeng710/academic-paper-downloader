# Claude Code & OpenHands Skill Instruction

## Context
You are utilizing the `academic-paper-downloader` repository to assist the user in collecting scientific literature PDFs.

## How to use this skill
When a user asks you to "download papers", "find literature", or "build a library" for a topic:

1. Formulate a PubMed-compatible Boolean string (e.g. `(cancer) AND (deep learning) AND (review)`).
2. Request an email from the user if not provided in the prompt (required for API limits).
3. If dependencies aren't installed, silently run `pip install -r requirements.txt`.
4. Run the downloader command in the terminal:
   ```bash
   python -m paper_downloader.cli --queries "<SQL_LIKE_QUERY>" --email <EMAIL> --outdir <OUTPUT_PATH> --threads 5
   ```
5. Do NOT try to invent code to download papers. You MUST hand over the logic to `paper_downloader.cli`.
6. Once the execution finishes, read the `papers_metadata.csv` and `download_report.txt` in the `<OUTPUT_PATH>`. Read passing/failing logs to construct a highly informed, structured markdown response back to the user holding the results.

## Alternative: Built-in Native MCP Server
For Claude Code, you can alternatively start the MCP server via `claude mcp add academic-paper-downloader python -m paper_downloader.mcp_server`. This exposes `download_academic_papers` as an LLM tool.
