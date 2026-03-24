"""
Academic Paper Batch Downloader v3
===================================
Multi-source search and download: PMC, PubMed, Crossref, OpenAlex + Unpaywall + Publishers.

v3 additions:
  - Crossref API: keyword search across all scholarly DOIs (not limited to biomedical)
  - OpenAlex API: 250M+ works index with built-in OA status and PDF links
  - Extended publisher patterns: OUP, Cambridge, ACS, Annual Reviews, PNAS, PLOS, etc.
  - Unified deduplication by DOI across all sources

Usage:
  1. Set OUTPUT_DIR, UNPAYWALL_EMAIL, HAS_INSTITUTIONAL_ACCESS
  2. Customize SEARCH_QUERIES for your research topic
  3. Run: python download_papers.py

Dependencies: pip install requests
"""

import requests
import requests.packages.urllib3
import xml.etree.ElementTree as ET
import os
import sys
import time
import json
import re
from datetime import date
from urllib.parse import quote

# Suppress SSL warnings when verify=False is used as fallback
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ============================================================
# CONFIGURATION - Customize these for each task
# ============================================================

# Output directory for downloaded PDFs
OUTPUT_DIR = r"C:\Users\wuwei\Desktop\papers"

# Email for Unpaywall & OpenAlex (must NOT be @example.com)
UNPAYWALL_EMAIL = "academic.downloader@outlook.com"

# PMC/PubMed/Crossref/OpenAlex search queries - customize for your topic
SEARCH_QUERIES = [
    '(tomato) AND (disease resistance breeding) AND (review)',
    '(tomato) AND (molecular breeding) AND (disease resistance)',
]

# Crossref-specific queries (plain text, not PubMed Boolean syntax)
# Leave empty to auto-derive from SEARCH_QUERIES
CROSSREF_QUERIES = []

# OpenAlex-specific queries (plain text search)
# Leave empty to auto-derive from SEARCH_QUERIES
OPENALEX_QUERIES = []

# Direct PDF URLs from other sources
OTHER_PAPERS = []

# Max results per query per source
RETMAX_PER_QUERY = 30

# Set True if your IP has institutional access to publishers
HAS_INSTITUTIONAL_ACCESS = False

# ============================================================
# CORE ENGINE
# ============================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)
downloaded = []
failed = []
all_dois_downloaded = set()  # Global DOI dedup
all_dois_attempted = set()   # Avoid re-attempting same DOI
stats = {"pmc_oa": 0, "unpaywall": 0, "openalex_oa": 0,
         "publisher": 0, "direct": 0, "cached": 0}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
}


def sanitize_filename(name, max_len=120):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    name = name.strip('. ')
    return name[:max_len].strip() if len(name) > max_len else name


def robust_get(url, timeout=90, **kwargs):
    """GET with retry + SSL fallback."""
    for attempt in range(2):
        try:
            r = requests.get(url, timeout=timeout, headers=HEADERS,
                             allow_redirects=True, verify=(attempt == 0), **kwargs)
            return r
        except requests.exceptions.SSLError:
            if attempt == 0:
                continue
        except Exception:
            pass
    return None


def is_valid_pdf(content):
    return content and b'%PDF' in content[:20] and len(content) > 5000


# ============================================================
# SEARCH SOURCE 1: PMC (open-access full text)
# ============================================================

def search_pmc(query, retmax=30):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": "pmc", "term": query, "retmax": retmax,
              "retmode": "json", "sort": "relevance"}
    try:
        r = requests.get(url, params=params, timeout=30, headers=HEADERS)
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        print(f"  [PMC]      {len(ids):>3} hits: {query[:60]}...")
        return ids
    except Exception as e:
        print(f"  [PMC]      error: {e}")
        return []


