---
name: academic-paper-downloader
description: Search, collect, and batch download academic papers (PDF) from PMC, PubMed, Crossref, OpenAlex + Unpaywall + 11 publisher patterns (Elsevier/Springer/Wiley/OUP/ACS/PNAS/PLOS etc). Use when the user asks to find papers, download literature, collect references, build a literature library, or do a literature search on any research topic.
---

# Academic Paper Downloader v3

Multi-source search and batch download of academic literature PDFs.

Search sources: PMC, PubMed, Crossref, OpenAlex (250M+ works).
Download strategies: PMC OA, Europe PMC, Unpaywall, OpenAlex OA links, 11 publisher URL patterns.

## Workflow

### Phase 1: Clarify Requirements

Use AskUserQuestion to gather:

1. **Research topic**: Keywords, organisms, genes, diseases, methods
2. **Scope**: Broad survey vs. focused sub-topic
3. **Language**: English / Chinese / both (note: Chinese databases not yet supported)
4. **Quantity**: 10-20 (精选) / 20-50 / 50+
5. **Institutional access**: Whether their IP has publisher access (Elsevier, Springer, etc.)
6. **Output folder**: Where to save (default: user's selected folder)

### Phase 2: Build Search Queries

Write queries in PubMed Boolean format (used by PMC + PubMed). The script auto-converts these to plain text for Crossref and OpenAlex.

**Design principles:**

- Boolean: `AND`, `OR`, parentheses
- Include domain-specific terms: gene names, pathogen names, method keywords
- One query with `(review OR comprehensive)` for review articles
- 15-30 queries for broad topics, `retmax=30` each
- Optionally set `CROSSREF_QUERIES` / `OPENALEX_QUERIES` for source-specific tuning

### Phase 3: Configure and Run

Customize the script's configuration block:

```python
OUTPUT_DIR = r"path\to\output"
UNPAYWALL_EMAIL = "academic.downloader@outlook.com"  # Must not be @example.com
HAS_INSTITUTIONAL_ACCESS = True   # Set True if user confirms
SEARCH_QUERIES = [...]            # PubMed Boolean queries
CROSSREF_QUERIES = []             # Optional; auto-derived if empty
OPENALEX_QUERIES = []             # Optional; auto-derived if empty
OTHER_PAPERS = [{"url": "...", "title": "..."}]  # Direct PDF URLs
```

Run:
```bash
pip install requests -q
python scripts/download_papers.py
```

The script executes 4 phases automatically:
1. **PMC OA** (3 OA strategies + Unpaywall/publisher fallback)
2. **PubMed-only** via Unpaywall + publisher
3. **Crossref-only** via Unpaywall + publisher
4. **OpenAlex-only** (built-in OA URLs + Unpaywall + publisher)

Runtime: 20-60 min for 500+ articles. Use `run_in_background=true`.

### Phase 4: Supplement with WebSearch

Search for additional PDF URLs not found by the 4 sources. Add to `OTHER_PAPERS`.

### Phase 5: Report

Auto-generated `download_report.txt` in output folder with per-channel statistics.

## Download Strategy Chain

```
For each article (by DOI):
  1. OpenAlex OA PDF URL (if available from search)
  2. Unpaywall API -> best OA PDF URL
  3. Publisher-specific URL patterns (11 publishers)

For PMC articles additionally (before DOI chain):
  1. NCBI OA Service API
  2. Direct PMC PDF endpoint
  3. Europe PMC renderer
```

### Supported Publisher Patterns (v3)

| Publisher | URL Pattern | Notes |
|-----------|-------------|-------|
| Springer/Nature/BMC | `link.springer.com/content/pdf/{DOI}.pdf` | Institutional IP recommended |
| Wiley | `onlinelibrary.wiley.com/doi/pdfdirect/{DOI}` | Has bot protection |
| Taylor & Francis | `tandfonline.com/doi/pdf/{DOI}` | Institutional IP recommended |
| Elsevier | `api.elsevier.com/content/article/doi/{DOI}` | PDF Accept header |
| Oxford University Press | `academic.oup.com/doi/pdf/{DOI}` | Institutional IP recommended |
| Cambridge Univ Press | `cambridge.org/core/.../content/view/{DOI}` | |
| Annual Reviews | `annualreviews.org/doi/pdf/{DOI}` | |
| PNAS | `pnas.org/doi/pdf/{DOI}` | |
| PLOS | `journals.plos.org/.../file?id={DOI}&type=printable` | All OA |
| ACS | `pubs.acs.org/doi/pdf/{DOI}` | Institutional IP required |
| RSC | `pubs.rsc.org/en/content/articlepdf/{DOI}` | |
| MDPI | `mdpi.com/{DOI}/pdf` | All OA; has bot protection |

### Key APIs

**Crossref** (`api.crossref.org/works`): Searches all scholarly DOIs across disciplines. Not limited to biomedical. Polite pool via `mailto:` header. Returns DOI, title, authors, journal.

**OpenAlex** (`api.openalex.org/works`): 250M+ works index. Returns OA status and direct PDF URLs when available. Free, no key needed. `mailto` parameter for polite pool.

**Unpaywall** (`api.unpaywall.org/v2/{DOI}`): Finds best available OA PDF for a DOI. Email must NOT be `@example.com`. Default: `academic.downloader@outlook.com`. 100k requests/day.

### Rate Limiting

- NCBI: 3 req/sec (no key), 10/sec (with key)
- Crossref: polite pool with `mailto:` header (~50 req/sec)
- OpenAlex: 100k req/day with `mailto`
- Unpaywall: 100k req/day
- Script uses conservative sleeps: 0.3-0.8s between requests

### Robustness

- `robust_get()`: SSL retry with `verify=False` fallback
- Global DOI dedup: `all_dois_downloaded` + `all_dois_attempted` sets prevent re-downloading and re-attempting
- PubMed Boolean auto-conversion to plain text for Crossref/OpenAlex via `pubmed_to_plain()`

## Limitations

- **No Chinese databases**: CNKI, Wanfang, VIP need browser automation (future)
- **Publisher bot protection**: Wiley, MDPI sometimes block even OA papers
- **Expected success rate**: ~50-60% without institutional IP, ~70-85% with institutional IP
- **Crossref/OpenAlex overlap**: Some papers appear in multiple sources; handled via DOI dedup

## Additional Resources

For the complete download script template, see [scripts/download_papers.py](scripts/download_papers.py).
