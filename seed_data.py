#!/usr/bin/env python3
"""
SENAITE LIMS Comprehensive Data Seeder
Populates a blank local SENAITE LIMS instance with beautiful, functional demonstration data.
"""
import requests
import re
import time
import sys
from datetime import datetime, timedelta

BASE = "http://localhost:8080/senaite"
AUTH = ("admin", "admin")

s = requests.Session()
s.auth = AUTH

# Color codes
OK   = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
INFO = "\033[94m→\033[0m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ─────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────

def get_csrf():
    """Fetches a fresh global CSRF token from SENAITE."""
    r = s.get(f"{BASE}/@@authenticator")
    tokens = re.findall(r'value="([^"]+)"', r.text, re.I)
    return tokens[0] if tokens else ""

def api_get_all(endpoint):
    """Fetches all items of a given content type using SENAITE's JSON API."""
    all_items = []
    page = 1
    while True:
        r = s.get(
            f"{BASE}/@@API/senaite/v1/{endpoint}",
            params={"page": page, "pagesize": 100},
            headers={"Accept": "application/json"}
        )
        if not r.ok:
            break
        data = r.json()
        items = data.get("items", [])
        if not items:
            break
        all_items.extend(items)
        if len(items) < 100 or page >= data.get("pages", 1):
            break
        page += 1
    return all_items

def lookup_uid(endpoint, match_key, match_val):
    """Robust local cache lookup for UIDs using the API list."""
    items = api_get_all(endpoint)
    for item in items:
        # Match case-insensitively or exactly
        val = item.get(match_key, "")
        if str(val).strip().lower() == str(match_val).strip().lower():
            return item.get("uid", "")
    return ""

def lookup_client_contact_uid(client_uid, contact_name):
    """Finds the contact UID inside a specific client."""
    items = api_get_all("contact")
    for item in items:
        fullname = item.get("title", "") or item.get("fullname", "")
        if contact_name.lower() in fullname.lower():
            return item.get("uid", "")
    return ""

def create_archetype_object(container_url, portal_type, fields, label):
    """Creates a Plone Archetypes object using the standard portal_factory forms."""
    # Step 1: GET createObject to get redirected to portal_factory edit page
    r1 = s.get(f"{container_url}/createObject", params={"type_name": portal_type}, allow_redirects=False)
    edit_url = r1.headers.get("Location", "")
    if not edit_url:
        print(f"  {FAIL} FAILED : No edit redirect for {label}")
        return None

    # Step 2: GET the edit page to retrieve the CSRF and form action
    r2 = s.get(edit_url)
    csrf_tokens = re.findall(r'_authenticator.*?value="([^"]+)"', r2.text, re.I)
    form_actions = re.findall(r'<form[^>]*action="([^"]+)"', r2.text)
    if not csrf_tokens or not form_actions:
        print(f"  {FAIL} FAILED : Could not parse form for {label}")
        return None

    authenticator = csrf_tokens[0]
    form_action = form_actions[0]
    save_url = form_action.replace("/edit", "/base_edit") if "/edit" == form_action[-5:] else form_action
    if not save_url.endswith("base_edit"):
        save_url = form_action

    # Step 3: Submit POST form data to save the object
    payload = {
        "_authenticator": authenticator,
        "form.submitted": "1",
        "form.button.save": "Save",
        **fields
    }
    r3 = s.post(save_url, data=payload, allow_redirects=False)
    if r3.status_code in (200, 302):
        if r3.status_code == 302:
            obj_url = r3.headers.get("Location", "").split("?")[0]
            if obj_url.endswith("/view"):
                obj_url = obj_url[:-5]
        else:
            obj_url = save_url.replace("/base_edit", "")
        print(f"  {OK} CREATED: {label}")
        return obj_url
    else:
        print(f"  {FAIL} FAILED : {label} (HTTP {r3.status_code})")
        return None

def create_dexterity_object(add_form_url, fields, label):
    """Creates a Plone Dexterity object using the standard z3c.form ++add++ forms."""
    csrf = get_csrf()
    payload = {
        "_authenticator": csrf,
        "form.buttons.save": "Save",
        **fields
    }
    r = s.post(add_form_url, data=payload, allow_redirects=False)
    if r.status_code in (200, 302):
        # 302 means success redirect
        print(f"  {OK} CREATED: {label}")
        return True
    else:
        print(f"  {FAIL} FAILED : {label} (HTTP {r.status_code})")
        return False