def get_pmc_details(pmc_ids):
    if not pmc_ids:
        return []
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    articles = []
    for i in range(0, len(pmc_ids), 15):
        batch = pmc_ids[i:i + 15]
        params = {"db": "pmc", "id": ",".join(batch), "retmode": "json"}
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=30, headers=HEADERS)
                result = r.json().get("result", {})
                for pid in batch:
                    info = result.get(pid, {})
                    if isinstance(info, dict) and "title" in info:
                        articles.append({
                            "pmcid": f"PMC{pid}", "origin": "pmc",
                            "title": info.get("title", ""),
                            "authors": info.get("sortfirstauthor", ""),
                            "source": info.get("source", ""),
                            "pubdate": info.get("pubdate", ""),
                            "doi": info.get("doi", ""),
                        })
                break
            except Exception as e:
                print(f"    metadata error (attempt {attempt+1}): {e}")
                time.sleep(2)
        time.sleep(0.5)
    return articles


# ============================================================
# SEARCH SOURCE 2: PubMed (all indexed biomedical literature)
# ============================================================

def search_pubmed(query, retmax=30):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": "pubmed", "term": query, "retmax": retmax,
              "retmode": "json", "sort": "relevance"}
    try:
        r = requests.get(url, params=params, timeout=30, headers=HEADERS)
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        print(f"  [PubMed]   {len(ids):>3} hits: {query[:60]}...")
        return ids
    except Exception as e:
        print(f"  [PubMed]   error: {e}")
        return []


def get_pubmed_details(pmids):
    if not pmids:
        return []
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    articles = []
    for i in range(0, len(pmids), 15):
        batch = pmids[i:i + 15]
        params = {"db": "pubmed", "id": ",".join(batch), "retmode": "json"}
        for attempt in range(3):
            try:
                r = requests.get(url, params=params, timeout=30, headers=HEADERS)
                result = r.json().get("result", {})
                for pid in batch:
                    info = result.get(pid, {})
                    if isinstance(info, dict) and "title" in info:
                        doi = ""
                        for aid in info.get("articleids", []):
                            if aid.get("idtype") == "doi":
                                doi = aid.get("value", "")
                                break
                        if doi:
                            articles.append({
                                "pmid": pid, "origin": "pubmed",
                                "title": info.get("title", ""),
                                "authors": info.get("sortfirstauthor", ""),
                                "source": info.get("source", ""),
                                "pubdate": info.get("pubdate", ""),
                                "doi": doi,
                            })
                break
            except Exception as e:
                print(f"    PubMed metadata error (attempt {attempt+1}): {e}")
                time.sleep(2)
        time.sleep(0.5)
    return articles


# ============================================================
# SEARCH SOURCE 3: Crossref (all scholarly DOIs, any discipline)
# ============================================================

def search_crossref(query, rows=30):
    """Search Crossref for works matching query. Returns list of article dicts."""
    url = "https://api.crossref.org/works"
    params = {
        "query": query,
        "rows": rows,
        "sort": "relevance",
        "filter": "type:journal-article",
        "select": "DOI,title,author,container-title,published-print,published-online",
    }
    cr_headers = {**HEADERS, 'User-Agent': f'AcademicDownloader/3.0 (mailto:{UNPAYWALL_EMAIL})'}
    try:
        r = requests.get(url, params=params, timeout=30, headers=cr_headers)
        if r.status_code != 200:
            print(f"  [Crossref] HTTP {r.status_code}: {query[:60]}...")
            return []
        items = r.json().get("message", {}).get("items", [])
        articles = []
        for item in items:
            doi = item.get("DOI", "")
            title_list = item.get("title", [])
            title = title_list[0] if title_list else ""
            if doi and title:
                # Extract first author
                authors = item.get("author", [])
                first_author = ""
                if authors:
                    a = authors[0]
                    first_author = f"{a.get('family', '')} {a.get('given', '')}".strip()
                # Extract journal
                journal_list = item.get("container-title", [])
                journal = journal_list[0] if journal_list else ""
                # Extract year
                pub = item.get("published-print") or item.get("published-online") or {}
                parts = pub.get("date-parts", [[]])
                year = str(parts[0][0]) if parts and parts[0] else ""
                articles.append({
                    "doi": doi, "origin": "crossref",
                    "title": title, "authors": first_author,
                    "source": journal, "pubdate": year,
                })
        print(f"  [Crossref] {len(articles):>3} hits: {query[:60]}...")
        return articles
    except Exception as e:
        print(f"  [Crossref] error: {e}")
        return []


