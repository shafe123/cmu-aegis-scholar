import os
import gzip
import orjson
import random
import logging
import time
from typing import Optional, List
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel
from ldap3 import Server, Connection, ALL, MODIFY_REPLACE, SUBTREE
from rapidfuzz import process, fuzz

# Setup logging for Docker
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# Config
LDAP_SERVER = os.getenv("LDAP_SERVER", "ldap://localhost:1389")
LDAP_USER = os.getenv("LDAP_ADMIN_DN", "cn=admin,dc=example,dc=org")
LDAP_PASS = os.getenv("LDAP_ADMIN_PASSWORD", "admin")
INPUT_FILE = os.getenv("JSONL_FILE_PATH", "/cmu-aegis-scholar/data/dtic_compressed/dtic_authors_001.jsonl.gz")
ORG_FILE = os.getenv('ORG_JSONL_FILE_PATH', '/cmu-aegis-scholar/data/dtic_compressed/dtic_orgs_001.jsonl.gz')
DOMAINS = ["dtic.mil", "navy.mil", "army.mil", "af.mil", "usmc.mil", "university.edu", "us.gov"]
LETTERS_LIST = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']
CONTACT = LETTERS_LIST[0:26:3]
NO_CONTACT = LETTERS_LIST[1:26:3]
SIMILAR_CONTACT = LETTERS_LIST[2:26:3]

class UserRecord(BaseModel):
    username: str
    name: str
    email: Optional[str] = None
    org: Optional[str] = None

class StatusResponse(BaseModel):
    success: bool
    message: str

def count_records(file_path):
    if not os.path.exists(file_path):
        return 0
    with gzip.open(file_path, 'rb') as f:
        return sum(1 for _ in f)

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
        'objectClass': ['inetOrgPerson']
    }
    
    # We only include the mail attribute if it was actually generated
    if record.email:
        attrs['mail'] = record.email
        
    # Search to determine if we should add or modify
    conn.search(dn, '(objectClass=*)')
    if not conn.entries:
        conn.add(dn, attributes=attrs)
    else:
        if record.email:
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
                    
                    name = data.get('name', '')
                    if not name: 
                        continue
                        
                    first_char = name[0].upper()
                    
                    # 1. Skip the names that start with a letter in the NO_CONTACT variable
                    if first_char in NO_CONTACT:
                        continue
                        
                    # 2. Only add an email if the name starts with the letters in the CONTACT variable
                    if first_char in CONTACT:
                        if 'email' not in data or not data['email']:
                            data['email'] = generate_email(name)
                    
                    if 'org_name' not in data or not data['org_name']:
                        data['org_name'] = generate_org()
                        
                    record = UserRecord(
                        username=data.get('uid', name.replace(' ', '').lower()),
                        name=name,
                        email=data.get('email'),
                        org=data['org_name']
                    )
                    
                    # Speed optimization: direct connection add
                    dn_org = record.org.replace(' ', '').replace(',', '')  # Sanitized
                    dn = f"uid={record.username},ou=users,dc=example,dc={dn_org}"
                    
                    attrs = {
                        'sn': record.name.split()[-1] if ' ' in record.name else record.name,
                        'cn': record.name,
                        'o': record.org,
                        'objectClass': ['inetOrgPerson']
                    }
                    if record.email:
                        attrs['mail'] = record.email
                        
                    conn.add(dn, attributes=attrs)
                    upsert_count += 1

                    out_f.write(orjson.dumps(data) + b'\n')
                    count += 1

                    if count % 1000 == 0:
                        percent = (count / TOTAL_ESTIMATED_RECORDS) * 100 if TOTAL_ESTIMATED_RECORDS else 0
                        logger.info(f"{percent:.1f}% complete - Processed {count} records - Elapsed: {time.time()-start_time:.2f}s")
                
        os.replace(output_file, INPUT_FILE)
        logger.info(f"100% complete - Sync Finished in {time.time()-start_time:.2f}s.")
    except Exception as e:
        if os.path.exists(output_file): os.remove(output_file)
        logger.error(f"Sync failed: {e}")

def generate_org():
    return random.choice(org_names) if org_names else "DefaultOrg"

def generate_org_list(org_file_path):
    orgs = set()
    if os.path.exists(org_file_path):
        try:
            with gzip.open(org_file_path, 'rb') as f:
                for line in f:
                    try:
                        data = orjson.loads(line)
                        orgs.add(data['name'])
                    except:
                        continue
        except Exception as e:
            logger.error(f"Could not read org file: {e}")
            
    if not orgs:
        orgs.add("DefaultOrg")
    return list(orgs)

# --- Generated variables ---

org_names = generate_org_list(ORG_FILE)
TOTAL_ESTIMATED_RECORDS = count_records(INPUT_FILE)

# --- Endpoints ---

@app.post("/upsert", response_model=StatusResponse)
async def http_upsert_bulk(records: List[UserRecord]):
    """Accepts a list of records for manual bulk upserting."""
    server = Server(LDAP_SERVER, get_info=ALL)
    try:
        with Connection(server, user=LDAP_USER, password=LDAP_PASS, auto_bind=True) as conn:
            for record in records:
                if not record.name:
                    continue
                    
                first_char = record.name[0].upper()
                if first_char in NO_CONTACT:
                    continue
                    
                if first_char in CONTACT:
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
        return UserRecord(
            username=str(entry.uid), 
            name=str(entry.cn), 
            email=str(entry.mail) if entry.mail else None
        )

@app.get("/similar-emails")
async def similar_emails(name: str = Query(..., description="Target name to match against SIMILAR_CONTACT candidates")):
    """
    3. Returns the emails for any name that is similar to a name 
    that starts with a letter in SIMILAR_CONTACT variable using rapidfuzz.
    """
    server = Server(LDAP_SERVER, get_info=ALL)
    try:
        with Connection(server, user=LDAP_USER, password=LDAP_PASS, auto_bind=True) as conn:
            # Gather candidates explicitly filtering so they start with a SIMILAR_CONTACT letter
            conn.search("dc=example", "(objectClass=inetOrgPerson)", search_scope=SUBTREE, attributes=['cn', 'mail'])
            
            candidates = {}
            for entry in conn.entries:
                if entry.cn:
                    cn_str = str(entry.cn)
                    if cn_str[0].upper() in SIMILAR_CONTACT:
                        candidates[cn_str] = str(entry.mail) if entry.mail else None
            
            if not candidates:
                return {"similar_emails": []}

            # Uses RapidFuzz to find visually similar names
            matches = process.extract(name, candidates.keys(), scorer=fuzz.WRatio, limit=10)
            
            results = []
            for match_name, score, _ in matches:
                # matching threshold (score of 60) for acceptable similarity
                if score >= 60:
                    email = candidates.get(match_name)
                    if email:
                        results.append({
                            "name": match_name,
                            "email": email,
                            "score": score
                        })
                        
            return {"similar_emails": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sync-file")
async def trigger_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(process_and_sync_file)
    return {"message": "Background sync started."}