# ─────────────────────────────────────────────────────────────
# Seeding script
# ─────────────────────────────────────────────────────────────

print("\n" + "═"*66)
print(f"  {BOLD}SENAITE LIMS — AUTOMATED COMPREHENSIVE DATA SEEDER{RESET}")
print("═"*66)

# ══ 1. LAB MANAGER (LabContact) ══════════════════════════════
print(f"\n{INFO} [1/8] Checking Lab Manager Contact...")
lm_uid = lookup_uid("labcontact", "title", "Lab Manager")
if lm_uid:
    print(f"  {INFO} EXISTS : Lab Manager (UID: {lm_uid})")
else:
    fields = {
        "Firstname": "Lab",
        "Surname": "Manager",
        "EmailAddress": "manager@biogenix.com"
    }
    created_url = create_archetype_object(
        f"{BASE}/bika_setup/bika_labcontacts",
        "LabContact",
        fields,
        "Lab Manager"
    )
    lm_uid = lookup_uid("labcontact", "title", "Lab Manager")

if not lm_uid:
    print(f"  {FAIL} CRITICAL ERROR: Failed to obtain Lab Manager UID.")
    sys.exit(1)

# ══ 2. LAB DEPARTMENTS ═══════════════════════════════════════
print(f"\n{INFO} [2/8] Checking Lab Departments...")
dept_uid = lookup_uid("department", "title", "Main Laboratory")
if dept_uid:
    print(f"  {INFO} EXISTS : Main Laboratory (UID: {dept_uid})")
else:
    fields = {
        "form.widgets.title": "Main Laboratory",
        "form.widgets.department_id": "LAB",
        "form.widgets.manager": lm_uid
    }
    create_dexterity_object(
        f"{BASE}/setup/departments/++add++Department",
        fields,
        "Main Laboratory"
    )
    dept_uid = lookup_uid("department", "title", "Main Laboratory")

if not dept_uid:
    print(f"  {FAIL} CRITICAL ERROR: Failed to obtain Department UID.")
    sys.exit(1)

# ══ 3. ANALYSIS CATEGORIES ══════════════════════════════════
print(f"\n{INFO} [3/8] Checking Analysis Categories...")
categories = [
    "Clinical Chemistry",
    "Haematology",
    "Microbiology",
    "Heavy Metals",
    "Water Quality",
    "Agricultural",
    "Pharmaceuticals"
]
cat_uids = {}
for cat in categories:
    uid = lookup_uid("analysiscategory", "title", cat)
    if uid:
        cat_uids[cat] = uid
        print(f"  {INFO} EXISTS : {cat}")
    else:
        fields = {
            "form.widgets.title": cat,
            "form.widgets.department": dept_uid
        }
        create_dexterity_object(
            f"{BASE}/setup/analysiscategories/++add++AnalysisCategory",
            fields,
            cat
        )
        uid = lookup_uid("analysiscategory", "title", cat)
        cat_uids[cat] = uid

# ══ 4. SAMPLE TYPES ══════════════════════════════════════════
print(f"\n{INFO} [4/8] Checking Sample Types...")
sample_types_def = [
    {"title": "Serum",          "prefix": "SRM", "volume": "2 mL"},
    {"title": "Whole Blood",    "prefix": "WB",  "volume": "3 mL"},
    {"title": "Urine",          "prefix": "URN", "volume": "10 mL"},
    {"title": "Water Sample",   "prefix": "WTR", "volume": "500 mL"},
    {"title": "Soil Sample",    "prefix": "SOL", "volume": "100 g"},
    {"title": "Food Sample",    "prefix": "FD",  "volume": "50 g"},
    {"title": "Pharmaceutical", "prefix": "PHR", "volume": "10 tablets"},
    {"title": "Swab",           "prefix": "SWB", "volume": "1 swab"},
]
st_uids = {}
for st in sample_types_def:
    uid = lookup_uid("sampletype", "title", st["title"])
    if uid:
        st_uids[st["title"]] = uid
        print(f"  {INFO} EXISTS : {st['title']}")
    else:
        fields = {
            "form.widgets.title": st["title"],
            "form.widgets.prefix": st["prefix"],
            "form.widgets.min_volume": st["volume"],
            "form.widgets.retention_period.days:record:int": "30",
            "form.widgets.retention_period.hours:record:int": "0",
            "form.widgets.retention_period.minutes:record:int": "0",
            "form.widgets.retention_period.seconds:record:int": "0"
        }
        create_dexterity_object(
            f"{BASE}/setup/sampletypes/++add++SampleType",
            fields,
            st["title"]
        )
        uid = lookup_uid("sampletype", "title", st["title"])
        st_uids[st["title"]] = uid