# ============================================================
# SEARCH SOURCE 4: OpenAlex (250M+ works, with OA info)
# ============================================================

def search_openalex(query, per_page=30):
    """Search OpenAlex for works. Returns articles with OA PDF links if available."""
    url = "https://api.openalex.org/works"
    params = {
        "search": query,
        "per_page": per_page,
        "sort": "relevance_score:desc",
        "filter": "type:article",
        "mailto": UNPAYWALL_EMAIL,
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200:
            print(f"  [OpenAlex] HTTP {r.status_code}: {query[:60]}...")
            return []
        results = r.json().get("results", [])
        articles = []
        for item in results:
            doi = (item.get("doi") or "").replace("https://doi.org/", "")
            title = item.get("title", "")
            if not doi or not title:
                continue

            # Extract OA PDF URL
            oa_url = None
            best_oa = item.get("best_oa_location") or {}
            if best_oa.get("pdf_url"):
                oa_url = best_oa["pdf_url"]
            else:
                for loc in item.get("locations", []):
                    if loc.get("pdf_url"):
                        oa_url = loc["pdf_url"]
                        break

            # Extract first author
            authorships = item.get("authorships", [])
            first_author = ""
            if authorships:
                first_author = authorships[0].get("author", {}).get("display_name", "")

            # Extract journal
            source_info = (item.get("primary_location") or {}).get("source") or {}
            journal = source_info.get("display_name", "")

            year = str(item.get("publication_year", ""))

            articles.append({
                "doi": doi, "origin": "openalex",
                "title": title, "authors": first_author,
                "source": journal, "pubdate": year,
                "oa_pdf_url": oa_url,
            })
        print(f"  [OpenAlex] {len(articles):>3} hits: {query[:60]}...")
        return articles
    except Exception as e:
        print(f"  [OpenAlex] error: {e}")
        return []


# ============================================================
# UNPAYWALL
# ============================================================

def query_unpaywall(doi):
    if not doi:
        return None
    url = f"https://api.unpaywall.org/v2/{doi}?email={UNPAYWALL_EMAIL}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        candidates = []
        best = data.get("best_oa_location")
        if best:
            candidates.append(best)
        for loc in data.get("oa_locations", []):
            if loc not in candidates:
                candidates.append(loc)
        for loc in candidates:
            if loc.get("url_for_pdf"):
                return {"pdf_url": loc["url_for_pdf"],
                        "source": loc.get("evidence", ""),
                        "host": loc.get("host_type", "")}
    except Exception:
        pass
    return None


# ============================================================
# PUBLISHER-SPECIFIC PDF DOWNLOAD (extended for v3)
# ============================================================

def try_publisher_pdf(doi):
    """Try known publisher PDF URL patterns. Works best with institutional IP."""
    if not doi:
        return None

    patterns = [
        # Springer / Nature / BMC
        f"https://link.springer.com/content/pdf/{doi}.pdf",
        # Wiley
        f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}",
        # Taylor & Francis
        f"https://www.tandfonline.com/doi/pdf/{doi}",
        # Oxford University Press
        f"https://academic.oup.com/doi/pdf/{doi}",
        # Cambridge University Press
        f"https://www.cambridge.org/core/services/aop-cambridge-core/content/view/{doi}",
        # Annual Reviews
        f"https://www.annualreviews.org/doi/pdf/{doi}",
        # PNAS
        f"https://www.pnas.org/doi/pdf/{doi}",
        # PLOS (all OA)
        f"https://journals.plos.org/plosone/article/file?id={doi}&type=printable",
        # ACS (American Chemical Society)
        f"https://pubs.acs.org/doi/pdf/{doi}",
        # Royal Society of Chemistry
        f"https://pubs.rsc.org/en/content/articlepdf/{doi}",
        # MDPI (all OA)
        f"https://www.mdpi.com/{doi}/pdf",
    ]

    for url in patterns:
        r = robust_get(url, timeout=60)
        if r and r.status_code == 200 and is_valid_pdf(r.content):
            return r.content

    # Elsevier / ScienceDirect - special Accept header
    try:
        h = {**HEADERS, 'Accept': 'application/pdf'}
        r = requests.get(f"https://api.elsevier.com/content/article/doi/{doi}",
                         headers=h, timeout=60, allow_redirects=True)
        if r.status_code == 200 and is_valid_pdf(r.content):
            return r.content
    except Exception:
        pass

    # Elsevier fallback: ScienceDirect redirect
    try:
        r = robust_get(f"https://www.sciencedirect.com/science/article/pii/doi/{doi}")
        if r and r.status_code == 200:
            # Look for PDF link in redirect chain
            pdf_url = r.url.replace("/article/", "/article/pii/") + "/pdfft"
            r2 = robust_get(pdf_url, timeout=60)
            if r2 and r2.status_code == 200 and is_valid_pdf(r2.content):
                return r2.content
    except Exception:
        pass

    return None


