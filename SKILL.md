---
name: academic-paper-downloader
description: An automated literature retrieval and open-access PDF mass-downloader. Integrates PMC, PubMed, Crossref, OpenAlex, and Unpaywall API. Best used when the user needs to find, collect, or download academic papers based on a research query.
version: 1.0.0
author: WUWeifeng710
tags:
  - academic
  - literature
  - python
  - automation
  - research
---

# Academic Paper Downloader Skill

You are an AI programming assistant/agent equipped with the `academic-paper-downloader` skill. 

## 🛠 Prerequisites (Environment Setup)
Before executing this skill, ensure the environment has the necessary Python dependencies. Execute the following command silently:
```bash
pip install requests colorlog tqdm
```

## 🎯 When to Use This Skill
Activate this skill whenever the user asks to:
1. Search for academic papers or scientific literature.
2. Download PDFs for a specific research topic (e.g., "Find me literature on tomato disease resistance").
3. Build a local paper database.

## 🚀 Execution Instructions

### Step 1: Gather Parameters
To run the underlying Python tool, you must determine:
- **`--queries`**: Formulate a high-quality PubMed-style Boolean search query based on the user's intent. (e.g., `"(tomato) AND (disease resistance)"`)
- **`--email`**: An email address is REQUIRED by the Crossref/Unpaywall APIs. Ask the user for their email if missing, or use a placeholder if appropriate, but under NO circumstances use `@example.com`.
- **`--outdir`**: Create a logical directory name for the output (e.g., `./papers_out`).
- **`--threads`**: Recommended value is `5`.

### Step 2: Run the Downloader Tool
Run the tool using the following CLI command:
```bash
python -m paper_downloader.cli --queries "<YOUR_BOOLEAN_QUERY>" --email <EMAIL> --outdir <OUT_DIR> --threads 5
```

### Step 3: Parse and Report Results
Once the CLI tool finishes executing, it will generate two files in the `<OUT_DIR>`:
1. `download_report.txt`: A human-readable text summary of successful and failed downloads.
2. `papers_metadata.csv`: A strictly formatted CSV file of all retrieved paper metadata.

**Your final action:** 
Read `download_report.txt` and `papers_metadata.csv`. Present a concise, beautifully formatted Markdown summary to the user, listing the titles, DOIs, and channels of the successfully downloaded papers, along with the absolute path where they have been saved on the user's local machine.

## ⚠️ Constraints & Guidelines
- **Do not invent papers**: Only report what is actually written in the `papers_metadata.csv` file. 
- **Graceful Failure**: If the command fails, read the terminal output or log files and suggest corrections to the user.
