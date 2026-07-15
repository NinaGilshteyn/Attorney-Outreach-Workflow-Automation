#!/usr/bin/env python3
"""
Attorney scraper processor — Step 1 output → matched CSV.
Reads all scraped_b*.json files, runs name-matching + email extraction,
outputs attorneys_step1.csv with: Attorney Name, Page, Bar Number, Phone, Email.
"""
import json, re, os, csv, glob, sys

# ── TLD list and email helpers ───────────────────────────────────────────────
TLDS = ['attorney','legal','law','com','net','org','edu','gov','mil','us','io',
        'ca','biz','me','pro','co','uk']

def extract_emails(text):
    segs = text.split('@')
    emails = []
    for i in range(len(segs) - 1):
        local = segs[i]
        for tld in sorted(TLDS, key=len, reverse=True):
            idx = segs[i].rfind('.' + tld)
            if idx >= 0:
                local = segs[i][idx + len(tld) + 1:]
                break
        domain = segs[i + 1]
        for tld in sorted(TLDS, key=len, reverse=True):
            idx = segs[i + 1].find('.' + tld)
            if idx >= 0:
                domain = segs[i + 1][:idx + len(tld) + 1]
                break
        if local and domain and '.' in domain and re.match(r'^[a-zA-Z0-9._%+\-]+$', local):
            emails.append(local + '@' + domain)
    return emails

def score_email(email):
    score = 0
    domain = email.split('@')[1].lower()
    local  = email.split('@')[0].lower()
    if any(f in domain for f in ['gmail','yahoo','hotmail','outlook','aol']): score += 8
    if any(w in domain for w in ['law','llp','firm','legal','atty','esq']):   score += 5
    if '.' in local:                                                           score += 4
    if len(domain.split('.')[0]) > 10:                                         score += 2
    if re.findall(r'[bcdfghjklmnpqrstvwxyz]{4,}', local):                    score -= 3
    return score

def best_email(raw):
    if not raw or not raw.strip():
        return ''
    candidates = extract_emails(raw.strip())
    if not candidates:
        return ''
    return max(candidates, key=score_email)

# ── Name matching ────────────────────────────────────────────────────────────
SUFFIXES = re.compile(r'\b(jr|sr|ii|iii|iv|esq|esquire|phd|md)\.?$', re.I)
AKA_RE   = re.compile(r'\s*\(aka[^)]*\)', re.I)

def normalize(name):
    name = AKA_RE.sub('', name)
    name = SUFFIXES.sub('', name).strip().lower()
    name = re.sub(r'[^a-z\s-]', '', name)
    return name.split()

def name_score(searched_words, scraped_display):
    """Return 0–3 match score."""
    sw = normalize(searched_words)
    dw = normalize(scraped_display)
    if not sw or not dw:
        return 0
    # last-name overlap check (handles hyphenated names)
    s_last = sw[-1]
    d_last = dw[-1]
    last_ok = s_last in d_last or d_last in s_last
    if not last_ok:
        return 0
    if set(sw) == set(dw):
        return 3
    common = set(sw) & set(dw)
    if s_last in common and len(common) >= 2:
        return 2
    return 1

# ── Phone cleanup ────────────────────────────────────────────────────────────
def clean_phone(p):
    if not p or p.strip() in ('600', '000000', '650', ''):
        return ''
    # strip non-digits except + - ( ) .
    p = p.strip()
    # if looks like a real US number (10+ digits), keep
    digits = re.sub(r'\D', '', p)
    if len(digits) < 10:
        return ''
    return p

# ── Load all scraped JSON files ──────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
pattern = os.path.join(HERE, 'scraped_b*.json')
files = sorted(glob.glob(pattern))

if not files:
    print("ERROR: No scraped_b*.json files found. Run the Apify fetcher first.", file=sys.stderr)
    sys.exit(1)

print(f"Loading {len(files)} batch files …")
all_items = []
for fp in files:
    with open(fp) as f:
        data = json.load(f)
    all_items.extend(data)