# ============================================================
# DOWNLOAD ORCHESTRATOR
# ============================================================

def download_pmc_pdf(pmcid, title):
    """PMC open-access download (3 strategies)."""
    filename = sanitize_filename(f"{pmcid}_{title}") + ".pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        return filepath, "cached"

    for fn in [_try_ncbi_oa, _try_pmc_direct, _try_europepmc]:
        content = fn(pmcid)
        if content and is_valid_pdf(content):
            with open(filepath, 'wb') as f:
                f.write(content)
            return filepath, "pmc_oa"
    return None, None


def _try_ncbi_oa(pmcid):
    try:
        r = requests.get(f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}",
                         timeout=30, headers=HEADERS)
        root = ET.fromstring(r.content)
        for link in root.iter('link'):
            if link.get('format') == 'pdf':
                href = link.get('href', '')
                if href.startswith('ftp://'):
                    href = href.replace('ftp://ftp.ncbi.nlm.nih.gov/',
                                        'https://ftp.ncbi.nlm.nih.gov/')
                pdf_r = requests.get(href, timeout=90, headers=HEADERS)
                if pdf_r.status_code == 200 and len(pdf_r.content) > 1000:
                    return pdf_r.content
    except Exception:
        pass
    return None


def _try_pmc_direct(pmcid):
    try:
        r = requests.get(f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/",
                         headers=HEADERS, timeout=90, allow_redirects=True)
        if r.status_code == 200 and b'%PDF' in r.content[:20]:
            return r.content
    except Exception:
        pass
    return None


def _try_europepmc(pmcid):
    try:
        r = requests.get(f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf",
                         headers=HEADERS, timeout=90, allow_redirects=True)
        if r.status_code == 200 and b'%PDF' in r.content[:20]:
            return r.content
    except Exception:
        pass
    return None


def download_via_doi(doi, title, oa_pdf_url=None):
    """Multi-strategy DOI download: OpenAlex OA -> Unpaywall -> Publisher."""
    if not doi or doi.lower() in all_dois_attempted:
        return None, None
    all_dois_attempted.add(doi.lower())

    filename = sanitize_filename(f"DOI_{doi.replace('/', '_')}_{title}") + ".pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
        return filepath, "cached"

    # Strategy 1: OpenAlex-provided OA PDF URL (if available)
    if oa_pdf_url:
        r = robust_get(oa_pdf_url, timeout=90)
        if r and r.status_code == 200 and is_valid_pdf(r.content):
            with open(filepath, 'wb') as f:
                f.write(r.content)
            return filepath, "openalex_oa"

    # Strategy 2: Unpaywall
    uw = query_unpaywall(doi)
    if uw and uw.get("pdf_url"):
        r = robust_get(uw["pdf_url"], timeout=90)
        if r and r.status_code == 200 and is_valid_pdf(r.content):
            with open(filepath, 'wb') as f:
                f.write(r.content)
            return filepath, "unpaywall"

    # Strategy 3: Publisher-specific URL patterns
    content = try_publisher_pdf(doi)
    if content:
        with open(filepath, 'wb') as f:
            f.write(content)
        return filepath, "publisher"

    return None, None


