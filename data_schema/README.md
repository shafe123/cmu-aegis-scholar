# Database Schema Documentation

This directory contains JSON schemas and example data for the AEGIS Scholar database structure.

## Files

### Schema Definition
- **database_schemas.json**: JSON Schema definitions for all entity types

### Example Data (by Entity Type)
- **sample_organizations_tiny.json**: Sample organizations (institutions, funders, publishers)
- **sample_authors_tiny.json**: Sample authors with affiliations
- **sample_topics_tiny.json**: Sample research topics
- **sample_works_tiny.json**: Sample publications with relationships

## Entity Types

### 1. Organizations ([sample_organizations_tiny.json](sample_organizations_tiny.json))
Represents research institutions, funding agencies, and publishers.

**Key Fields:**
- `id`: Primary identifier - GUID prefixed with 'org_' (e.g., org_a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d)
- `name`: Official display name
- `country`: ISO country code or full name
- `type`: Organization type (institution, funder, publisher, other)
- `sources`: Array of source objects with `source` name and `id` from each database
- `last_updated`: Timestamp of last update (ISO 8601 date-time)

**Example:**
```json
{
  "id": "org_a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
  "name": "Carnegie Mellon University",
  "country": "US",
  "type": "institution",
  "sources": [
    {
      "source": "ror",
      "id": "041nk4h53"
    },
    {
      "source": "openalex",
      "id": "I130238516"
    }
  ],
  "last_updated": "2024-01-15T10:30:00Z"
}
```

### 2. Authors ([sample_authors_tiny.json](sample_authors_tiny.json))
Individual researchers who contribute to works.

**Key Fields:**
- `id`: Primary identifier - GUID prefixed with 'author_' (e.g., author_d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a)
- `name`: Full display name
- `org_ids`: Array of organization IDs (current and past affiliations)
- `h_index`, `citation_count`, `works_count`: Bibliometric data
- `sources`: Array of source objects with `source` name and `id` from each database
- `last_updated`: Timestamp of last update (ISO 8601 date-time)

**Example:**
```json
{
  "id": "author_d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a",
  "name": "Dr. Sarah Chen",
  "org_ids": ["org_a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"],
  "h_index": 42,
  "citation_count": 8924,
  "works_count": 156,
  "sources": [
    {
      "source": "orcid",
      "id": "0000-0002-1234-5678"
    },
    {
      "source": "openalex",
      "id": "A2089743210"
    }
  ],
  "last_updated": "2024-02-10T14:22:00Z"
}
```

### 3. Topics ([sample_topics_tiny.json](sample_topics_tiny.json))
Research subject areas and topics from OpenAlex taxonomy.

**Key Fields:**
- `id`: Primary identifier - GUID prefixed with 'topic_' (e.g., topic_f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8a9b0c)
- `name`: Topic name
- `field`, `subfield`, `domain`: Hierarchical categorization
- `sources`: Array of source objects with `source` name and `id` from each database
- `last_updated`: Timestamp of last update (ISO 8601 date-time)

**Example:**
```json
{
  "id": "topic_f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8a9b0c",
  "name": "Network Security and Intrusion Detection",
  "field": "Computer Science",
  "subfield": "Computer Networks and Communications",
  "domain": "Physical Sciences",
  "sources": [
    {
      "source": "openalex",
      "id": "T10199"
    }
  ],
  "last_updated": "2024-01-20T12:00:00Z"
}
```

### 4. Works ([sample_works_tiny.json](sample_works_tiny.json))
Published research papers, reports, and other scholarly outputs.

**Key Fields:**
- `id`: Primary identifier - GUID prefixed with 'work_' (e.g., work_b8c9d0e1-f2a3-4b4c-5d6e-7f8a9b0c1d2e)
- `title`, `abstract`: Content metadata
- `publication_date`: ISO 8601 date
- `citation_count`: Number of citations
- `authors`: Array of author objects with `author_id` and `org_id` (affiliation at time of publication)
- `orgs`: Array of organization objects with `org_id` and `role` (funder, publisher, affiliation)
- `topics`: Array of topic objects with `topic_id` and `score` (relevance score 0.0-1.0)
- `sources`: Array of source objects with `source` name and `id` from each database
- `last_updated`: Timestamp of last update (ISO 8601 date-time)

**Example:**
```json
{
  "id": "work_b8c9d0e1-f2a3-4b4c-5d6e-7f8a9b0c1d2e",
  "title": "Adversarial Machine Learning in Network Security Systems",
  "abstract": "This paper presents a comprehensive study...",
  "publication_date": "2023-05-15",
  "citation_count": 247,
  "authors": [
    {
      "author_id": "author_d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a",
      "org_id": "org_a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
    },
    {
      "author_id": "author_e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b",
      "org_id": "org_b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e"
    }
  ],
  "orgs": [
    {
      "org_id": "org_c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f",
      "role": "funder"
    }
  ],
  "topics": [
    {
      "topic_id": "topic_f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8a9b0c",
      "score": 0.95
    },
    {
      "topic_id": "topic_a7b8c9d0-e1f2-4a3b-4c5d-6e7f8a9b0c1d",
      "score": 0.88
    }
  ],
  "sources": [
    {
      "source": "openalex",
      "id": "W3124567890"
    },
    {
      "source": "crossref",
      "id": "10.1234/example.2023.001"
    }
  ],
  "venue": "IEEE Symposium on Security and Privacy",
  "doi": "10.1234/example.2023.001",
  "url": "https://doi.org/10.1234/example.2023.001",
  "last_updated": "2024-02-15T16:45:00Z"
}
```

## Relationships

