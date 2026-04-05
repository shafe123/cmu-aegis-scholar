import os
import gzip
import orjson
import random
import logging
import time
from typing import Optional, List
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel
from ldap3 import Server, Connection, ALL, MODIFY_REPLACE

# Setup logging for Docker
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# Config
LDAP_SERVER = os.getenv("LDAP_SERVER", "ldap://localhost:1389")
LDAP_USER = os.getenv("LDAP_ADMIN_DN", "cn=admin,dc=example,dc=org")
LDAP_PASS = os.getenv("LDAP_ADMIN_PASSWORD", "admin")
INPUT_FILE = os.getenv("JSONL_FILE_PATH", "/data/dtic_authors_001.jsonl.gz")
TOTAL_ESTIMATED_RECORDS = 94000 
DOMAINS = ["dtic.mil", "navy.mil", "army.mil", "af.mil", "usmc.mil", "university.edu", "us.gov"]

class UserRecord(BaseModel):
    username: str
    name: str
    email: Optional[str] = None

class StatusResponse(BaseModel):
    success: bool
    message: str

def generate_email(name: str) -> str:
    punc = ['.', '-', '_']
    clean_name = name.replace('.', '').lower().replace(' ', random.choice(punc))
    return f"{clean_name}@{random.choice(DOMAINS)}"

def perform_upsert(conn: Connection, record: UserRecord):
    """Internal helper to upsert a single record into an active LDAP connection."""
    dn = f"uid={record.username},ou=users,dc=example,dc=org"
    attrs = {
        'sn': record.name.split()[-1] if ' ' in record.name else record.name,
        'cn': record.name,
        'mail': record.email,
        'objectClass': ['inetOrgPerson']
    }
    # Search to determine if we should add or modify
    conn.search(dn, '(objectClass=*)')
    if not conn.entries:
        conn.add(dn, attributes=attrs)
    else:
        conn.modify(dn, {'mail': [(MODIFY_REPLACE, [record.email])]})

def process_and_sync_file():
    """Optimized batch processing for the 94k record JSONL file."""
    output_file = INPUT_FILE + ".tmp"
    if not os.path.exists(INPUT_FILE):
        logger.error(f"File {INPUT_FILE} not found!")
        return

    start_time = time.time()
    server = Server(LDAP_SERVER, get_info=ALL)
    
    try:
        with Connection(server, user=LDAP_USER, password=LDAP_PASS, auto_bind=True) as conn:
            with gzip.open(INPUT_FILE, "rb") as f, gzip.open(output_file, "wb", compresslevel=5) as out_f:
                count = 0
                upsert_count = 0
                logger.info(f"0.0% complete - Starting batch sync (Target: ~{TOTAL_ESTIMATED_RECORDS} records)...")

                for line in f:
                    if not line.strip(): continue
                    data = orjson.loads(line)
                    
                    if 'email' not in data or not data['email']:
                        data['email'] = generate_email(data['name'])
                        record = UserRecord(
                            username=data.get('uid', data['name'].replace(' ', '').lower()),
                            name=data['name'],
                            email=data['email']
                        )
                        # Speed optimization: direct connection add
                        dn = f"uid={record.username},ou=users,dc=example,dc=org"
                        conn.add(dn, attributes={
                            'sn': record.name.split()[-1] if ' ' in record.name else record.name,
                            'cn': record.name,
                            'mail': record.email,
                            'objectClass': ['inetOrgPerson']
                        })
                        upsert_count += 1

                    out_f.write(orjson.dumps(data) + b'\n')
                    count += 1

                    if count % 1000 == 0:
                        percent = (count / TOTAL_ESTIMATED_RECORDS) * 100
                        logger.info(f"{percent:.1f}% complete - Processed {count} records - Elapsed: {time.time()-start_time:.2f}s")
                
        os.replace(output_file, INPUT_FILE)
        logger.info(f"100% complete - Sync Finished in {time.time()-start_time:.2f}s.")
    except Exception as e:
        if os.path.exists(output_file): os.remove(output_file)
        logger.error(f"Sync failed: {e}")

# --- Endpoints ---

@app.post("/upsert", response_model=StatusResponse)
async def http_upsert_bulk(records: List[UserRecord]):
    """Accepts a list of records for manual bulk upserting."""
    server = Server(LDAP_SERVER, get_info=ALL)
    try:
        with Connection(server, user=LDAP_USER, password=LDAP_PASS, auto_bind=True) as conn:
            for record in records:
                if not record.email:
                    record.email = generate_email(record.name)
                perform_upsert(conn, record)
        return {"success": True, "message": f"Successfully upserted {len(records)} records."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search", response_model=UserRecord)
async def search_by_name(name: str = Query(...)):
    server = Server(LDAP_SERVER, get_info=ALL)
    with Connection(server, user=LDAP_USER, password=LDAP_PASS, auto_bind=True) as conn:
        conn.search("ou=users,dc=example,dc=org", f"(cn={name})", attributes=['mail', 'cn', 'uid'])
        if not conn.entries: raise HTTPException(status_code=404, detail="User not found")
        entry = conn.entries[0]
        return UserRecord(username=str(entry.uid), name=str(entry.cn), email=str(entry.mail))

@app.post("/sync-file")
async def trigger_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(process_and_sync_file)
    return {"message": "Background sync started."}