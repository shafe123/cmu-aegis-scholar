import gzip
import logging
import os
import random
import re
from contextlib import asynccontextmanager

import orjson
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from ldap3 import ALL, SUBTREE, Connection, Server
from ldap3.core.exceptions import LDAPEntryAlreadyExistsResult
from ldap3.utils.dn import escape_rdn
from rapidfuzz import fuzz, process

from .docs import (
    HEALTH_RESPONSES,
    LOOKUP_RESPONSES,
    STATS_RESPONSES,
    SYNC_FILE_RESPONSES,
)
from .schemas import LookupResponse, SimilarMatch, UserRecord

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
    return "<set>" if value else "<not set>"


async def log_startup_config():
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
async def lifespan(app: FastAPI):
    await log_startup_config()
    yield


app = FastAPI(lifespan=lifespan)


def clean_uid(text: str) -> str:
    """Removes any characters that are illegal in an LDAP UID."""
    return re.sub(r"[^a-zA-Z0-9.-]", "", text).lower()


def get_org_list() -> list[str]:
    global _ORG_LIST_CACHE

    if _ORG_LIST_CACHE is not None:
        return _ORG_LIST_CACHE

    orgs: set[str] = set()
    if os.path.exists(ORG_FILE):
        try:
            with gzip.open(ORG_FILE, "rb") as f:
                for line in f:
                    try:
                        d = orjson.loads(line)
                        if "name" in d:
                            orgs.add(d["name"])
                    except:  # noqa: E722
                        continue
        except:  # noqa: E722
            pass

    _ORG_LIST_CACHE = list(orgs) if orgs else ["DefaultOrg"]
    logger.info("Loaded %d organizations into cache", len(_ORG_LIST_CACHE))
    return _ORG_LIST_CACHE


@app.get("/health", responses=HEALTH_RESPONSES)
async def health_check():
    return {
        "status": "ok",
        "service": "identity",
        "ldap_server": LDAP_SERVER,
    }


@app.get("/stats", responses=STATS_RESPONSES)
async def get_stats():
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LDAP Error: {str(e)}") from e


@app.post("/sync-file", responses=SYNC_FILE_RESPONSES)
async def trigger_sync(background_tasks: BackgroundTasks, force: bool = Query(False)):
    background_tasks.add_task(process_and_sync_file, force=force)
    return {"message": "Sync started. Check docker logs for progress."}


def process_and_sync_file(force: bool = False):
    if not os.path.exists(AUTHOR_FILE):
        logger.error(f"File not found: {AUTHOR_FILE}")
        return

    server = Server(LDAP_SERVER, get_info=ALL)
    try:
        # The 'auto_bind' here uses the LDAP_USER (Admin DN)
        with Connection(server, user=LDAP_USER, password=LDAP_PASS, auto_bind=True) as conn:
            # Create OU if missing
            users_ou = f"ou=users,{LDAP_BASE_DN}"
            conn.search(LDAP_BASE_DN, "(ou=users)", search_scope=SUBTREE)
            if not conn.entries:
                logger.info("Creating ou=users...")
                conn.add(
                    users_ou,
                    objectClass=["organizationalUnit", "top"],
                    attributes={"ou": "users"},
                )

            if not force:
                conn.search(users_ou, "(objectClass=inetOrgPerson)", attributes=["cn"])
                if len(conn.entries) > 1000:
                    logger.info(f"Skipping sync: {len(conn.entries)} records exist.")
                    return

            org_names = get_org_list()
            with gzip.open(AUTHOR_FILE, "rb") as f:
                count = 0
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        author_data = orjson.loads(line)
                        name = author_data.get("name", "")
                        if not name:
                            continue

                        email = None
                        if random.random() < 0.5:
                            email = (
                                author_data.get("email") or f"{name.replace(' ', '.').lower()}@{random.choice(DOMAINS)}"
                            )

                        org = author_data.get("org_name") or random.choice(org_names)

                        # Use escape_rdn to prevent invalidDNSyntax for users
                        safe_uid = escape_rdn(clean_uid(author_data.get("uid", name.replace(" ", ""))))
                        dn = f"uid={safe_uid},ou=users,{LDAP_BASE_DN}"

                        attrs = {
                            "sn": escape_rdn(name.split()[-1] if " " in name else name),
                            "cn": name,
                            "o": org,
                            "objectClass": ["inetOrgPerson", "top"],
                        }
                        if email:
                            attrs["mail"] = email

                        try:
                            if conn.add(dn, attributes=attrs):
                                count += 1
                                if count % 1000 == 0:
                                    logger.info(f"Synced {count} records...")
                        except LDAPEntryAlreadyExistsResult:
                            logger.debug("LDAP entry already exists for dn=%s", dn)
                            continue
                    except Exception as e:
                        logger.exception("Failed to process author record during sync: %s", e)
                        continue
            logger.info(f"Final: Sync finished. {count} records added.")
    except Exception as e:
        logger.error(f"Critical Sync Error: {e}")


@app.get("/lookup", response_model=LookupResponse, responses=LOOKUP_RESPONSES)
async def lookup_record(name: str = Query(...)):
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

            # Fuzzy logic with fuzz.ratio for your 54.55 score requirement
            conn.search(
                search_base,
                "(&(objectClass=inetOrgPerson)(mail=*))",
                attributes=["cn", "mail", "o"],
            )
            candidate_map = {
                str(e.cn): {
                    "email": str(e.mail),
                    "org": str(e.o) if hasattr(e, "o") else None,
                }
                for e in conn.entries
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
    except Exception as entry:
        raise HTTPException(status_code=500, detail=str(entry)) from entry
