#!/usr/bin/env python3
import requests
import re
from datetime import datetime, timedelta

BASE = "http://localhost:8080/senaite"
AUTH = ("admin", "admin")

s = requests.Session()
s.auth = AUTH

def get_csrf():
    r = s.get(f"{BASE}/@@authenticator")
    tokens = re.findall(r'value="([^"]+)"', r.text, re.I)
    return tokens[0] if tokens else ""

def api_get_all(endpoint):
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
    items = api_get_all(endpoint)
    for item in items:
        val = item.get(match_key, "")
        if str(val).strip().lower() == str(match_val).strip().lower():
            return item.get("uid", "")
    return ""

def lookup_client_contact_uid(client_uid, contact_name):
    items = api_get_all("contact")
    for item in items:
        fullname = item.get("title", "") or item.get("fullname", "")
        if contact_name.lower() in fullname.lower():
            return item.get("uid", "")
    return ""

print("Registering extra samples to remain in 'sample_due' state...")

client_uid = lookup_uid("client", "title", "BIS National Testing Laboratory")
contact_uid = lookup_client_contact_uid(client_uid, "Rajesh")
sample_type_uid = lookup_uid("sampletype", "title", "Serum")
glucose_svc_uid = lookup_uid("analysisservice", "getKeyword", "GLU")
hgb_svc_uid = lookup_uid("analysisservice", "getKeyword", "HGB")

now = datetime.utcnow() - timedelta(hours=2)

extra_samples = [
    {"ClientSampleID": "EXTRA-SMP-001", "Priority": "normal", "minutes_offset": 10},
    {"ClientSampleID": "EXTRA-SMP-002", "Priority": "high", "minutes_offset": 20},
    {"ClientSampleID": "EXTRA-SMP-003", "Priority": "normal", "minutes_offset": 30},
    {"ClientSampleID": "EXTRA-SMP-004", "Priority": "high", "minutes_offset": 40},
    {"ClientSampleID": "EXTRA-SMP-005", "Priority": "normal", "minutes_offset": 50},
]

for smp in extra_samples:
    ar_uid = lookup_uid("analysisrequest", "getClientSampleID", smp["ClientSampleID"])
    if ar_uid:
        print(f"Sample {smp['ClientSampleID']} already exists.")
        continue

    sample_time = now - timedelta(minutes=smp["minutes_offset"])
    sample_time_str = sample_time.strftime("%Y-%m-%d %H:%M")

    csrf = get_csrf()
    payload = [
        ("_authenticator", csrf),
        ("ar_count", "1"),
        ("Client-0", client_uid),
        ("Contact-0", contact_uid),
        ("SampleType-0", sample_type_uid),
        ("DateSampled-0", sample_time_str),
        ("ClientSampleID-0", smp["ClientSampleID"]),
        ("Priority-0", smp["Priority"]),
        ("Analyses-0:list", glucose_svc_uid),
        ("Analyses-0:list", hgb_svc_uid),
    ]

    r = s.post(
        f"{BASE}/ajax_ar_add/submit",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if r.ok and "success" in r.json():
        print(f"Successfully registered {smp['ClientSampleID']} (Reception Pending)")
    else:
        print(f"Failed to register {smp['ClientSampleID']}")