def download_direct_pdf(url, title):
    r = robust_get(url, timeout=90)
    if r and r.status_code == 200 and is_valid_pdf(r.content):
        filename = sanitize_filename(title) + ".pdf"
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, 'wb') as f:
            f.write(r.content)
        return filepath
    return None


def record_download(article, filepath, channel):
    stats[channel] = stats.get(channel, 0) + 1
    entry = {k: v for k, v in article.items() if k != 'oa_pdf_url'}
    entry["channel"] = channel
    entry["file"] = os.path.basename(filepath)
    downloaded.append(entry)
    doi = article.get('doi', '')
    if doi:
        all_dois_downloaded.add(doi.lower())


def record_failure(article):
    entry = {k: v for k, v in article.items()
             if k in ('title', 'doi', 'pmcid', 'pmid', 'authors', 'source')}
    failed.append(entry)


# ============================================================
# REPORT
# ============================================================

def save_report():
    report_path = os.path.join(OUTPUT_DIR, "download_report.txt")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("Literature Download Report (v3)\n")
        f.write("=" * 60 + "\n")
        f.write(f"Date: {date.today()}\n")
        f.write(f"Downloaded: {len(downloaded)} | Failed: {len(failed)}\n")
        f.write(f"Channels: " + ", ".join(f"{k}={v}" for k, v in stats.items() if v > 0) + "\n\n")

        f.write("=" * 60 + "\n")
        f.write("Downloaded Papers\n")
        f.write("=" * 60 + "\n\n")
        for i, d in enumerate(downloaded, 1):
            f.write(f"{i}. {d.get('title', 'N/A')}\n")
            for key, label in [('pmcid', 'PMCID'), ('pmid', 'PMID'),
                               ('authors', 'Authors'), ('source', 'Journal'),
                               ('doi', 'DOI'), ('channel', 'Channel')]:
                if d.get(key):
                    f.write(f"   {label}: {d[key]}\n")
            f.write(f"   File: {d.get('file', 'N/A')}\n\n")

        if failed:
            f.write("\n" + "=" * 60 + "\n")
            f.write("Failed Downloads\n")
            f.write("=" * 60 + "\n\n")
            for i, d in enumerate(failed, 1):
                f.write(f"{i}. {d.get('title', 'N/A')}\n")
                for key, label in [('pmcid', 'PMCID'), ('pmid', 'PMID'), ('doi', 'DOI')]:
                    if d.get(key):
                        f.write(f"   {label}: {d[key]}\n")
                f.write("\n")
    print(f"Report saved: {report_path}")


# ============================================================
# QUERY CONVERSION: PubMed Boolean -> plain text for Crossref/OpenAlex
# ============================================================

