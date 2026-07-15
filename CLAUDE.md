CA State Bar Scraping Workflow
1. Step 1 — Look up each attorney on the CA State Bar
1.	Use apify/cheerio-scraper in two sub-steps:
2.	2a. Search page: https://apps.calbar.ca.gov/attorney/LicenseeSearch/QuickSearch?freetext=FIRST+LAST&btnSearch=Search
3.	In the page function, use a seed URL approach: pass attorney names in customData.attorneys, generate search URLs in the seed handler, then follow a[href*="Licensee/Detail"] links to profile pages. Pass avvoName via userData to connect results back.
4.	2b. Profile page: Extract from $('body').text():
5.	Bar number: from URL (url.split('/').pop())
6.	Phone: regex Phone[^\d]*(\d[\d\s\-\(\)\.]+)
7.	Raw email: regex Email:\s*([^\r\n]*@[^\r\n]*)
8.	The CA State Bar profile pages ARE server-side rendered — Cheerio works fine. The email is an obfuscated string of ~20 fake addresses with the real one mixed in. Parse it with the segment algorithm below.
9.	Email parsing algorithm (from project instructions):
pythonTLDS = ['com','net','org','edu','gov','mil','us','io','ca','law','legal','biz','me','pro','co','uk','attorney']
def extract_emails(text):
    segs = text.split('@')
    emails = []
    for i in range(len(segs)-1):
        local = segs[i]
        for tld in sorted(TLDS, key=len, reverse=True):
            idx = segs[i].rfind('.'+tld)
            if idx >= 0: local = segs[i][idx+len(tld)+1:]; break
        domain = segs[i+1]
        for tld in sorted(TLDS, key=len, reverse=True):
            idx = segs[i+1].find('.'+tld)
            if idx >= 0: domain = segs[i+1][:idx+len(tld)+1]; break
        if local and domain and '.' in domain and re.match(r'^[a-zA-Z0-9._%+\-]+$', local):
            emails.append(local+'@'+domain)
    return emails
def score_email(email):
    score = 0
    domain = email.split('@')[1].lower()
    local = email.split('@')[0].lower()
    if any(f in domain for f in ['gmail','yahoo','hotmail','outlook','aol']): score += 8
    if any(w in domain for w in ['law','llp','firm','legal','atty','esq']): score += 5
    if '.' in local: score += 4
    if len(domain.split('.')[0]) > 10: score += 2
    if re.findall(r'[bcdfghjklmnpqrstvwxyz]{4,}', local): score -= 3
    return score
10.	Name matching (to avoid picking the wrong profile when a search returns multiple results):
11.	Strip suffixes (Jr., Sr., II, III), remove (aka ...) clauses, normalize spaces/commas
12.	Check that last names overlap (handles hyphenated married names like Welsh → Welsh-Levin)
13.	Score: 3 = exact, 2 = last name + one other word, 1 = last name only, 0 = reject
14.	For missing attorneys: Re-run with first+last only (strip middle names) — catches ~80% of the unmatched ones.
15.	Run in 8 parallel batches of ~205 attorneys each using the customData.attorneys seed approach (4–5KB per call instead of 277KB for full URL arrays).
2. Step 2 — Re-scrape CA Bar profiles for firm name and city
16.	Re-run apify/cheerio-scraper on all bar profile URLs (constructed as https://apps.calbar.ca.gov/attorney/Licensee/Detail/{barNum}). Use the seed+customData approach passing bar numbers.
17.	Page function extracts from $('body').text():
18.	Address line: Address:\s*([^\r\n]{5,200})
19.	Firm name: first comma-delimited segment of address if it doesn't start with a digit
20.	City: regex ,[^,]*([A-Za-z][A-Za-z\s]+),\s*CA\s*\d
21.	Note: yearsLicensed won't parse from the CA Bar (they don't use that format) — estimate from bar number instead
22.	Bar number → approximate years licensed:
23.	< 50k: 52+ yrs | 50–100k: 40–45 | 100–150k: 36–40 | 150–200k: 30–33 | 200–250k: 24–27 | 250–300k: 19–21 | 300k+: < 18
3. Step3  — Generate personalization sentences
Use firm name + bar number (years proxy) + city to generate a sentence tying the attorney to the case. Branch on inferred practice area:
General/unknown: reference years of experience and the case's civil rights + defamation + institutional accountability elements
Do NOT use em dashes.
Do NOT use quotation marks inside the sentences.
Final CSV columns:
Attorney Name, Page, Bar Number, Phone, Email, Firm, City, Personalization
