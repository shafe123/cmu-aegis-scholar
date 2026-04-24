"""Identity service endpoints and LDAP synchronization helpers."""

import gzip
import json
import logging
import os
import random
import re
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from ldap3 import ALL, SUBTREE, Connection, Server
from ldap3.core.exceptions import LDAPEntryAlreadyExistsResult
from ldap3.utils.dn import escape_rdn
from rapidfuzz import fuzz, process

from app.docs import (
    HEALTH_RESPONSES,
    LOOKUP_RESPONSES,
    STATS_RESPONSES,
    SYNC_FILE_RESPONSES,
)
from app.schemas import LookupResponse, SimilarMatch, UserRecord

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Config - Explicitly stripping whitespace to prevent invalidDNSyntax
LDAP_SERVER = os.getenv("LDAP_SERVER", "ldap://ldap-server:1389").strip()
LDAP_USER = os.getenv("LDAP_ADMIN_DN", "cn=admin,dc=example,dc=org").strip()
LDAP_PASS = os.getenv("LDAP_ADMIN_PASSWORD", "admin").strip()
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "dc=example,dc=org").strip()

AUTHOR_FILE = os.getenv("AUTH_JSONL_FILE_PATH", "/data/dtic_authors_001.jsonl.gz")
ORG_FILE = os.getenv("ORG_JSONL_FILE_PATH", "/data/dtic_orgs_001.jsonl.gz")
DOMAINS = [
    "dtic.mil",
    "navy.mil",
    "army.mil",
    "af.mil",
    "usmc.mil",
    "university.edu",
    "us.gov",
]

_ORG_LIST_CACHE: list[str] | None = None


def _mask_config_value(value: str) -> str:
    """Hide sensitive configuration values in logs."""
    return "<set>" if value else "<not set>"


