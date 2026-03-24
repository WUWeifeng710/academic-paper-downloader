import re
import os
import sys
import logging
import colorlog

def setup_logger(debug=False):
    """Setup a colored logger for the CLI"""
    logger = logging.getLogger("paper_downloader")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG if debug else logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        
        formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s | %(levelname)-8s | %(message)s",
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

logger = setup_logger()

def sanitize_filename(name: str, max_len: int = 120) -> str:
    """Sanitize the title for safe usage as a Windows/Linux filename."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    name = name.strip('. ')
    return name[:max_len].strip() if len(name) > max_len else name

def is_valid_pdf(content: bytes) -> bool:
    """
    Robust PDF detection. 
    1. Must contain %PDF in the first 100 bytes.
    2. Optional: check for EOF marker for completeness but just basic length is usually enough.
    """
    if not content or len(content) < 5000:
        return False
    # Look for PDF magic string near the start to account for some leading weird bytes sometimes
    if b'%PDF' not in content[:100]:
        return False
        
    return True

def pubmed_to_plain(query: str) -> str:
    """Convert PubMed Boolean query to plain text for Crossref/OpenAlex."""
    q = query.replace("(", "").replace(")", "")
    q = re.sub(r'\bAND\b', ' ', q, flags=re.IGNORECASE)
    q = re.sub(r'\bOR\b', ' ', q, flags=re.IGNORECASE)
    q = re.sub(r'"', '', q)
    return re.sub(r'\s+', ' ', q).strip()