print(f"  Total raw items: {len(all_items)}")

# ── Load attorneys_clean.json ────────────────────────────────────────────────
clean_path = os.path.join(HERE, 'outputs', 'attorneys_clean.json')
if not os.path.exists(clean_path):
    # try alternate location
    clean_path = os.path.join(os.path.dirname(HERE), 'outputs', 'attorneys_clean.json')
if not os.path.exists(clean_path):
    print("WARNING: attorneys_clean.json not found. Will use 'display' names from scraped data.", file=sys.stderr)
    attorneys_clean = None
else:
    with open(clean_path) as f:
        attorneys_clean = json.load(f)
    print(f"  Loaded {len(attorneys_clean)} cleaned attorney names")

# ── Group scraped items by searched attorney name ────────────────────────────
# key = normalised display name the scraper used
groups = {}
for item in all_items:
    key = item.get('searchedAttorney.display') or item.get('searchedAttorney.last', '')
    groups.setdefault(key, []).append(item)

print(f"  Unique search keys in scraped data: {len(groups)}")

# ── Match each searched name to best profile ─────────────────────────────────
results = []

for key, candidates in groups.items():
    # Pick best candidate by name score then by having email/phone
    best = None
    best_score = -1
    for c in candidates:
        sc = name_score(key, c.get('searchedAttorney.display', key))
        # bonus for having usable contact info
        bonus = 0
        if best_email(c.get('rawEmail', '')):
            bonus += 2
        if clean_phone(c.get('phone', '')):
            bonus += 1
        total = sc * 10 + bonus
        if total > best_score:
            best_score = total
            best = c

    if best is None or best_score < 10:  # require at least score 1
        results.append({
            'searched_name': key,
            'barNumber': '',
            'phone': '',
            'email': '',
            'profileUrl': '',
        })
        continue

    raw = best.get('rawEmail', '')
    results.append({
        'searched_name': key,
        'barNumber': best.get('barNumber', ''),
        'phone': clean_phone(best.get('phone', '')),
        'email': best_email(raw),
        'profileUrl': best.get('profileUrl', ''),
    })

# ── If we have attorneys_clean, merge in Page info ───────────────────────────
if attorneys_clean:
    # Build lookup: display → attorney entry
    display_to_clean = {a['display']: a for a in attorneys_clean}
    # Also by (last.lower, first.lower)
    name_to_clean = {(a['last'].lower(), a['first'].lower()): a for a in attorneys_clean}

    def find_clean(searched_name):
        if searched_name in display_to_clean:
            return display_to_clean[searched_name]
        parts = normalize(searched_name)
        if len(parts) >= 2:
            key2 = (parts[-1], parts[0])
            if key2 in name_to_clean:
                return name_to_clean[key2]
        return None

    enhanced = []
    for r in results:
        clean = find_clean(r['searched_name'])
        if clean:
            r['original'] = clean.get('original', r['searched_name'])
        else:
            r['original'] = r['searched_name']
        enhanced.append(r)
    results = enhanced

# ── Write step1 CSV ───────────────────────────────────────────────────────────
out_path = os.path.join(HERE, 'attorneys_step1.csv')
fieldnames = ['Attorney Name', 'Bar Number', 'Phone', 'Email', 'Profile URL']

with open(out_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for r in results:
        w.writerow({
            'Attorney Name': r.get('original', r['searched_name']),
            'Bar Number':    r['barNumber'],
            'Phone':         r['phone'],
            'Email':         r['email'],
            'Profile URL':   r['profileUrl'],
        })

print(f"\nWrote {len(results)} rows to {out_path}")
matched   = sum(1 for r in results if r['barNumber'])
emailed   = sum(1 for r in results if r['email'])
phoned    = sum(1 for r in results if r['phone'])
print(f"  Matched to profile: {matched}/{len(results)}")
print(f"  Have email:         {emailed}/{len(results)}")
print(f"  Have phone:         {phoned}/{len(results)}")