# ══ 5. ANALYSIS SERVICES ═════════════════════════════════════
print(f"\n{INFO} [5/8] Checking Analysis Services...")
services_def = [
    # Clinical Chemistry
    {"title": "Glucose",           "Keyword": "GLU",  "Unit": "mg/dL",        "Price": "150", "cat": "Clinical Chemistry"},
    {"title": "Haemoglobin",       "Keyword": "HGB",  "Unit": "g/dL",         "Price": "120", "cat": "Clinical Chemistry"},
    {"title": "Creatinine",        "Keyword": "CRTN", "Unit": "mg/dL",        "Price": "180", "cat": "Clinical Chemistry"},
    {"title": "Total Cholesterol", "Keyword": "CHOL", "Unit": "mg/dL",        "Price": "200", "cat": "Clinical Chemistry"},
    {"title": "ALT (SGPT)",        "Keyword": "ALT",  "Unit": "U/L",          "Price": "220", "cat": "Clinical Chemistry"},
    {"title": "AST (SGOT)",        "Keyword": "AST",  "Unit": "U/L",          "Price": "220", "cat": "Clinical Chemistry"},
    {"title": "Total Bilirubin",   "Keyword": "TBIL", "Unit": "mg/dL",        "Price": "190", "cat": "Clinical Chemistry"},
    {"title": "Urea (BUN)",        "Keyword": "UREA", "Unit": "mg/dL",        "Price": "160", "cat": "Clinical Chemistry"},
    # Haematology
    {"title": "WBC Count",         "Keyword": "WBC",  "Unit": "10³/µL",       "Price": "250", "cat": "Haematology"},
    {"title": "Platelet Count",    "Keyword": "PLT",  "Unit": "10³/µL",       "Price": "250", "cat": "Haematology"},
    {"title": "RBC Count",         "Keyword": "RBC",  "Unit": "10⁶/µL",       "Price": "200", "cat": "Haematology"},
    # Microbiology
    {"title": "Total Plate Count", "Keyword": "TPC",  "Unit": "CFU/mL",       "Price": "350", "cat": "Microbiology"},
    {"title": "E. coli Detection", "Keyword": "ECOLI","Unit": "Absent/Present","Price": "400", "cat": "Microbiology"},
    {"title": "Salmonella Screen", "Keyword": "SAL",  "Unit": "Absent/Present","Price": "500", "cat": "Microbiology"},
    {"title": "Coliform Count",    "Keyword": "COLI", "Unit": "MPN/100mL",    "Price": "380", "cat": "Microbiology"},
    # Heavy Metals
    {"title": "Lead (Pb)",         "Keyword": "PB",   "Unit": "mg/kg",        "Price": "600", "cat": "Heavy Metals"},
    {"title": "Arsenic (As)",      "Keyword": "AS",   "Unit": "mg/kg",        "Price": "650", "cat": "Heavy Metals"},
    {"title": "Mercury (Hg)",      "Keyword": "HG",   "Unit": "mg/kg",        "Price": "750", "cat": "Heavy Metals"},
    {"title": "Cadmium (Cd)",      "Keyword": "CD",   "Unit": "mg/kg",        "Price": "620", "cat": "Heavy Metals"},
    # Water Quality
    {"title": "pH",                "Keyword": "PH",   "Unit": "pH units",     "Price": "80",  "cat": "Water Quality"},
    {"title": "Turbidity",         "Keyword": "TURB", "Unit": "NTU",          "Price": "100", "cat": "Water Quality"},
    {"title": "Dissolved Oxygen",  "Keyword": "DO",   "Unit": "mg/L",         "Price": "120", "cat": "Water Quality"},
    {"title": "BOD",               "Keyword": "BOD",  "Unit": "mg/L",         "Price": "250", "cat": "Water Quality"},
    {"title": "COD",               "Keyword": "COD",  "Unit": "mg/L",         "Price": "300", "cat": "Water Quality"},
    {"title": "Total Hardness",    "Keyword": "HARD", "Unit": "mg/L as CaCO3","Price": "150", "cat": "Water Quality"},
    # Agricultural
    {"title": "Soil pH",           "Keyword": "SPHH", "Unit": "pH",           "Price": "90",  "cat": "Agricultural"},
    {"title": "Nitrogen (N)",      "Keyword": "NITR", "Unit": "%",            "Price": "200", "cat": "Agricultural"},
    {"title": "Phosphorus (P)",    "Keyword": "PHOS", "Unit": "mg/kg",        "Price": "180", "cat": "Agricultural"},
    {"title": "Pesticide Residue", "Keyword": "PEST", "Unit": "ppm",           "Price": "800", "cat": "Agricultural"},
    # Pharmaceuticals
    {"title": "Assay (HPLC)",      "Keyword": "ASSAY","Unit": "%",            "Price": "1200","cat": "Pharmaceuticals"},
    {"title": "Dissolution Test",  "Keyword": "DISS", "Unit": "%",            "Price": "1500","cat": "Pharmaceuticals"},
    {"title": "Related Substances","Keyword": "RS",   "Unit": "%",            "Price": "1800","cat": "Pharmaceuticals"},
]
svc_uids = {}
for sv in services_def:
    uid = lookup_uid("analysisservice", "getKeyword", sv["Keyword"])
    if uid:
        svc_uids[sv["Keyword"]] = uid
        print(f"  {INFO} EXISTS : {sv['title']} ({sv['Keyword']})")
    else:
        fields = {
            "title": sv["title"],
            "Keyword": sv["Keyword"],
            "Unit": sv["Unit"],
            "Price": sv["Price"],
            "Category": cat_uids[sv["cat"]]
        }
        create_archetype_object(
            f"{BASE}/bika_setup/bika_analysisservices",
            "AnalysisService",
            fields,
            f"{sv['title']} ({sv['Keyword']})"
        )
        uid = lookup_uid("analysisservice", "getKeyword", sv["Keyword"])
        svc_uids[sv["Keyword"]] = uid