def pubmed_to_plain(query):
    """Convert PubMed Boolean query to plain text for Crossref/OpenAlex."""
    q = query.replace("(", "").replace(")", "")
    q = re.sub(r'\bAND\b', ' ', q, flags=re.IGNORECASE)
    q = re.sub(r'\bOR\b', ' ', q, flags=re.IGNORECASE)
    q = re.sub(r'"', '', q)
    return re.sub(r'\s+', ' ', q).strip()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Academic Paper Batch Downloader v3")
    print(f"Sources: PMC + PubMed + Crossref + OpenAlex")
    print(f"Unpaywall: ON | Institutional: {'ON' if HAS_INSTITUTIONAL_ACCESS else 'OFF'}")
    print("=" * 60)

    # Derive Crossref/OpenAlex queries if not set
    crossref_queries = CROSSREF_QUERIES or [pubmed_to_plain(q) for q in SEARCH_QUERIES]
    openalex_queries = OPENALEX_QUERIES or [pubmed_to_plain(q) for q in SEARCH_QUERIES]

    # ===========================================================
    # PHASE 1: Search all sources and collect article metadata
    # ===========================================================
    print("\n--- Searching all sources ---")

    all_pmc_ids = set()
    all_pubmed_ids = set()

    for query in SEARCH_QUERIES:
        ids = search_pmc(query, retmax=RETMAX_PER_QUERY)
        all_pmc_ids.update(ids)
        time.sleep(0.4)
        ids = search_pubmed(query, retmax=RETMAX_PER_QUERY)
        all_pubmed_ids.update(ids)
        time.sleep(0.4)

    crossref_articles = []
    for query in crossref_queries:
        arts = search_crossref(query, rows=RETMAX_PER_QUERY)
        crossref_articles.extend(arts)
        time.sleep(0.5)

    openalex_articles = []
    for query in openalex_queries:
        arts = search_openalex(query, per_page=RETMAX_PER_QUERY)
        openalex_articles.extend(arts)
        time.sleep(0.3)

    print(f"\nSearch totals:")
    print(f"  PMC IDs      : {len(all_pmc_ids)}")
    print(f"  PubMed IDs   : {len(all_pubmed_ids)}")
    print(f"  Crossref     : {len(crossref_articles)}")
    print(f"  OpenAlex     : {len(openalex_articles)}")

    # Fetch NCBI metadata
    print("\nFetching NCBI metadata...")
    pmc_articles = get_pmc_details(list(all_pmc_ids))
    pubmed_articles = get_pubmed_details(list(all_pubmed_ids))
    print(f"  PMC articles : {len(pmc_articles)}")
    print(f"  PubMed w/DOI : {len(pubmed_articles)}")

    # ===========================================================
    # PHASE 2: Download PMC articles (OA + Unpaywall fallback)
    # ===========================================================
    print(f"\n{'=' * 60}")
    print(f"Phase 1/4: PMC open-access papers ({len(pmc_articles)})")
    print(f"{'=' * 60}")

    for i, art in enumerate(pmc_articles):
        pmcid, title, doi = art['pmcid'], art['title'], art.get('doi', '')
        print(f"[{i+1}/{len(pmc_articles)}] {title[:72]}...")

        filepath, channel = download_pmc_pdf(pmcid, title)
        if filepath:
            record_download(art, filepath, channel)
            print(f"  [OK] {channel}")
        elif doi:
            filepath2, channel2 = download_via_doi(doi, title)
            if filepath2:
                record_download(art, filepath2, channel2)
                print(f"  [OK] {channel2} (DOI fallback)")
            else:
                record_failure(art)
                print(f"  [SKIP]")
        else:
            record_failure(art)
            print(f"  [SKIP]")
        time.sleep(0.4)

    print(f"\nPhase 1 done: {len(downloaded)} downloaded")

    # ===========================================================
    # PHASE 3: PubMed-only articles via Unpaywall/Publisher
    # ===========================================================
    pubmed_new = [a for a in pubmed_articles
                  if a.get('doi', '').lower() not in all_dois_downloaded
                  and a.get('doi', '').lower() not in all_dois_attempted]

    if pubmed_new:
        print(f"\n{'=' * 60}")
        print(f"Phase 2/4: PubMed-only via Unpaywall+Publisher ({len(pubmed_new)})")
        print(f"{'=' * 60}")
        for i, art in enumerate(pubmed_new):
            doi, title = art['doi'], art['title']
            print(f"[{i+1}/{len(pubmed_new)}] {title[:72]}...")
            filepath, channel = download_via_doi(doi, title)
            if filepath:
                record_download(art, filepath, channel)
                print(f"  [OK] {channel}")
            else:
                record_failure(art)
                print(f"  [SKIP]")
            time.sleep(0.6)

    # ===========================================================
    # PHASE 4: Crossref articles via Unpaywall/Publisher
    # ===========================================================
    crossref_new = [a for a in crossref_articles
                    if a.get('doi', '').lower() not in all_dois_downloaded
                    and a.get('doi', '').lower() not in all_dois_attempted]
    # Deduplicate within crossref results
    seen = set()
    crossref_dedup = []
    for a in crossref_new:
        d = a['doi'].lower()
        if d not in seen:
            seen.add(d)
            crossref_dedup.append(a)
    crossref_new = crossref_dedup

    if crossref_new:
        print(f"\n{'=' * 60}")
        print(f"Phase 3/4: Crossref-only via Unpaywall+Publisher ({len(crossref_new)})")
        print(f"{'=' * 60}")
        for i, art in enumerate(crossref_new):
            doi, title = art['doi'], art['title']
            print(f"[{i+1}/{len(crossref_new)}] {title[:72]}...")
            filepath, channel = download_via_doi(doi, title)
            if filepath:
                record_download(art, filepath, channel)
                print(f"  [OK] {channel}")
            else:
                record_failure(art)
                print(f"  [SKIP]")
            time.sleep(0.6)

    # ===========================================================
    # PHASE 5: OpenAlex articles (use built-in OA URLs first)
    # ===========================================================
    openalex_new = [a for a in openalex_articles
                    if a.get('doi', '').lower() not in all_dois_downloaded
                    and a.get('doi', '').lower() not in all_dois_attempted]
    seen2 = set()
    openalex_dedup = []
    for a in openalex_new:
        d = a['doi'].lower()
        if d not in seen2:
            seen2.add(d)
            openalex_dedup.append(a)
    openalex_new = openalex_dedup

    if openalex_new:
        print(f"\n{'=' * 60}")
        print(f"Phase 4/4: OpenAlex-only ({len(openalex_new)})")
        print(f"{'=' * 60}")
        for i, art in enumerate(openalex_new):
            doi, title = art['doi'], art['title']
            oa_url = art.get('oa_pdf_url')
            print(f"[{i+1}/{len(openalex_new)}] {title[:72]}...")
            filepath, channel = download_via_doi(doi, title, oa_pdf_url=oa_url)
            if filepath:
                record_download(art, filepath, channel)
                print(f"  [OK] {channel}")
            else:
                record_failure(art)
                print(f"  [SKIP]")
            time.sleep(0.5)

    # ===========================================================
    # PHASE 6: Direct URLs
    # ===========================================================
    if OTHER_PAPERS:
        print(f"\n{'=' * 60}")
        print(f"Bonus: Direct URLs ({len(OTHER_PAPERS)})")
        print(f"{'=' * 60}")
        existing = set(d['title'].lower()[:50] for d in downloaded)
        for paper in OTHER_PAPERS:
            title = paper['title']
            if title.lower()[:50] in existing:
                continue
            print(f"  {title[:70]}...")
            filepath = download_direct_pdf(paper['url'], title)
            if filepath:
                stats["direct"] += 1
                downloaded.append({"title": title, "channel": "direct",
                                   "file": os.path.basename(filepath)})
                print(f"  [OK]")
            else:
                print(f"  [SKIP]")
            time.sleep(0.5)

    # ===========================================================
    # SUMMARY
    # ===========================================================
    print(f"\n{'=' * 60}")
    print(f"FINAL SUMMARY")
    print(f"{'=' * 60}")
    print(f"Downloaded : {len(downloaded)}")
    print(f"Failed     : {len(failed)}")
    print(f"Channels:")
    for ch, count in sorted(stats.items(), key=lambda x: -x[1]):
        if count > 0:
            print(f"  {ch:<14}: {count}")
    print(f"{'=' * 60}")
    save_report()
    print("Done!")
