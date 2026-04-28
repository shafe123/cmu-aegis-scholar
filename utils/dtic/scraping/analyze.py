"""
Analyze scraped DTIC publication data.

This script provides utilities for analyzing the JSON output from the scraper.
"""

import json
from pathlib import Path
from collections import Counter, defaultdict
import re


class DTICAnalyzer:
    """Analyze scraped DTIC publication data."""

    def __init__(self, data_dir: str = "dtic_publications"):
        self.data_dir = Path(data_dir)
        self.publications = []
        self._load_data()

    def _load_data(self):
        """Load publications from JSON files in directory."""
        if not self.data_dir.exists():
            print(f"Warning: {self.data_dir} does not exist")
            return

        if not self.data_dir.is_dir():
            print(f"Warning: {self.data_dir} is not a directory")
            return

        # Load all JSON files in the directory
        json_files = list(self.data_dir.glob("*.json"))

        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    self.publications.append(json.load(f))
            except json.JSONDecodeError as e:
                print(f"Error parsing {json_file}: {e}")

        print(
            f"Loaded {len(self.publications)} publications from {len(json_files)} files"
        )

    def summary_stats(self):
        """Print summary statistics."""
        print("\n" + "=" * 70)
        print("DTIC Publication Summary Statistics")
        print("=" * 70)

        print(f"\nTotal Publications: {len(self.publications)}")

        # Count publications with various fields
        with_abstract = sum(1 for p in self.publications if p.get("abstract"))
        with_doi = sum(1 for p in self.publications if p.get("doi"))
        with_keywords = sum(1 for p in self.publications if p.get("keywords"))
        with_citations = sum(1 for p in self.publications if p.get("citations_count"))

        print(
            f"Publications with abstracts: {with_abstract} ({with_abstract / len(self.publications) * 100:.1f}%)"
        )
        print(
            f"Publications with DOI: {with_doi} ({with_doi / len(self.publications) * 100:.1f}%)"
        )
        print(
            f"Publications with keywords: {with_keywords} ({with_keywords / len(self.publications) * 100:.1f}%)"
        )
        print(
            f"Publications with citation counts: {with_citations} ({with_citations / len(self.publications) * 100:.1f}%)"
        )

        # Author stats
        total_authors = sum(len(p.get("authors", [])) for p in self.publications)
        avg_authors = total_authors / len(self.publications) if self.publications else 0
        print(f"\nTotal author entries: {total_authors}")
        print(f"Average authors per publication: {avg_authors:.2f}")

        # Organization stats
        total_orgs = sum(len(p.get("organizations", [])) for p in self.publications)
        avg_orgs = total_orgs / len(self.publications) if self.publications else 0
        print(f"\nTotal organization entries: {total_orgs}")
        print(f"Average organizations per publication: {avg_orgs:.2f}")

    def top_authors(self, n: int = 10):
        """Find most prolific authors."""
        print(f"\n{'=' * 70}")
        print(f"Top {n} Most Prolific Authors")
        print("=" * 70)

        author_counts = Counter()

        for pub in self.publications:
            for author in pub.get("authors", []):
                author_counts[author["name"]] += 1

        for i, (author, count) in enumerate(author_counts.most_common(n), 1):
            print(f"{i:2d}. {author:50s} {count:4d} publications")

    def top_organizations(self, n: int = 10):
        """Find most active organizations."""
        print(f"\n{'=' * 70}")
        print(f"Top {n} Most Active Organizations")
        print("=" * 70)

        org_counts = Counter()

        for pub in self.publications:
            for org in pub.get("organizations", []):
                org_counts[org["name"]] += 1

        for i, (org, count) in enumerate(org_counts.most_common(n), 1):
            print(f"{i:2d}. {org:60s} {count:4d} publications")

    def top_keywords(self, n: int = 20):
        """Find most common keywords."""
        print(f"\n{'=' * 70}")
        print(f"Top {n} Most Common Keywords")
        print("=" * 70)

        keyword_counts = Counter()

        for pub in self.publications:
            for keyword in pub.get("keywords", []):
                keyword_counts[keyword.lower()] += 1

        for i, (keyword, count) in enumerate(keyword_counts.most_common(n), 1):
            print(f"{i:2d}. {keyword:50s} {count:4d} occurrences")

    def publications_by_year(self):
        """Count publications by year."""
        print(f"\n{'=' * 70}")
        print("Publications by Year")
        print("=" * 70)

        year_counts = Counter()

        for pub in self.publications:
            date_str = pub.get("publication_date", "")
            if date_str:
                # Try to extract year from various date formats
                year_match = re.search(r"\d{4}", date_str)
                if year_match:
                    year = int(year_match.group())
                    year_counts[year] += 1

        if not year_counts:
            print("No publication dates found")
            return

        for year in sorted(year_counts.keys(), reverse=True):
            count = year_counts[year]
            bar = "█" * (count // max(1, max(year_counts.values()) // 50))
            print(f"{year}: {count:4d} {bar}")

    def document_types(self):
        """Count different document types."""
        print(f"\n{'=' * 70}")
        print("Document Types")
        print("=" * 70)

        type_counts = Counter()

        for pub in self.publications:
            doc_type = pub.get("document_type", "Unknown")
            type_counts[doc_type] += 1

        for doc_type, count in type_counts.most_common():
            pct = count / len(self.publications) * 100
            print(f"{doc_type:40s} {count:5d} ({pct:5.1f}%)")

    def citation_stats(self):
        """Analyze citation statistics."""
        print(f"\n{'=' * 70}")
        print("Citation Statistics")
        print("=" * 70)

        citations = [
            p.get("citations_count", 0)
            for p in self.publications
            if p.get("citations_count") is not None
        ]

        if not citations:
            print("No citation data available")
            return

        citations.sort(reverse=True)

        total = sum(citations)
        avg = total / len(citations)
        median = citations[len(citations) // 2]

        print(f"Publications with citation data: {len(citations)}")
        print(f"Total citations: {total:,}")
        print(f"Average citations: {avg:.2f}")
        print(f"Median citations: {median}")
        print(f"Max citations: {max(citations)}")
        print(f"Min citations: {min(citations)}")

        print("\nTop 10 Most Cited Publications:")
        cited_pubs = [
            (
                p.get("citations_count", 0),
                p.get("title", "Unknown"),
                p.get("publication_id", ""),
            )
            for p in self.publications
            if p.get("citations_count")
        ]
        cited_pubs.sort(reverse=True)

        for i, (cites, title, pub_id) in enumerate(cited_pubs[:10], 1):
            print(f"{i:2d}. [{cites:4d}] {title[:60]}")

    def author_network(self):
        """Analyze author collaboration patterns."""
        print(f"\n{'=' * 70}")
        print("Author Collaboration Analysis")
        print("=" * 70)

        # Find authors who frequently collaborate
        collaborations = defaultdict(Counter)

        for pub in self.publications:
            authors = [a["name"] for a in pub.get("authors", [])]
            if len(authors) > 1:
                for i, author1 in enumerate(authors):
                    for author2 in authors[i + 1 :]:
                        collaborations[author1][author2] += 1
                        collaborations[author2][author1] += 1

        # Find most frequent collaborations
        all_collabs = []
        seen = set()

        for author1, partners in collaborations.items():
            for author2, count in partners.items():
                pair = tuple(sorted([author1, author2]))
                if pair not in seen:
                    seen.add(pair)
                    all_collabs.append((count, author1, author2))

        all_collabs.sort(reverse=True)

        print("\nTop 10 Author Collaborations:")
        for i, (count, author1, author2) in enumerate(all_collabs[:10], 1):
            print(f"{i:2d}. {author1:30s} & {author2:30s} ({count} papers)")

    def export_csv(self, output_file: str = "dtic_publications.csv"):
        """Export publications to CSV format."""
        import csv

        if not self.publications:
            print("No publications to export")
            return

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            # Determine all possible fields
            fieldnames = [
                "publication_id",
                "title",
                "abstract",
                "publication_date",
                "doi",
                "document_type",
                "citations_count",
                "url",
                "author_names",
                "organization_names",
                "keywords",
            ]

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for pub in self.publications:
                # Flatten author and organization lists
                author_names = "; ".join(a["name"] for a in pub.get("authors", []))
                org_names = "; ".join(o["name"] for o in pub.get("organizations", []))
                keywords = "; ".join(pub.get("keywords", []))

                writer.writerow(
                    {
                        "publication_id": pub.get("publication_id", ""),
                        "title": pub.get("title", ""),
                        "abstract": pub.get("abstract", ""),
                        "publication_date": pub.get("publication_date", ""),
                        "doi": pub.get("doi", ""),
                        "document_type": pub.get("document_type", ""),
                        "citations_count": pub.get("citations_count", ""),
                        "url": pub.get("url", ""),
                        "author_names": author_names,
                        "organization_names": org_names,
                        "keywords": keywords,
                    }
                )

        print(f"\nExported {len(self.publications)} publications to {output_file}")

    def run_all_analyses(self):
        """Run all available analyses."""
        self.summary_stats()
        self.top_authors()
        self.top_organizations()
        self.top_keywords()
        self.publications_by_year()
        self.document_types()
        self.citation_stats()
        self.author_network()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze DTIC publication data")
    parser.add_argument(
        "--input-dir",
        "-i",
        default="dtic_publications",
        help="Input directory with JSON files (default: dtic_publications)",
    )
    parser.add_argument(
        "--export-csv", "-e", metavar="FILE", help="Export data to CSV file"
    )
    parser.add_argument(
        "--summary", "-s", action="store_true", help="Show summary statistics only"
    )

    args = parser.parse_args()

    analyzer = DTICAnalyzer(args.input_dir)

    if args.export_csv:
        analyzer.export_csv(args.export_csv)
    elif args.summary:
        analyzer.summary_stats()
    else:
        analyzer.run_all_analyses()


if __name__ == "__main__":
    main()