The schema uses **enriched arrays with nested objects** for many-to-many relationships:

### Work ↔ Authors (Many-to-Many)
- Works contain `authors[]` array with `author_id` and `org_id` fields
- The `org_id` captures the author's affiliation at the time of publication
- Multiple authors can collaborate on one work
- One author can have many works

### Work ↔ Organizations (Many-to-Many)
- Works contain `orgs[]` array with `org_id` and `role` fields
- The `role` specifies the organization's relationship (funder, publisher, affiliation, other)
- Organizations can be associated with many works in different roles

### Work ↔ Topics (Many-to-Many)
- Works contain `topics[]` array with `topic_id` and `score` fields
- The `score` indicates relevance (0.0-1.0) of the topic to the work
- Each work can be categorized under multiple topics
- Topics can be associated with many works

### Author ↔ Organizations (Many-to-Many)
- Authors contain `org_ids[]` field
- Represents current and past institutional affiliations
- Authors may be affiliated with multiple institutions
- Institutions have many researchers

## Data Sources

- **OpenAlex**: Primary source for works, authors, topics, and organizations
- **Crossref**: Additional metadata for DOIs and citations
- **DTIC**: Defense Technical Information Center publications
- **ROR**: Research Organization Registry for institution IDs
- **ORCID**: Author identifier system

## Query Examples

### Find all works by an author
```python
import json

# Load works and filter by author ID
with open('sample_works_tiny.json') as f:
    works = json.load(f)

author_works = [
    work for work in works
    if any(author['author_id'] == "author_d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a" 
           for author in work['authors'])
]
```

### Find all authors affiliated with an organization
```python
import json

# Load authors and filter by organization ID
with open('sample_authors_tiny.json') as f:
    authors = json.load(f)

org_authors = [
    author for author in authors
    if "org_a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d" in author['org_ids']
]
```

### Find all works on a specific topic
```python
import json

# Load works and filter by topic ID
with open('sample_works_tiny.json') as f:
    works = json.load(f)

topic_works = [
    work for work in works
    if any(topic['topic_id'] == "topic_f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8a9b0c" 
           for topic in work['topics'])
]
```

### Find collaborators of an author
```python
import json

# Get all works by the author, then extract unique co-author IDs
with open('sample_works_tiny.json') as f:
    works = json.load(f)
with open('sample_authors_tiny.json') as f:
    authors = json.load(f)

author_id = "author_d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a"
author_works = [
    work for work in works
    if any(author['author_id'] == author_id for author in work['authors'])
]

coauthor_ids = {
    author['author_id']
    for work in author_works
    for author in work['authors']
    if author['author_id'] != author_id
}

coauthors = [
    author for author in authors
    if author['id'] in coauthor_ids
]
```

### Get organization details for an author's affiliations
```python
import json

with open('sample_authors_tiny.json') as f:
    authors = json.load(f)
with open('sample_organizations_tiny.json') as f:
    organizations = json.load(f)

author = next(a for a in authors if a['id'] == "author_d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a")
author_orgs = [
    org for org in organizations
    if org['id'] in author['org_ids']
]
```

### Find works funded by a specific organization
```python
import json

with open('sample_works_tiny.json') as f:
    works = json.load(f)

funded_works = [
    work for work in works
    if any(org['org_id'] == "org_c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f" and org['role'] == "funder"
           for org in work['orgs'])
]
```

### Get high-relevance topics for a work
```python
import json

with open('sample_works_tiny.json') as f:
    works = json.load(f)

work = next(w for w in works if w['id'] == "work_b8c9d0e1-f2a3-4b4c-5d6e-7f8a9b0c1d2e")
high_relevance_topics = sorted(
    [topic for topic in work['topics'] if topic['score'] > 0.8],
    key=lambda t: t['score'],
    reverse=True
)
```

## Validation

To validate data against these schemas, use a JSON Schema validator:

```python
import json
from jsonschema import validate, ValidationError

# Load schemas and data
with open('database_schemas.json') as f:
    schemas = json.load(f)
with open('sample_works_tiny.json') as f:
    works = json.load(f)

# Validate work objects
work_schema = schemas['definitions']['Work']
for work in works:
    try:
        validate(instance=work, schema=work_schema)
    except ValidationError as e:
        print(f"Invalid work: {work['id']}")
        print(f"Error: {e.message}")
```

## Notes

- **Primary IDs**: All entities use GUID-based primary identifiers with entity-type prefixes:
  - Organizations: `org_<uuid>` (e.g., org_a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d)
  - Authors: `author_<uuid>` (e.g., author_d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a)
  - Topics: `topic_<uuid>` (e.g., topic_f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8a9b0c)
  - Works: `work_<uuid>` (e.g., work_b8c9d0e1-f2a3-4b4c-5d6e-7f8a9b0c1d2e)
- **Sources**: The original IDs from external databases (ORCID, ROR, OpenAlex, DOI, etc.) are preserved in the `sources` array
- All ID fields should be unique within their entity type
- Arrays should contain unique values (no duplicate IDs)
- Date fields use ISO 8601 format (YYYY-MM-DD)
- Timestamp fields (`last_updated`) use ISO 8601 date-time format (YYYY-MM-DDTHH:MM:SSZ)
- Required fields are marked in the schema; others are optional
- Each entity type is stored in a separate JSON file for easier management
- Works use nested objects (not just IDs) for authors, orgs, and topics to capture additional context:
  - `authors[]`: includes author's affiliation at time of publication
  - `orgs[]`: includes organization's role (funder, publisher, affiliation)
  - `topics[]`: includes relevance score for each topic