# ══ 6. CLIENTS & CLIENT CONTACTS ═════════════════════════════
print(f"\n{INFO} [6/8] Checking Clients & Contacts...")
clients_def = [
    {
        "title": "BIS National Testing Laboratory",
        "ClientID": "BIS-NTL-001",
        "Phone": "011-23232400",
        "EmailAddress": "lab@bis.gov.in",
        "city": "New Delhi", "zip": "110002",
        "contact_fn": "Rajesh", "contact_sn": "Sharma", "contact_email": "rajesh.sharma@bis.gov.in"
    },
    {
        "title": "Punjab Agri Testing Center",
        "ClientID": "PATC-002",
        "Phone": "0172-2214682",
        "EmailAddress": "agritest@punjab.gov.in",
        "city": "Mohali", "zip": "160068",
        "contact_fn": "Priya", "contact_sn": "Nair", "contact_email": "priya.nair@punjab.gov.in"
    },
    {
        "title": "MaxLab Diagnostics Pvt Ltd",
        "ClientID": "MAXL-003",
        "Phone": "080-45678900",
        "EmailAddress": "info@maxlabdiag.com",
        "city": "Bengaluru", "zip": "560001",
        "contact_fn": "Amit", "contact_sn": "Gupta", "contact_email": "amit.gupta@maxlab.com"
    },
    {
        "title": "DRDO Materials Research Lab",
        "ClientID": "DRDO-004",
        "Phone": "011-23011347",
        "EmailAddress": "mrl@drdo.gov.in",
        "city": "New Delhi", "zip": "110011",
        "contact_fn": "Sunita", "contact_sn": "Reddy", "contact_email": "sunita.reddy@drdo.gov.in"
    },
    {
        "title": "Cipla Quality Control Lab",
        "ClientID": "CIPL-005",
        "Phone": "022-20972020",
        "EmailAddress": "qc@cipla.com",
        "city": "Mumbai", "zip": "400013",
        "contact_fn": "Vikram", "contact_sn": "Mehta", "contact_email": "vikram.mehta@cipla.com"
    },
]

client_uids = {}
contact_uids = {}

