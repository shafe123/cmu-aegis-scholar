#!/usr/bin/env python3
"""Build a small linked DTIC subset for integration and end-to-end testing.

The script creates a connected dataset across authors, works, orgs, and topics,
while intentionally preserving a controlled number of edge cases.
"""

from __future__ import annotations

import argparse
import json
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


@dataclass(frozen=True)
class WorkMeta:
    raw: dict
    id: str
    author_ids: tuple[str, ...]
    author_org_ids: tuple[str, ...]
    org_ids: tuple[str, ...]
    topic_ids: tuple[str, ...]
    num_authors: int
    year: int | None
    has_abstract: bool
    has_doi: bool
    has_authors: bool
    has_topics: bool
    has_orgs: bool
    has_author_missing_org: bool
    all_authors_present: bool
    all_orgs_present: bool
    all_topics_present: bool


def iter_jsonl(path: Path) -> Iterable[dict]:
    """Yield JSON objects from a JSONL file, skipping malformed lines."""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def load_entity_map(path: Path) -> dict[str, dict]:
    """Load a JSONL file into an ID-keyed dictionary."""
    result: dict[str, dict] = {}
    for obj in iter_jsonl(path):
        entity_id = obj.get("id")
        if entity_id:
            result[entity_id] = obj
    return result


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    """Deduplicate while preserving insertion order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


def parse_year(publication_date: str | None) -> int | None:
    """Extract a year from ISO-like publication_date text."""
    if not publication_date or len(publication_date) < 4:
        return None
    try:
        return int(publication_date[:4])
    except ValueError:
        return None


def has_special_name(name: str | None) -> bool:
    """Identify names useful for coverage of formatting and unicode cases."""
    if not name:
        return False
    if any(ord(ch) > 127 for ch in name):
        return True
    if "-" in name or "." in name or len(name.split()) >= 3:
        return True
    return False


def author_org_ids(author: dict) -> list[str]:
    """Return author org IDs as a cleaned list."""
    return unique_preserve_order(author.get("org_ids") or [])


def build_work_meta(
    work: dict,
    authors_map: dict[str, dict],
    orgs_map: dict[str, dict],
    topics_map: dict[str, dict],
) -> WorkMeta:
    """Build derived metadata used for subset selection."""
    author_entries = work.get("authors") or []
    work_org_entries = work.get("orgs") or []
    work_topic_entries = work.get("topics") or []

    author_ids = unique_preserve_order(
        entry.get("author_id") for entry in author_entries if isinstance(entry, dict)
    )
    author_orgs = unique_preserve_order(
        entry.get("org_id") for entry in author_entries if isinstance(entry, dict)
    )
    work_orgs = unique_preserve_order(
        entry.get("org_id") for entry in work_org_entries if isinstance(entry, dict)
    )
    topic_ids = unique_preserve_order(
        entry.get("topic_id") for entry in work_topic_entries if isinstance(entry, dict)
    )

    return WorkMeta(
        raw=work,
        id=work["id"],
        author_ids=tuple(author_ids),
        author_org_ids=tuple(author_orgs),
        org_ids=tuple(work_orgs),
        topic_ids=tuple(topic_ids),
        num_authors=len(author_ids),
        year=parse_year(work.get("publication_date")),
        has_abstract=bool((work.get("abstract") or "").strip()),
        has_doi=bool((work.get("doi") or "").strip()),
        has_authors=bool(author_ids),
        has_topics=bool(topic_ids),
        has_orgs=bool(work_orgs),
        has_author_missing_org=any(
            not (entry.get("org_id") or "").strip()
            for entry in author_entries
            if isinstance(entry, dict)
        ),
        all_authors_present=all(author_id in authors_map for author_id in author_ids),
        all_orgs_present=all(
            org_id in orgs_map for org_id in set(author_orgs).union(work_orgs)
        ),
        all_topics_present=all(topic_id in topics_map for topic_id in topic_ids),
    )


def referenced_org_ids_from_work(meta: WorkMeta) -> set[str]:
    """Return all org IDs implied by the work record."""
    return set(meta.org_ids).union(meta.author_org_ids)


def can_add_work(
    meta: WorkMeta,
    seen_authors: set[str],
    seen_orgs: set[str],
    seen_topics: set[str],
    max_authors: int,
    max_orgs: int,
    max_topics: int,
) -> bool:
    """Check whether adding this work would exceed the linked-entity budget."""
    projected_authors = len(seen_authors.union(meta.author_ids))
    projected_orgs = len(seen_orgs.union(referenced_org_ids_from_work(meta)))
    projected_topics = len(seen_topics.union(meta.topic_ids))
    return (
        projected_authors <= max_authors
        and projected_orgs <= max_orgs
        and projected_topics <= max_topics
    )


def choose_work_batch(
    works: list[WorkMeta],
    predicate: Callable[[WorkMeta], bool],
    quota: int,
    selected_ids: set[str],
    seen_authors: set[str],
    seen_orgs: set[str],
    seen_topics: set[str],
    max_authors: int,
    max_orgs: int,
    max_topics: int,
) -> list[WorkMeta]:
    """Greedily choose works that maximize reuse of already-selected entities."""
    picks: list[WorkMeta] = []
    remaining = [
        meta for meta in works if meta.id not in selected_ids and predicate(meta)
    ]

    while remaining and len(picks) < quota:
        remaining.sort(
            key=lambda meta: (
                len(set(meta.author_ids) - seen_authors),
                len(referenced_org_ids_from_work(meta) - seen_orgs),
                len(set(meta.topic_ids) - seen_topics),
                0 if meta.num_authors == 1 else meta.num_authors,
                0 if meta.has_abstract else 1,
                meta.year or 9999,
                meta.id,
            )
        )

        chosen = None
        for meta in remaining:
            if can_add_work(
                meta,
                seen_authors,
                seen_orgs,
                seen_topics,
                max_authors,
                max_orgs,
                max_topics,
            ):
                chosen = meta
                break
        if chosen is None:
            break

        picks.append(chosen)
        selected_ids.add(chosen.id)
        seen_authors.update(chosen.author_ids)
        seen_orgs.update(referenced_org_ids_from_work(chosen))
        seen_topics.update(chosen.topic_ids)
        remaining.remove(chosen)

    return picks


def choose_extra_authors(
    authors_map: dict[str, dict],
    selected_author_ids: set[str],
    selected_org_ids: set[str],
    target_count: int,
) -> list[str]:
    """Backfill authors while preserving linkability and edge-case coverage."""
    extras: list[str] = []

    def add_from(predicate: Callable[[dict], bool], max_take: int) -> None:
        nonlocal extras
        if len(selected_author_ids) + len(extras) >= target_count:
            return

        candidates = []
        for author_id, author in authors_map.items():
            if author_id in selected_author_ids or author_id in extras:
                continue
            if not predicate(author):
                continue
            orgs = set(author_org_ids(author))
            new_orgs = len(orgs - selected_org_ids)
            candidates.append(
                (
                    new_orgs,
                    len(orgs),
                    author.get("works_count", 0),
                    author.get("name", ""),
                    author_id,
                )
            )

        for _, _, _, _, author_id in sorted(candidates):
            if len(selected_author_ids) + len(extras) >= target_count or max_take <= 0:
                break
            extras.append(author_id)
            selected_org_ids.update(author_org_ids(authors_map[author_id]))
            max_take -= 1

    add_from(lambda a: (a.get("works_count") or 0) == 0, 6)
    add_from(lambda a: not author_org_ids(a), 6)
    add_from(lambda a: len(author_org_ids(a)) != len(set(author_org_ids(a))), 4)
    add_from(
        lambda a: (
            (a.get("citation_count") or 0) == 0 and (a.get("works_count") or 0) > 0
        ),
        4,
    )
    add_from(lambda a: has_special_name(a.get("name")), 4)

    if len(selected_author_ids) + len(extras) < target_count:
        add_from(lambda a: True, target_count - len(selected_author_ids) - len(extras))

    return extras


def fill_entities(
    required_ids: set[str],
    entity_map: dict[str, dict],
    target_count: int,
    sort_key: Callable[[dict], tuple],
) -> list[dict]:
    """Return exactly target_count entities, starting from required linked ones."""
    selected = [
        entity_map[entity_id] for entity_id in required_ids if entity_id in entity_map
    ]
    selected_ids = {obj["id"] for obj in selected}

    if len(selected) > target_count:
        raise ValueError(
            f"Required linked entities exceed target count: {len(selected)} > {target_count}. "
            "Reduce work/author diversity or increase target count."
        )

    extras = [
        obj for entity_id, obj in entity_map.items() if entity_id not in selected_ids
    ]
    extras.sort(key=sort_key)

    for obj in extras:
        if len(selected) >= target_count:
            break
        selected.append(obj)

    return selected[:target_count]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """Write JSON objects as deterministic JSONL."""
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def analyze_subset(
    authors: list[dict], works: list[dict], orgs: list[dict], topics: list[dict]
) -> dict:
    """Produce integrity and edge-case metrics for the final subset."""
    author_ids = {obj["id"] for obj in authors}
    org_ids = {obj["id"] for obj in orgs}
    topic_ids = {obj["id"] for obj in topics}

    work_author_missing = []
    work_org_missing = []
    work_topic_missing = []
    linked_work_counts: defaultdict[str, int] = defaultdict(int)

    for work in works:
        for author_entry in work.get("authors") or []:
            author_id = author_entry.get("author_id")
            if author_id:
                if author_id in author_ids:
                    linked_work_counts[author_id] += 1
                else:
                    work_author_missing.append(
                        {"work_id": work["id"], "author_id": author_id}
                    )

            org_id = author_entry.get("org_id")
            if org_id and org_id not in org_ids:
                work_org_missing.append(
                    {"work_id": work["id"], "org_id": org_id, "source": "work.authors"}
                )

        for org_entry in work.get("orgs") or []:
            org_id = org_entry.get("org_id")
            if org_id and org_id not in org_ids:
                work_org_missing.append(
                    {"work_id": work["id"], "org_id": org_id, "source": "work.orgs"}
                )

        for topic_entry in work.get("topics") or []:
            topic_id = topic_entry.get("topic_id")
            if topic_id and topic_id not in topic_ids:
                work_topic_missing.append({"work_id": work["id"], "topic_id": topic_id})

    author_org_missing = []
    for author in authors:
        for org_id in author.get("org_ids") or []:
            if org_id and org_id not in org_ids:
                author_org_missing.append({"author_id": author["id"], "org_id": org_id})

    analysis = {
        "counts": {
            "authors": len(authors),
            "works": len(works),
            "orgs": len(orgs),
            "topics": len(topics),
        },
        "integrity": {
            "missing_work_author_refs": work_author_missing,
            "missing_work_org_refs": work_org_missing,
            "missing_work_topic_refs": work_topic_missing,
            "missing_author_org_refs": author_org_missing,
            "is_fully_linked": not any(
                [
                    work_author_missing,
                    work_org_missing,
                    work_topic_missing,
                    author_org_missing,
                ]
            ),
        },
        "connectivity": {
            "authors_with_selected_works": sum(
                1 for author in authors if linked_work_counts.get(author["id"], 0) > 0
            ),
            "authors_without_selected_works": sum(
                1 for author in authors if linked_work_counts.get(author["id"], 0) == 0
            ),
            "orgs_referenced_by_subset": sum(
                1
                for org in orgs
                if any(org["id"] in (author.get("org_ids") or []) for author in authors)
                or any(
                    org["id"] == org_entry.get("org_id")
                    for work in works
                    for org_entry in (work.get("orgs") or [])
                )
            ),
            "topics_referenced_by_subset": sum(
                1
                for topic in topics
                if any(
                    topic["id"] == topic_entry.get("topic_id")
                    for work in works
                    for topic_entry in (work.get("topics") or [])
                )
            ),
        },
        "edge_cases": {
            "authors_no_orgs": sum(
                1 for author in authors if not (author.get("org_ids") or [])
            ),
            "authors_zero_works": sum(
                1 for author in authors if (author.get("works_count") or 0) == 0
            ),
            "authors_zero_citations": sum(
                1 for author in authors if (author.get("citation_count") or 0) == 0
            ),
            "authors_special_names": sum(
                1 for author in authors if has_special_name(author.get("name"))
            ),
            "works_missing_abstract": sum(
                1 for work in works if not (work.get("abstract") or "").strip()
            ),
            "works_missing_doi": sum(
                1 for work in works if not (work.get("doi") or "").strip()
            ),
            "works_no_authors": sum(
                1 for work in works if not (work.get("authors") or [])
            ),
            "works_author_missing_org": sum(
                1
                for work in works
                if any(
                    not (entry.get("org_id") or "").strip()
                    for entry in (work.get("authors") or [])
                )
            ),
            "works_no_topics": sum(
                1 for work in works if not (work.get("topics") or [])
            ),
            "works_no_orgs": sum(1 for work in works if not (work.get("orgs") or [])),
        },
    }
    return analysis


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a linked 50x4 DTIC test subset")
    parser.add_argument(
        "--input-dir",
        default="data/dtic_compressed",
        help="Directory containing the source DTIC JSONL files",
    )
    parser.add_argument(
        "--output-dir",
        default="tests/dtic_test_subset",
        help="Directory where the linked subset should be written",
    )
    parser.add_argument(
        "--target-count",
        type=int,
        default=50,
        help="Exact number of authors/works/orgs/topics to output",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    target = args.target_count

    authors_map = load_entity_map(input_dir / "dtic_authors_001.jsonl")
    orgs_map = load_entity_map(input_dir / "dtic_orgs_001.jsonl")
    topics_map = load_entity_map(input_dir / "dtic_topics_001.jsonl")
    works = [
        build_work_meta(obj, authors_map, orgs_map, topics_map)
        for obj in iter_jsonl(input_dir / "dtic_works_001.jsonl")
        if obj.get("id")
    ]

    work_categories: OrderedDict[str, tuple[int, Callable[[WorkMeta], bool]]] = (
        OrderedDict(
            [
                (
                    "baseline",
                    (
                        20,
                        lambda meta: (
                            meta.has_abstract
                            and meta.has_doi
                            and meta.has_authors
                            and meta.has_topics
                            and meta.has_orgs
                            and meta.all_authors_present
                            and meta.all_orgs_present
                            and meta.num_authors <= 2
                        ),
                    ),
                ),
                (
                    "missing_abstract",
                    (
                        8,
                        lambda meta: (
                            (not meta.has_abstract)
                            and meta.has_authors
                            and meta.has_topics
                            and meta.has_orgs
                            and meta.all_authors_present
                            and meta.all_orgs_present
                            and meta.num_authors <= 2
                        ),
                    ),
                ),
                (
                    "missing_doi",
                    (
                        5,
                        lambda meta: (
                            (not meta.has_doi)
                            and meta.has_abstract
                            and meta.has_authors
                            and meta.has_topics
                            and meta.has_orgs
                            and meta.all_authors_present
                            and meta.all_orgs_present
                            and meta.num_authors <= 2
                        ),
                    ),
                ),
                (
                    "no_authors",
                    (
                        5,
                        lambda meta: (
                            (not meta.has_authors)
                            and meta.has_abstract
                            and meta.has_topics
                            and meta.has_orgs
                            and meta.all_orgs_present
                        ),
                    ),
                ),
                (
                    "author_missing_org",
                    (
                        5,
                        lambda meta: (
                            meta.has_authors
                            and meta.has_author_missing_org
                            and meta.has_topics
                            and meta.all_authors_present
                            and meta.num_authors <= 3
                        ),
                    ),
                ),
                (
                    "no_topics",
                    (
                        3,
                        lambda meta: (
                            meta.has_authors
                            and (not meta.has_topics)
                            and meta.has_orgs
                            and meta.all_authors_present
                            and meta.all_orgs_present
                            and meta.num_authors <= 2
                        ),
                    ),
                ),
                (
                    "no_orgs",
                    (
                        2,
                        lambda meta: (
                            meta.has_authors
                            and meta.has_topics
                            and (not meta.has_orgs)
                            and meta.all_authors_present
                            and meta.num_authors <= 2
                        ),
                    ),
                ),
                (
                    "older",
                    (
                        2,
                        lambda meta: (
                            meta.has_authors
                            and meta.has_topics
                            and meta.has_orgs
                            and meta.all_authors_present
                            and meta.all_orgs_present
                            and (meta.year is not None and meta.year < 2000)
                            and meta.num_authors <= 2
                        ),
                    ),
                ),
            ]
        )
    )

    selected_work_ids: set[str] = set()
    linked_author_ids: set[str] = set()
    linked_org_ids: set[str] = set()
    linked_topic_ids: set[str] = set()
    selection_breakdown: dict[str, int] = {}

    max_linked_authors = max(target - 6, 40)
    max_linked_orgs = max(target - 5, 45)
    max_linked_topics = target

    selected_work_meta: list[WorkMeta] = []
    for category_name, (quota, predicate) in work_categories.items():
        batch = choose_work_batch(
            works=works,
            predicate=predicate,
            quota=quota,
            selected_ids=selected_work_ids,
            seen_authors=linked_author_ids,
            seen_orgs=linked_org_ids,
            seen_topics=linked_topic_ids,
            max_authors=max_linked_authors,
            max_orgs=max_linked_orgs,
            max_topics=max_linked_topics,
        )
        if len(batch) < quota:
            raise ValueError(
                f"Could not satisfy work category '{category_name}' with quota={quota}; only found {len(batch)} linked candidates."
            )
        selected_work_meta.extend(batch)
        selection_breakdown[category_name] = len(batch)

    if len(selected_work_meta) != target:
        raise ValueError(
            f"Expected {target} works but selected {len(selected_work_meta)}"
        )

    referenced_author_ids = unique_preserve_order(
        author_id
        for meta in selected_work_meta
        for author_id in meta.author_ids
        if author_id in authors_map
    )
    if len(referenced_author_ids) > target:
        raise ValueError(
            f"Selected works reference {len(referenced_author_ids)} unique authors, which exceeds the target author count of {target}."
        )

    selected_author_ids = set(referenced_author_ids)
    extra_author_ids = choose_extra_authors(
        authors_map=authors_map,
        selected_author_ids=selected_author_ids,
        selected_org_ids=linked_org_ids,
        target_count=target,
    )
    selected_author_ids.update(extra_author_ids)

    if len(selected_author_ids) != target:
        raise ValueError(
            f"Expected {target} authors but selected {len(selected_author_ids)}"
        )

    required_org_ids = set(linked_org_ids)
    for author_id in selected_author_ids:
        required_org_ids.update(author_org_ids(authors_map[author_id]))

    required_topic_ids = set(linked_topic_ids)
    topic_entity_map = dict(topics_map)
    for topic_id in required_topic_ids:
        if topic_id not in topic_entity_map:
            topic_entity_map[topic_id] = {
                "id": topic_id,
                "name": f"Derived topic {topic_id.split('_', 1)[-1]}",
                "field": "Derived from selected work references",
                "sources": [{"source": "dtic", "id": topic_id}],
            }

    selected_orgs = fill_entities(
        required_ids=required_org_ids,
        entity_map=orgs_map,
        target_count=target,
        sort_key=lambda obj: (
            0 if obj.get("country") else 1,
            str(obj.get("country", "")),
            str(obj.get("name", "")),
            obj.get("id", ""),
        ),
    )

    selected_topics = fill_entities(
        required_ids=required_topic_ids,
        entity_map=topic_entity_map,
        target_count=target,
        sort_key=lambda obj: (
            0 if str(obj.get("field", "")).lower().find("information") >= 0 else 1,
            str(obj.get("field", "")),
            str(obj.get("name", "")),
            obj.get("id", ""),
        ),
    )

    selected_authors = [
        authors_map[author_id]
        for author_id in unique_preserve_order(
            list(referenced_author_ids) + extra_author_ids
        )
    ]
    selected_works = [meta.raw for meta in selected_work_meta]

    analysis = analyze_subset(
        selected_authors, selected_works, selected_orgs, selected_topics
    )
    analysis["selection_breakdown"] = selection_breakdown
    analysis["linked_reference_counts"] = {
        "linked_authors_from_works": len(referenced_author_ids),
        "required_orgs_from_links": len(required_org_ids),
        "required_topics_from_links": len(required_topic_ids),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "dtic_authors_50.jsonl", selected_authors)
    write_jsonl(output_dir / "dtic_works_50.jsonl", selected_works)
    write_jsonl(output_dir / "dtic_orgs_50.jsonl", selected_orgs)
    write_jsonl(output_dir / "dtic_topics_50.jsonl", selected_topics)

    with (output_dir / "analysis.json").open("w", encoding="utf-8") as handle:
        json.dump(analysis, handle, indent=2, ensure_ascii=False, sort_keys=True)

    report_lines = [
        "# DTIC Test Subset Analysis",
        "",
        f"- Authors: {analysis['counts']['authors']}",
        f"- Works: {analysis['counts']['works']}",
        f"- Orgs: {analysis['counts']['orgs']}",
        f"- Topics: {analysis['counts']['topics']}",
        "",
        "## Integrity",
        f"- Fully linked: {analysis['integrity']['is_fully_linked']}",
        f"- Missing work-author refs: {len(analysis['integrity']['missing_work_author_refs'])}",
        f"- Missing work-org refs: {len(analysis['integrity']['missing_work_org_refs'])}",
        f"- Missing work-topic refs: {len(analysis['integrity']['missing_work_topic_refs'])}",
        f"- Missing author-org refs: {len(analysis['integrity']['missing_author_org_refs'])}",
        "",
        "## Edge Cases",
    ]
    for key, value in analysis["edge_cases"].items():
        report_lines.append(f"- {key}: {value}")

    with (output_dir / "analysis.md").open("w", encoding="utf-8") as handle:
        handle.write("\n".join(report_lines) + "\n")

    print(json.dumps(analysis, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
