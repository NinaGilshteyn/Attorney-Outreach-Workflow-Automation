#!/usr/bin/env python3
"""
Step 2 + Step 3: Merge bar profile data with Step 1 CSV, fix city extraction,
generate personalization sentences, output final CSV.
"""

import json, re, csv, glob, os

BASE = '/sessions/peaceful-gracious-darwin/mnt/attorney_scraper'

# ── 1. Load Step 2 data (firm + address from all 4 batches) ──────────────────
step2_map = {}  # barNum -> {firm, address}
for fname in ['step2_s2b0.json','step2_s2b1.json','step2_s2b2.json','step2_s2b3.json']:
    path = os.path.join(BASE, fname)
    if not os.path.exists(path):
        print(f"WARNING: missing {fname}")
        continue
    items = json.load(open(path))
    for it in items:
        bn = str(it.get('barNum','') or '')
        if bn:
            step2_map[bn] = {
                'firm': it.get('firm','') or '',
                'address': it.get('address','') or ''
            }
print(f"Step 2 map: {len(step2_map)} bar numbers")

# ── 2. Fixed city extraction from raw address ────────────────────────────────
def extract_city(address):
    """Extract city from 'Firm, Street, City, CA ZIP' pattern."""
    if not address:
        return ''
    # Match last ", CityName, CA ZIPCODE" before end
    m = re.search(r',\s*([A-Za-z][A-Za-z\s\.]+?),\s*CA\s+[\d\-]+', address)
    if m:
        city = m.group(1).strip()
        # Skip if it looks like a suite/apt designation
        if re.match(r'^(Ste|Suite|Apt|Fl|Fl\s|Floor|Pmb|Unit|#)', city, re.I):
            # Try again with a broader match — look for city pattern further back
            segs = re.findall(r',\s*([A-Za-z][A-Za-z\s\.]+?),\s*CA\s+[\d\-]+', address)
            for s in reversed(segs):
                c = s.strip()
                if not re.match(r'^(Ste|Suite|Apt|Fl|Floor|Pmb|Unit|#|PO\s)', c, re.I):
                    return c
        return city
    return ''

# ── 3. Bar number → years licensed ──────────────────────────────────────────
def years_licensed(bar_num_str):
    try:
        bn = int(bar_num_str)
    except:
        return None
    if bn < 50000:    return '52+'
    if bn < 100000:   return '40-45'
    if bn < 150000:   return '36-40'
    if bn < 200000:   return '30-33'
    if bn < 250000:   return '24-27'
    if bn < 300000:   return '19-21'
    return '<18'

# ── 4. Personalization sentence generator ───────────────────────────────────
def make_personalization(name, bar_num, firm, city):
    yrs = years_licensed(bar_num)

    has_firm = bool(firm and not firm.startswith('PO Box') and not firm.startswith('Route '))
    has_city = bool(city and city not in ('', 'NA'))
    has_yrs  = bool(yrs)

    tail = ("aligns closely with the civil rights, defamation, and institutional "
            "accountability claims at the heart of this case against the UC Regents, "
            "and I would be grateful for the opportunity to discuss whether you might "
            "be able to help.")

    if has_firm and has_city and has_yrs:
        return (f"Your work at {firm}, based in {city}, with {yrs} years of California "
                f"bar experience {tail}")
    elif has_firm and has_city:
        return (f"Your work at {firm}, based in {city}, {tail}")
    elif has_firm and has_yrs:
        return (f"Your work at {firm}, with {yrs} years of California bar experience, {tail}")
    elif has_city and has_yrs:
        return (f"Your practice based in {city}, with {yrs} years of California bar experience, {tail}")
    elif has_firm:
        return (f"Your work at {firm} {tail}")
    elif has_city:
        return (f"Your practice based in {city} {tail}")
    elif has_yrs:
        return (f"With {yrs} years of experience as a California attorney, your background {tail}")
    else:
        return ("I believe your background in civil rights and institutional accountability "
                "litigation makes you well-suited to evaluate this case against the UC Regents, "
                "and I would welcome the chance to speak with you about it.")

# ── 5. Load Step 1 CSV and build final output ────────────────────────────────
step1_path = os.path.join(BASE, 'attorneys_step1.csv')
rows = []
with open(step1_path, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

print(f"Step 1 rows: {len(rows)}")

out_rows = []
matched_firm = 0
matched_city = 0

for row in rows:
    bar_num = row.get('Bar Number','').strip()
    name    = row.get('Attorney Name','').strip()
    phone   = row.get('Phone','').strip()
    email   = row.get('Email','').strip()
    profile = row.get('Profile URL','').strip()

    # Page: extract page number from profile URL if needed
    # Profile URL format: https://apps.calbar.ca.gov/attorney/Licensee/Detail/BARNUM
    # We don't have a "Page" column in step1 — leaving blank
    page = ''

    firm = ''
    city = ''
    address = ''

    if bar_num in step2_map:
        d = step2_map[bar_num]
        firm = d.get('firm','') or ''
        address = d.get('address','') or ''
        city = extract_city(address)
        if firm: matched_firm += 1
        if city: matched_city += 1

    personalization = make_personalization(name, bar_num, firm, city)

    out_rows.append({
        'Attorney Name': name,
        'Page': page,
        'Bar Number': bar_num,
        'Phone': phone,
        'Email': email,
        'Firm': firm,
        'City': city,
        'Personalization': personalization,
    })

print(f"Matched firm: {matched_firm}/{len(rows)}")
print(f"Matched city: {matched_city}/{len(rows)}")

# ── 6. Write final CSV ───────────────────────────────────────────────────────
out_path = os.path.join(BASE, 'attorneys_final.csv')
fieldnames = ['Attorney Name','Page','Bar Number','Phone','Email','Firm','City','Personalization']
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(out_rows)

print(f"\nWrote {len(out_rows)} rows to {out_path}")

# ── 7. Quick sample ──────────────────────────────────────────────────────────
print("\n=== SAMPLE (first 5 with firm+city) ===")
shown = 0
for r in out_rows:
    if r['Firm'] and r['City'] and shown < 5:
        print(f"  {r['Attorney Name']}")
        print(f"  Bar: {r['Bar Number']} | Firm: {r['Firm']} | City: {r['City']}")
        print(f"  Personalization: {r['Personalization'][:120]}...")
        print()
        shown += 1