async def log_startup_config() -> None:
    """Log the effective startup configuration for the identity service."""
    logger.info(
        "Identity service startup configuration:\n"
        "  LDAP_SERVER=%s\n"
        "  LDAP_ADMIN_DN=%s\n"
        "  LDAP_ADMIN_PASSWORD=%s\n"
        "  LDAP_BASE_DN=%s\n"
        "  AUTH_JSONL_FILE_PATH=%s\n"
        "  ORG_JSONL_FILE_PATH=%s",
        LDAP_SERVER,
        LDAP_USER,
        _mask_config_value(LDAP_PASS),
        LDAP_BASE_DN,
        AUTHOR_FILE,
        ORG_FILE,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run startup actions using the FastAPI lifespan hook."""
    await log_startup_config()
    yield


app = FastAPI(lifespan=lifespan)


def clean_uid(text: str) -> str:
    """Return a lowercase LDAP-safe UID derived from the input text."""
    return re.sub(r"[^a-zA-Z0-9.-]", "", text).lower()


def get_org_list() -> list[str]:
    """Load and cache organization names from the configured org data file."""
    global _ORG_LIST_CACHE  # pylint: disable=global-statement

    if _ORG_LIST_CACHE is not None:
        return _ORG_LIST_CACHE

    orgs: set[str] = set()
    if os.path.exists(ORG_FILE):
        try:
            with gzip.open(ORG_FILE, "rb") as file_handle:
                for line in file_handle:
                    try:
                        org_data = json.loads(line)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        continue

                    if "name" in org_data:
                        orgs.add(org_data["name"])
        except OSError:
            pass

    _ORG_LIST_CACHE = list(orgs) if orgs else ["DefaultOrg"]
    logger.info("Loaded %d organizations into cache", len(_ORG_LIST_CACHE))
    return _ORG_LIST_CACHE


@app.get("/health", responses=HEALTH_RESPONSES)
async def health_check() -> dict[str, str]:
    """Return a lightweight health response for container probes."""
    return {
        "status": "ok",
        "service": "identity",
        "ldap_server": LDAP_SERVER,
    }


@app.get("/stats", responses=STATS_RESPONSES)
async def get_stats() -> dict[str, int]:
    """Return basic LDAP population statistics for the identity directory."""
    server = Server(LDAP_SERVER, get_info=ALL)
    try:
        with Connection(server, user=LDAP_USER, password=LDAP_PASS, auto_bind=True) as conn:
            search_base = f"ou=users,{LDAP_BASE_DN}"
            conn.search(search_base, "(objectClass=inetOrgPerson)", attributes=["cn"])
            total = len(conn.entries)
            conn.search(search_base, "(mail=*)", attributes=["cn"])
            with_email = len(conn.entries)
            return {
                "total_in_ldap": total,
                "with_email": with_email,
                "without_email": total - with_email,
            }
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise HTTPException(status_code=500, detail=f"LDAP Error: {exc}") from exc


@app.post("/sync-file", responses=SYNC_FILE_RESPONSES)
async def trigger_sync(background_tasks: BackgroundTasks,
                       force: bool = Query(False)) -> dict[str, str]:
    """Queue a background synchronization job for the author source file."""
    background_tasks.add_task(process_and_sync_file, force=force)
    return {"message": "Sync started. Check docker logs for progress."}


def _build_ldap_attributes(name: str, org: str, email: str | None) -> dict[str, Any]:
    """Build the LDAP attribute payload for a single author record."""
    attrs: dict[str, Any] = {
        "sn": escape_rdn(name.split()[-1] if " " in name else name),
        "cn": name,
        "o": org,
    }
    if email:
        attrs["mail"] = email
    return attrs


def _sync_author_record(conn: Connection,
                        author_data: dict[str, Any],
                        org_names: list[str]) -> bool:
    """Create or skip a single LDAP author record and return whether it was added."""
    name = author_data.get("name", "")
    if not name:
        return False

    email = author_data.get("email")
    if not email and random.random() < 0.5:
        email = f"{name.replace(' ', '.').lower()}@{random.choice(DOMAINS)}"

    org = author_data.get("org_name") or random.choice(org_names)
    safe_uid = escape_rdn(clean_uid(author_data.get("uid", name.replace(" ", ""))))
    dn = f"uid={safe_uid},ou=users,{LDAP_BASE_DN}"
    attrs = _build_ldap_attributes(name, org, email)

    try:
        return bool(conn.add(dn, ["inetOrgPerson", "top"], attrs))
    except LDAPEntryAlreadyExistsResult:
        logger.debug("LDAP entry already exists for dn=%s", dn)
        return False


def process_and_sync_file(force: bool = False) -> None:
    """Load author data from disk and synchronize it into the LDAP directory."""
    if not os.path.exists(AUTHOR_FILE):
        logger.error("File not found: %s", AUTHOR_FILE)
        return

    server = Server(LDAP_SERVER, get_info=ALL)
    try:
        with Connection(server, user=LDAP_USER, password=LDAP_PASS, auto_bind=True) as conn:
            users_ou = f"ou=users,{LDAP_BASE_DN}"
            conn.search(LDAP_BASE_DN, "(ou=users)", SUBTREE)
            if not conn.entries:
                logger.info("Creating ou=users...")
                conn.add(users_ou, ["organizationalUnit", "top"], {"ou": "users"})

            if not force:
                conn.search(users_ou, "(objectClass=inetOrgPerson)", attributes=["cn"])
                existing_records = len(conn.entries)
                if existing_records > 1000:
                    logger.info("Skipping sync: %s records exist.", existing_records)
                    return

            org_names = get_org_list()
            count = 0
            with gzip.open(AUTHOR_FILE, "rb") as file_handle:
                for line in file_handle:
                    if not line.strip():
                        continue

                    try:
                        author_data = json.loads(line)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        logger.debug("Skipping unreadable author record during sync.")
                        continue

                    if _sync_author_record(conn, author_data, org_names):
                        count += 1
                        if count % 1000 == 0:
                            logger.info("Synced %s records...", count)

            logger.info("Final: Sync finished. %s records added.", count)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Critical Sync Error: %s", exc)


@app.get("/lookup", response_model=LookupResponse, responses=LOOKUP_RESPONSES)
async def lookup_record(name: str = Query(...)) -> LookupResponse:
    """Return an exact identity match plus fuzzy-match suggestions for a name query."""
    server = Server(LDAP_SERVER, get_info=ALL)
    try:
        with Connection(server, user=LDAP_USER, password=LDAP_PASS, auto_bind=True) as conn:
            search_base = f"ou=users,{LDAP_BASE_DN}"
            exact_record = None

            conn.search(search_base, f"(cn={name})", attributes=["mail", "cn", "uid", "o"])
            if conn.entries:
                entry = conn.entries[0]
                exact_record = UserRecord(
                    username=str(entry.uid) if hasattr(entry, "uid") else clean_uid(str(entry.cn)),
                    name=str(entry.cn),
                    email=str(entry.mail) if hasattr(entry, "mail") and entry.mail else None,
                    org=str(entry.o) if hasattr(entry, "o") else None,
                )

            conn.search(
                search_base,
                "(&(objectClass=inetOrgPerson)(mail=*))",
                attributes=["cn", "mail", "o"],
            )
            candidate_map = {
                str(entry.cn): {
                    "email": str(entry.mail),
                    "org": str(entry.o) if hasattr(entry, "o") else None,
                }
                for entry in conn.entries
            }

            matches = process.extract(name, list(candidate_map.keys()), scorer=fuzz.ratio, limit=10)
            results = [
                SimilarMatch(
                    name=match[0],
                    email=candidate_map[match[0]]["email"],
                    org=candidate_map[match[0]]["org"],
                    score=round(match[1], 2),
                )
                for match in matches
                if not exact_record or match[0] != exact_record.name
            ]

            if exact_record and results:
                message = "Exact match and suggestions provided."
            elif exact_record:
                message = "Exact match only."
            else:
                message = "Suggestions provided."

            return LookupResponse(
                exact_match=exact_record,
                similar_records=results or [],
                message=message,
            )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise HTTPException(status_code=500, detail=str(exc)) from exc