for cl in clients_def:
    cl_uid = lookup_uid("client", "title", cl["title"])
    if cl_uid:
        client_uids[cl["title"]] = cl_uid
        print(f"  {INFO} EXISTS : {cl['title']}")
    else:
        fields = {
            "Name": cl["title"],
            "ClientID": cl["ClientID"],
            "Phone": cl["Phone"],
            "EmailAddress": cl["EmailAddress"],
            "PhysicalAddress.city": cl["city"],
            "PhysicalAddress.zip": cl["zip"]
        }
        create_archetype_object(
            f"{BASE}/clients",
            "Client",
            fields,
            cl["title"]
        )
        cl_uid = lookup_uid("client", "title", cl["title"])
        client_uids[cl["title"]] = cl_uid

    # Client Contact
    ct_uid = lookup_client_contact_uid(cl_uid, cl["contact_fn"])
    if ct_uid:
        contact_uids[cl["title"]] = ct_uid
        print(f"  {INFO} EXISTS : Contact {cl['contact_fn']} {cl['contact_sn']}")
    else:
        # Find client URL path
        items = api_get_all("client")
        client_id_path = ""
        for item in items:
            if item.get("uid") == cl_uid:
                client_id_path = item.get("id")
                break
        if client_id_path:
            fields = {
                "form.widgets.firstname": cl["contact_fn"],
                "form.widgets.surname": cl["contact_sn"],
                "form.widgets.email_address": cl["contact_email"],
                "form.widgets.business_phone": cl["Phone"]
            }
            create_dexterity_object(
                f"{BASE}/clients/{client_id_path}/++add++Contact",
                fields,
                f"Contact {cl['contact_fn']} {cl['contact_sn']}"
            )
            ct_uid = lookup_client_contact_uid(cl_uid, cl["contact_fn"])
            contact_uids[cl["title"]] = ct_uid

# ══ 7. SAMPLES (Analysis Requests) ═══════════════════════════
print(f"\n{INFO} [7/8] Registering Samples (Analysis Requests)...")

# Current localized time to avoid "future sampling date" validation errors
now = datetime.utcnow() - timedelta(hours=2)

samples_def = [
    {
        "client": "BIS National Testing Laboratory",
        "SampleType": "Serum",
        "ClientSampleID": "BIS-SMP-001",
        "minutes_offset": 60,
        "services": ["GLU", "HGB", "CRTN", "CHOL", "ALT", "AST"],
        "Priority": "high"
    },
    {
        "client": "BIS National Testing Laboratory",
        "SampleType": "Water Sample",
        "ClientSampleID": "BIS-SMP-002",
        "minutes_offset": 120,
        "services": ["PH", "TURB", "DO", "BOD", "COLI"],
        "Priority": "normal"
    },
    {
        "client": "BIS National Testing Laboratory",
        "SampleType": "Food Sample",
        "ClientSampleID": "BIS-SMP-003",
        "minutes_offset": 180,
        "services": ["PB", "AS", "HG", "TPC", "ECOLI", "SAL"],
        "Priority": "high"
    },
    {
        "client": "Punjab Agri Testing Center",
        "SampleType": "Soil Sample",
        "ClientSampleID": "PATC-SMP-001",
        "minutes_offset": 240,
        "services": ["SPHH", "NITR", "PHOS", "PEST"],
        "Priority": "normal"
    },
    {
        "client": "Punjab Agri Testing Center",
        "SampleType": "Water Sample",
        "ClientSampleID": "PATC-SMP-002",
        "minutes_offset": 300,
        "services": ["PH", "TURB", "DO", "BOD", "ECOLI"],
        "Priority": "high"
    },
    {
        "client": "MaxLab Diagnostics Pvt Ltd",
        "SampleType": "Whole Blood",
        "ClientSampleID": "MAXL-SMP-001",
        "minutes_offset": 360,
        "services": ["HGB", "GLU", "CRTN", "WBC", "PLT", "RBC"],
        "Priority": "normal"
    },
    {
        "client": "MaxLab Diagnostics Pvt Ltd",
        "SampleType": "Serum",
        "ClientSampleID": "MAXL-SMP-002",
        "minutes_offset": 420,
        "services": ["GLU", "CHOL", "ALT", "AST", "TBIL", "UREA"],
        "Priority": "normal"
    },
    {
        "client": "MaxLab Diagnostics Pvt Ltd",
        "SampleType": "Swab",
        "ClientSampleID": "MAXL-SMP-003",
        "minutes_offset": 480,
        "services": ["TPC", "ECOLI", "SAL"],
        "Priority": "high"
    },
    {
        "client": "DRDO Materials Research Lab",
        "SampleType": "Food Sample",
        "ClientSampleID": "DRDO-SMP-001",
        "minutes_offset": 540,
        "services": ["PB", "AS", "HG", "CD", "PEST"],
        "Priority": "high"
    },
    {
        "client": "DRDO Materials Research Lab",
        "SampleType": "Water Sample",
        "ClientSampleID": "DRDO-SMP-002",
        "minutes_offset": 600,
        "services": ["PH", "TURB", "DO", "BOD", "COD", "HARD"],
        "Priority": "normal"
    },
]

