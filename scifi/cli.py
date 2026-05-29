"""Command-line interface for scifi."""
import argparse
import time
from collections import Counter

from .fetch import default_sources, fetch
from .sources.scihub import SciHub


def main():
    p = argparse.ArgumentParser(
        prog="scifi",
        description="Download scientific PDFs by DOI, PMID, or PMCID (PMC Open Access, Unpaywall, then Sci-Hub).",
        epilog="Example: scifi 10.1006/bbrc.2000.2954 PMID:10720320 PMC1234567 -o papers",
    )
    p.add_argument("ids", nargs="+", metavar="ID", help="one or more DOIs, PMIDs, or PMCIDs to fetch")
    p.add_argument("-o", "--outdir", default="papers", help="output directory (default: papers)")
    p.add_argument("-d", "--delay", type=float, default=3.0, help="seconds to sleep between IDs (default: 3)")
    p.add_argument("-m", "--mirror", action="append", help="override Sci-Hub mirror(s); repeatable")
    args = p.parse_args()

    sources = default_sources()
    if args.mirror:
        sources = [s for s in sources if not isinstance(s, SciHub)]
        sources.append(SciHub(mirrors=args.mirror))

    results = []
    for i, raw in enumerate(args.ids):
        results.append(fetch(raw, outdir=args.outdir, sources=sources))
        if i < len(args.ids) - 1:
            time.sleep(args.delay)

    _print_report(results)


def _print_report(results):
    """Render a per-ID table and (for >1 ID) an aggregate summary line."""
    headers = ("raw", "pmid", "pmcid", "doi", "source", "status")
    rows = []
    for r in results:
        a = r.article
        status = f"ok → {r.path}" if r.ok else (r.error or "?")
        rows.append((r.raw, a.pmid or "—", a.pmcid or "—", a.doi or "—", r.source or "—", status))

    widths = [max(len(h), *(len(row[i]) for row in rows)) for i, h in enumerate(headers)]
    # Pad every column except the last — the status column can be a long error
    # message, and padding it just trails whitespace off the right edge.
    fmt = "  ".join([f"{{:<{w}}}" for w in widths[:-1]] + ["{}"])
    print(fmt.format(*headers))
    for row in rows:
        print(fmt.format(*row))

    if len(results) > 1:
        by_source = Counter(r.source for r in results if r.ok)
        failed = sum(1 for r in results if not r.ok)
        parts = [f"{n} {s}" for s, n in by_source.most_common()]
        if failed:
            parts.append(f"{failed} failed")
        print("─ " + " · ".join(parts) + " ─")


if __name__ == "__main__":
    main()
