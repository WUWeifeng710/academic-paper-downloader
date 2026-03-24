import argparse
from .utils import logger
from .downloader import BatchDownloader

def main():
    parser = argparse.ArgumentParser(
        description="Academic Paper Downloader v4 (Modular & Concurrent)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        "--queries", 
        type=str, 
        required=True,
        help='Search query string (PubMed Boolean syntax). Quote to pass multiple separated by spaces.'
    )
    
    parser.add_argument(
        "--email", 
        type=str, 
        required=True,
        help="Valid email for Unpaywall and Crossref polite pool."
    )
    
    parser.add_argument(
        "--outdir", 
        type=str, 
        default="./papers",
        help="Directory to save downloaded PDFs and generated reports."
    )
    
    parser.add_argument(
        "--threads", 
        type=int, 
        default=5,
        help="Number of concurrent download threads (default: 5)."
    )
    
    parser.add_argument(
        "--retmax", 
        type=int, 
        default=30,
        help="Max results per engine query (default: 30)."
    )
    
    parser.add_argument(
        "--institutional", 
        action="store_true",
        help="Flag: Use if your network has publisher subscriptions."
    )

    args = parser.parse_args()

    # Split space-separated queries safely, or if it's one large query block
    # Simple heuristic to split queries: assuming user provides a block
    # Alternatively, user can just define one complex query string and run multiple times.
    
    queries = [q.strip() for q in args.queries.split("  ") if q.strip()]
    if not queries:
        queries = [args.queries]

    logger.info("=" * 60)
    logger.info("Academic Paper Bath Downloader v4 [CLI Mode]")
    logger.info("=" * 60)
    logger.info(f"Target Directory : {args.outdir}")
    logger.info(f"Email            : {args.email}")
    logger.info(f"Concurrent Threads: {args.threads}")
    logger.info(f"Number of Queries : {len(queries)}")

    downloader = BatchDownloader(
        outdir=args.outdir,
        email=args.email,
        threads=args.threads,
        retmax=args.retmax,
        institutional=args.institutional
    )

    downloader.run(queries)

if __name__ == "__main__":
    main()
