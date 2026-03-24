import os
import json
import csv
import concurrent.futures
from datetime import date
from urllib.parse import quote
import threading

from .utils import logger, sanitize_filename, pubmed_to_plain
from .clients import PaperSearchClients, robust_get

class BatchDownloader:
    def __init__(self, outdir, email, threads=5, retmax=30, institutional=False):
        self.outdir = os.path.abspath(outdir)
        self.email = email
        self.threads = threads
        self.retmax = retmax
        self.institutional = institutional
        self.clients = PaperSearchClients(email)
        
        self.state_file = os.path.join(self.outdir, "metadata_cache.json")
        self.papers_state = {}  # key: uid (pmcid/doi/title), val: article dict
        self.lock = threading.Lock()
        
        os.makedirs(self.outdir, exist_ok=True)
        self._load_state()

    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self.papers_state = json.load(f)
                logger.info(f"Loaded {len(self.papers_state)} cached paper records.")
            except Exception as e:
                logger.error(f"Error loading cache: {e}")

    def _save_state(self):
        with self.lock:
            try:
                with open(self.state_file, 'w', encoding='utf-8') as f:
                    json.dump(self.papers_state, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Error saving cache: {e}")

    def _get_uid(self, article):
        if article.get('doi'):
            return article['doi'].lower()
        if article.get('pmcid'):
            return article['pmcid'].lower()
        if article.get('pmid'):
            return article['pmid']
        return article.get('title', '').lower()

    def run(self, queries):
        logger.info("[PHASE 1] Searching Metadata APIs...")
        
        crossref_queries = [pubmed_to_plain(q) for q in queries]
        openalex_queries = crossref_queries
        
        all_articles = []
        
        # Parallel searching
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = []
            
            # PMC & PubMed
            for q in queries:
                futures.append(executor.submit(self._search_and_fetch_ncbi, q, 'pmc'))
                futures.append(executor.submit(self._search_and_fetch_ncbi, q, 'pubmed'))
            
            # Crossref
            for q in crossref_queries:
                futures.append(executor.submit(self.clients.search_crossref, q, self.retmax))
                
            # OpenAlex
            for q in openalex_queries:
                futures.append(executor.submit(self.clients.search_openalex, q, self.retmax))
                
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res:
                    all_articles.extend(res)
                    
        # Dedup and Merge with state
        logger.info(f"Aggregated {len(all_articles)} raw search results. Deduplicating...")
        new_count = 0
        for art in all_articles:
            uid = self._get_uid(art)
            if not uid:
                continue
            if uid not in self.papers_state:
                art['status'] = 'pending'
                art['channel'] = ''
                art['file'] = ''
                self.papers_state[uid] = art
                new_count += 1
            else:
                # Merge if new source has OA URL and old doesn't
                if art.get('oa_pdf_url') and not self.papers_state[uid].get('oa_pdf_url'):
                    self.papers_state[uid]['oa_pdf_url'] = art['oa_pdf_url']

        logger.info(f"Added {new_count} new unique papers to queue.")
        self._save_state()

        # Download Strategy Execution
        pending = [uid for uid, art in self.papers_state.items() if art.get('status') != 'success']
        if not pending:
            logger.info("All papers already downloaded or attempted. Exiting.")
            self._export_reports()
            return
            
        logger.info(f"[PHASE 2] Downloading {len(pending)} pending papers using {self.threads} threads...")
        from tqdm import tqdm
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = {executor.submit(self._download_worker, uid): uid for uid in pending}
            for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="Downloading"):
                uid = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Unhandled error downloading {uid}: {e}")

        # Final save and report
        self._save_state()
        self._export_reports()

    def _search_and_fetch_ncbi(self, query, db):
        if db == 'pmc':
            ids = self.clients.search_pmc(query, self.retmax)
            return self.clients.get_pmc_details(ids)
        else:
            ids = self.clients.search_pubmed(query, self.retmax)
            return self.clients.get_pubmed_details(ids)

    def _download_worker(self, uid):
        art = self.papers_state[uid]
        doi = art.get('doi', '')
        pmcid = art.get('pmcid', '')
        title = art.get('title', 'Unknown Title')
        oa_url = art.get('oa_pdf_url')

        prefix = f"[{art.get('origin', 'unk')}] "
        clean_title = sanitize_filename(f"{prefix}{doi.replace('/', '_') if doi else pmcid or 'txt'}_{title}")
        filepath = os.path.join(self.outdir, f"{clean_title}.pdf")
        
        # Check if file exists locally
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            self._mark_success(uid, filepath, "cached")
            return

        # 1. OpenAlex built-in OA URL
        if oa_url:
            if self._download_and_save(oa_url, filepath):
                self._mark_success(uid, filepath, "openalex_oa")
                return

        # 2. PMC specific OA retrieval
        if pmcid:
            content = self.clients.try_pmc_oa_strategies(pmcid)
            if content:
                self._save_file(filepath, content)
                self._mark_success(uid, filepath, "pmc_oa")
                return

        # 3. Unpaywall Best Location
        if doi:
            uw_res = self.clients.query_unpaywall(doi)
            if uw_res and uw_res.get("pdf_url"):
                if self._download_and_save(uw_res["pdf_url"], filepath):
                    self._mark_success(uid, filepath, "unpaywall")
                    return

        # 4. Publisher specific scraping
        if doi and (self.institutional or True):  # We try anyway, some are hybrid OA
            content = self.clients.try_publisher_pdf(doi)
            if content:
                self._save_file(filepath, content)
                self._mark_success(uid, filepath, "publisher")
                return

        # Failed
        with self.lock:
            self.papers_state[uid]['status'] = 'failed'

    def _download_and_save(self, url, filepath):
        from .utils import is_valid_pdf
        r = robust_get(url, timeout=90)
        if r and r.status_code == 200 and is_valid_pdf(r.content):
            self._save_file(filepath, r.content)
            return True
        return False

    def _save_file(self, filepath, content):
        with open(filepath, 'wb') as f:
            f.write(content)

    def _mark_success(self, uid, filepath, channel):
        with self.lock:
            self.papers_state[uid]['status'] = 'success'
            self.papers_state[uid]['channel'] = channel
            self.papers_state[uid]['file'] = os.path.basename(filepath)

    def _export_reports(self):
        txt_report = os.path.join(self.outdir, "download_report.txt")
        csv_report = os.path.join(self.outdir, "papers_metadata.csv")

        success_arts = [v for v in self.papers_state.values() if v.get('status') == 'success']
        failed_arts = [v for v in self.papers_state.values() if v.get('status') != 'success']

        # TXT Report
        try:
            with open(txt_report, 'w', encoding='utf-8') as f:
                f.write("Literature Download Report (v4 Open-Source)\n")
                f.write("=" * 60 + "\n")
                f.write(f"Date: {date.today()}\n")
                f.write(f"Total Unique: {len(self.papers_state)} | Downloaded: {len(success_arts)} | Failed: {len(failed_arts)}\n")
                
                f.write("\n" + "=" * 60 + "\n")
                f.write("Downloaded Papers\n")
                f.write("=" * 60 + "\n\n")
                for i, d in enumerate(success_arts, 1):
                    f.write(f"{i}. {d.get('title', 'N/A')}\n")
                    f.write(f"   DOI: {d.get('doi', '')} | Channel: {d.get('channel', '')}\n")
                    f.write(f"   File: {d.get('file', 'N/A')}\n\n")
        except Exception as e:
            logger.error(f"Error saving TXT report: {e}")

        # CSV Report (For EndNote/Zotero integration placeholder)
        try:
            headers = ["title", "authors", "source", "pubdate", "doi", "pmcid", "pmid", "status", "channel", "file"]
            with open(csv_report, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
                writer.writeheader()
                for art in self.papers_state.values():
                    writer.writerow(art)
        except Exception as e:
            logger.error(f"Error saving CSV report: {e}")

        logger.info(f"[DONE] Generated {txt_report} and {csv_report}")