created_ar_uids = []

for smp in samples_def:
    # Check if Sample already exists
    ar_uid = lookup_uid("analysisrequest", "getClientSampleID", smp["ClientSampleID"])
    if ar_uid:
        print(f"  {INFO} EXISTS : {smp['ClientSampleID']}")
        created_ar_uids.append(ar_uid)
        continue

    cl_uid = client_uids.get(smp["client"])
    ct_uid = contact_uids.get(smp["client"])
    st_uid = st_uids.get(smp["SampleType"])
    svc_list = [svc_uids[kw] for kw in smp["services"] if kw in svc_uids]

    if not cl_uid or not ct_uid or not st_uid:
        print(f"  {FAIL} FAILED : Missing client/contact/sampletype UID for {smp['ClientSampleID']}")
        continue

    sample_time = now - timedelta(minutes=smp["minutes_offset"])
    sample_time_str = sample_time.strftime("%Y-%m-%d %H:%M")

    csrf = get_csrf()
    payload = {
        "_authenticator": csrf,
        "ar_count": "1",
        "Client-0": cl_uid,
        "Contact-0": ct_uid,
        "SampleType-0": st_uid,
        "DateSampled-0": sample_time_str,
        "ClientSampleID-0": smp["ClientSampleID"],
        "Priority-0": smp["Priority"]
    }
    # Add multiple analysis services
    data_list = []
    for k, v in payload.items():
        data_list.append((k, v))
    for svc in svc_list:
        data_list.append(("Analyses-0:list", svc))

    r = s.post(
        f"{BASE}/ajax_ar_add/submit",
        data=data_list,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if r.ok:
        res = r.json()
        if "success" in res:
            ar_uid = lookup_uid("analysisrequest", "getClientSampleID", smp["ClientSampleID"])
            if ar_uid:
                created_ar_uids.append(ar_uid)
                print(f"  {OK} REGISTERED: {smp['ClientSampleID']} ({smp['SampleType']})")
            else:
                print(f"  {FAIL} FAILED : {smp['ClientSampleID']} (Created but UID lookup failed)")
        else:
            print(f"  {FAIL} FAILED : {smp['ClientSampleID']} => {res.get('errors')}")
    else:
        print(f"  {FAIL} FAILED : {smp['ClientSampleID']} (HTTP {r.status_code})")

# ══ 8. RECEIVE SAMPLES (Workflow Transition) ═════════════════
print(f"\n{INFO} [8/8] Processing workflow transitions (Receive Samples)...")
received_count = 0

# Fetch all current ARs to verify workflow transition state
ars = api_get_all("analysisrequest")
for ar in ars:
    uid = ar.get("uid")
    if uid in created_ar_uids:
        state = ar.get("review_state", "")
        ar_id = ar.get("id", "")
        ar_url = ar.get("url") or ar.get("@id")
        if state == "sample_due":
            # Keep 3 specific samples as reception pending
            client_sample_id = ar.get("getClientSampleID", "")
            if client_sample_id in ["DRDO-SMP-001", "DRDO-SMP-002", "MAXL-SMP-003"]:
                print(f"  {INFO} KEEPEING RECEPTION PENDING: {client_sample_id}")
                continue
            # Transition to received
            csrf = get_csrf()
            r = s.get(
                f"{ar_url}/content_status_modify",
                params={"workflow_action": "receive", "_authenticator": csrf}
            )
            if r.ok:
                received_count += 1
                print(f"  {OK} RECEIVED: {ar_id}")
            else:
                print(f"  {FAIL} FAILED to receive: {ar_id}")
        else:
            print(f"  {INFO} STATE '{state}': {ar_id}")

# ══ SUMMARY ══════════════════════════════════════════════════
print("\n" + "═"*66)
print(f"  {BOLD}SEEDING PROCESS COMPLETED SUCCESSFULLY{RESET}")
print("═"*66)
print(f"  Lab Manager         : Yes")
print(f"  Lab Departments     : 1")
print(f"  Analysis Categories : {len(categories)}")
print(f"  Sample Types        : {len(sample_types_def)}")
print(f"  Analysis Services   : {len(services_def)}")
print(f"  Clients             : {len(clients_def)}")
print(f"  Client Contacts     : {len(clients_def)}")
print(f"  Analysis Requests   : {len(created_ar_uids)}")
print(f"  ARs Received        : {received_count}")
print(f"\n  → Dashboard View: http://localhost:8080/senaite/senaite-dashboard")
print("═"*66 + "\n")
