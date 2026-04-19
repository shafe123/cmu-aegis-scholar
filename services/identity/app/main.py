import os
import gzip
import orjson
import random
import logging
import re
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query

from ldap3 import Server, Connection, ALL, SUBTREE
from ldap3.core.exceptions import LDAPEntryAlreadyExistsResult
from ldap3.utils.dn import escape_rdn
from rapidfuzz import process, fuzz

from .schemas import LookupResponse, SimilarMatch, UserRecord

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Config - Explicitly stripping whitespace to prevent invalidDNSyntax
LDAP_SERVER = os.getenv("LDAP_SERVER", "ldap://ldap-server:1389").strip()
LDAP_USER = os.getenv("LDAP_ADMIN_DN", "cn=admin,dc=example,dc=org").strip()
LDAP_PASS = os.getenv("LDAP_ADMIN_PASSWORD", "admin").strip()
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "dc=example,dc=org").strip()

INPUT_FILE = os.getenv("AUTH_JSONL_FILE_PATH", "/data/dtic_authors_001.jsonl.gz")
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


def _mask_config_value(value: str) -> str:
    return "<set>" if value else "<not set>"


@app.on_event("startup")
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
        INPUT_FILE,
        ORG_FILE,
    )


def clean_uid(text: str) -> str:
    """Removes any characters that are illegal in an LDAP UID."""
    return re.sub(r"[^a-zA-Z0-9.-]", "", text).lower()


def get_org_list() -> set[str]:
    orgs = set()
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
    return orgs if orgs else set("DefaultOrg")


@app.get("/stats")
async def get_stats():
    server = Server(LDAP_SERVER, get_info=ALL)
    try:
        with Connection(
            server, user=LDAP_USER, password=LDAP_PASS, auto_bind=True
        ) as conn:
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


@app.post("/sync-file")
async def trigger_sync(background_tasks: BackgroundTasks, force: bool = Query(False)):
    background_tasks.add_task(process_and_sync_file, force=force)
    return {"message": "Sync started. Check docker logs for progress."}


def process_and_sync_file(force: bool = False):
    if not os.path.exists(INPUT_FILE):
        logger.error(f"File not found: {INPUT_FILE}")
        return

    server = Server(LDAP_SERVER, get_info=ALL)
    try:
        # The 'auto_bind' here uses the LDAP_USER (Admin DN)
        with Connection(
            server, user=LDAP_USER, password=LDAP_PASS, auto_bind=True
        ) as conn:
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
            with gzip.open(INPUT_FILE, "rb") as f:
                count = 0
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = orjson.loads(line)
                        name = data.get("name", "")
                        if not name:
                            continue

                        email = None
                        if random.random() < 0.5:
                            email = (
                                data.get("email")
                                or f"{name.replace(' ', '.').lower()}@{random.choice(DOMAINS)}"
                            )

                        org = data.get("org_name") or random.choice(org_names)

                        # Use escape_rdn to prevent invalidDNSyntax for users
                        safe_uid = escape_rdn(
                            clean_uid(data.get("uid", name.replace(" ", "")))
                        )
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
                            continue
                    except Exception:
                        continue
            logger.info(f"Final: Sync finished. {count} records added.")
    except Exception as e:
        logger.error(f"Critical Sync Error: {e}")


@app.get("/lookup", response_model=LookupResponse)
async def lookup_record(name: str = Query(...)):
    server = Server(LDAP_SERVER, get_info=ALL)
    try:
        with Connection(
            server, user=LDAP_USER, password=LDAP_PASS, auto_bind=True
        ) as conn:
            search_base = f"ou=users,{LDAP_BASE_DN}"
            conn.search(
                search_base, f"(cn={name})", attributes=["mail", "cn", "uid", "o"]
            )

            if conn.entries:
                e = conn.entries[0]
                if hasattr(e, "mail") and e.mail:
                    return LookupResponse(
                        record=UserRecord(
                            username=str(e.uid),
                            name=str(e.cn),
                            email=str(e.mail),
                            org=str(e.o) if hasattr(e, "o") else None,
                        ),
                        message="Match found.",
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

            matches = process.extract(
                name, list(candidate_map.keys()), scorer=fuzz.ratio, limit=10
            )
            results = [
                SimilarMatch(
                    name=m[0],
                    email=candidate_map[m[0]]["email"],
                    org=candidate_map[m[0]]["org"],
                    score=round(m[1], 2),
                )
                for m in matches
            ]
            return LookupResponse(
                similar_records=results, message="Suggestions provided."
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
