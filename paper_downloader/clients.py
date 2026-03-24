import requests
import requests.packages.urllib3
import xml.etree.ElementTree as ET
import time
import re
from .utils import logger

# Suppress SSL warnings when verify=False is used as fallback
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
}

def robust_get(url, timeout=90, **kwargs):
    """GET with retry + SSL fallback."""
    for attempt in range(2):
        try:
            r = requests.get(url, timeout=timeout, headers=HEADERS,
                             allow_redirects=True, verify=(attempt == 0), **kwargs)
            return r
        except requests.exceptions.SSLError:
            if attempt == 0:
                logger.warning(f"SSL Error for {url}. Retrying with verify=False")
                continue
        except requests.exceptions.RequestException as e:
            logger.debug(f"Request failed for {url}: {e}")
            pass
    return None

class PaperSearchClients:
    def __init__(self, unpaywall_email):
        self.unpaywall_email = unpaywall_email
        self.crossref_headers = {**HEADERS, 'User-Agent': f'AcademicDownloader/4.0 (mailto:{unpaywall_email})'}

    # ========================== PMC ==========================
    def search_pmc(self, query, retmax=30):
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {"db": "pmc", "term": query, "retmax": retmax, "retmode": "json", "sort": "relevance"}
        try:
            r = requests.get(url, params=params, timeout=30, headers=HEADERS)
            r.raise_for_status()
            ids = r.json().get("esearchresult", {}).get("idlist", [])
            logger.info(f"[PMC] {len(ids)} hits: {query[:60]}...")
            return ids
        except Exception as e:
            logger.error(f"[PMC] error scanning {query}: {e}")
            return []

    def get_pmc_details(self, pmc_ids):
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
                                "pubdate": str(info.get("pubdate", "")),
                                "doi": info.get("doi", ""),
                            })
                    break
                except Exception as e:
                    logger.debug(f"[PMC] metadata error (attempt {attempt+1}): {e}")
                    time.sleep(2)
            time.sleep(0.5)
        return articles

    # ========================== PubMed ==========================
    def search_pubmed(self, query, retmax=30):
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {"db": "pubmed", "term": query, "retmax": retmax, "retmode": "json", "sort": "relevance"}
        try:
            r = requests.get(url, params=params, timeout=30, headers=HEADERS)
            r.raise_for_status()
            ids = r.json().get("esearchresult", {}).get("idlist", [])
            logger.info(f"[PubMed] {len(ids)} hits: {query[:60]}...")
            return ids
        except Exception as e:
            logger.error(f"[PubMed] error scanning {query}: {e}")
            return []

    def get_pubmed_details(self, pmids):
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
                                    "pubdate": str(info.get("pubdate", "")),
                                    "doi": doi,
                                })
                    break
                except Exception as e:
                    logger.debug(f"[PubMed] metadata error (attempt {attempt+1}): {e}")
                    time.sleep(2)
            time.sleep(0.5)
        return articles

    # ========================== Crossref ==========================
    def search_crossref(self, query, rows=30):
        url = "https://api.crossref.org/works"
        params = {
            "query": query, "rows": rows, "sort": "relevance",
            "filter": "type:journal-article",
            "select": "DOI,title,author,container-title,published-print,published-online",
        }
        try:
            r = requests.get(url, params=params, timeout=30, headers=self.crossref_headers)
            r.raise_for_status()
            items = r.json().get("message", {}).get("items", [])
            articles = []
            for item in items:
                doi = item.get("DOI", "")
                title_list = item.get("title", [])
                title = title_list[0] if title_list else ""
                if doi and title:
                    authors = item.get("author", [])
                    first_author = f"{authors[0].get('family', '')} {authors[0].get('given', '')}".strip() if authors else ""
                    journal_list = item.get("container-title", [])
                    journal = journal_list[0] if journal_list else ""
                    pub = item.get("published-print") or item.get("published-online") or {}
                    parts = pub.get("date-parts", [[]])
                    year = str(parts[0][0]) if parts and parts[0] else ""
                    articles.append({
                        "doi": doi, "origin": "crossref", "title": title,
                        "authors": first_author, "source": journal, "pubdate": year,
                    })
            logger.info(f"[Crossref] {len(articles)} hits: {query[:60]}...")
            return articles
        except Exception as e:
            logger.error(f"[Crossref] error scanning {query}: {e}")
            return []

    # ========================== OpenAlex ==========================
    def search_openalex(self, query, per_page=30):
        url = "https://api.openalex.org/works"
        params = {
            "search": query, "per_page": per_page, "sort": "relevance_score:desc",
            "filter": "type:article", "mailto": self.unpaywall_email,
        }
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            results = r.json().get("results", [])
            articles = []
            for item in results:
                doi = (item.get("doi") or "").replace("https://doi.org/", "")
                title = item.get("title", "")
                if not doi or not title:
                    continue
                oa_url = item.get("best_oa_location", {}).get("pdf_url")
                if not oa_url:
                    for loc in item.get("locations", []):
                        if loc.get("pdf_url"):
                            oa_url = loc["pdf_url"]
                            break
                authorships = item.get("authorships", [])
                first_author = authorships[0].get("author", {}).get("display_name", "") if authorships else ""
                journal = (item.get("primary_location") or {}).get("source", {}).get("display_name", "")
                year = str(item.get("publication_year", ""))
                articles.append({
                    "doi": doi, "origin": "openalex", "title": title,
                    "authors": first_author, "source": journal, "pubdate": year,
                    "oa_pdf_url": oa_url,
                })
            logger.info(f"[OpenAlex] {len(articles)} hits: {query[:60]}...")
            return articles
        except Exception as e:
            logger.error(f"[OpenAlex] error scanning {query}: {e}")
            return []

    # ========================== Unpaywall ==========================
    def query_unpaywall(self, doi):
        if not doi:
            return None
        url = f"https://api.unpaywall.org/v2/{doi}?email={self.unpaywall_email}"
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                for loc in [data.get("best_oa_location")] + data.get("oa_locations", []):
                    if loc and loc.get("url_for_pdf"):
                        return {
                            "pdf_url": loc["url_for_pdf"],
                            "source": loc.get("evidence", ""),
                            "host": loc.get("host_type", "")
                        }
        except Exception as e:
            logger.debug(f"[Unpaywall] error for {doi}: {e}")
        return None

    # ========================== Publisher PDF Matchers ==========================
    @staticmethod
    def try_publisher_pdf(doi):
        """Try known publisher PDF URL patterns."""
        if not doi:
            return None

        patterns = [
            f"https://link.springer.com/content/pdf/{doi}.pdf",       # Springer/Nature/BMC
            f"https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}",   # Wiley
            f"https://www.tandfonline.com/doi/pdf/{doi}",             # Taylor & Francis
            f"https://academic.oup.com/doi/pdf/{doi}",                # Oxford University Press
            f"https://www.cambridge.org/core/services/aop-cambridge-core/content/view/{doi}", # Cambridge
            f"https://www.annualreviews.org/doi/pdf/{doi}",           # Annual Reviews
            f"https://www.pnas.org/doi/pdf/{doi}",                    # PNAS
            f"https://journals.plos.org/plosone/article/file?id={doi}&type=printable", # PLOS
            f"https://pubs.acs.org/doi/pdf/{doi}",                    # ACS
            f"https://pubs.rsc.org/en/content/articlepdf/{doi}",      # RSC
            f"https://www.mdpi.com/{doi}/pdf",                        # MDPI
        ]

        from .utils import is_valid_pdf

        for url in patterns:
            r = robust_get(url, timeout=45)
            if r and r.status_code == 200 and is_valid_pdf(r.content):
                return r.content

        # Elsevier Direct API
        try:
            h = {**HEADERS, 'Accept': 'application/pdf'}
            r = requests.get(f"https://api.elsevier.com/content/article/doi/{doi}",
                             headers=h, timeout=45, allow_redirects=True)
            if r.status_code == 200 and is_valid_pdf(r.content):
                return r.content
        except Exception:
            pass

        # Elsevier Web Redirect Fallback
        try:
            r = robust_get(f"https://www.sciencedirect.com/science/article/pii/doi/{doi}")
            if r and r.status_code == 200:
                pdf_url = r.url.replace("/article/", "/article/pii/") + "/pdfft"
                r2 = robust_get(pdf_url, timeout=45)
                if r2 and r2.status_code == 200 and is_valid_pdf(r2.content):
                    return r2.content
        except Exception:
            pass

        return None

    # ========================== PMC Direct Downloaders ==========================
    @staticmethod
    def try_pmc_oa_strategies(pmcid):
        from .utils import is_valid_pdf

        # Strategy 1: NCBI OA API FTP lookup
        try:
            r = requests.get(f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}",
                             timeout=30, headers=HEADERS)
            root = ET.fromstring(r.content)
            for link in root.iter('link'):
                if link.get('format') == 'pdf':
                    href = link.get('href', '').replace('ftp://ftp.ncbi.nlm.nih.gov/', 'https://ftp.ncbi.nlm.nih.gov/')
                    pdf_r = robust_get(href, timeout=60)
                    if pdf_r and pdf_r.status_code == 200 and is_valid_pdf(pdf_r.content):
                        return pdf_r.content
        except Exception:
             pass

        # Strategy 2: Direct PMC endpoint
        try:
            r = requests.get(f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/pdf/",
                             headers=HEADERS, timeout=60, allow_redirects=True)
            if r.status_code == 200 and is_valid_pdf(r.content):
                return r.content
        except Exception:
            pass

        # Strategy 3: Europe PMC endpoint
        try:
            r = requests.get(f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf",
                             headers=HEADERS, timeout=60, allow_redirects=True)
            if r.status_code == 200 and is_valid_pdf(r.content):
                return r.content
        except Exception:
             pass
             
        return None
