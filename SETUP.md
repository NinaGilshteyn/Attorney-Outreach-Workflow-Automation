# Setup Guide: Attorney Scraper Workflow

**Goal**: Get this workflow running on your machine in 1–2 hours.

**⚠️ Critical Requirement**: You NEED an **Apify account** for web scraping. This cannot be skipped.

---

## Prerequisites Checklist

Before you start, make sure you have:

- [ ] **Apify account** (free tier available at https://apify.com)
- [ ] **Apify API key** (from account settings)
- [ ] **Python 3.8+** installed on your machine
- [ ] **Initial attorney list** (names from Perplexity/ChatGPT research)
- [ ] **Google Sheets account** (optional, for email outreach)
- [ ] **Gmail API enabled** (optional, for email automation)

---

## Step 0: Apify Setup (CRITICAL — Do This First!)

### Why Apify?

The CA State Bar website uses JavaScript rendering. Standard Python tools won't work:
- ❌ `urllib` / `requests` — No JavaScript execution
- ❌ `BeautifulSoup` alone — No JS support
- ✅ **Apify + cheerio-scraper** — Handles JS rendering + CSS extraction

### Create Apify Account & Get API Key

1. **Sign up**: https://apify.com (free tier)
2. **Get API key**:
   - Click your profile → **Settings**
   - Scroll to **API tokens**
   - Copy your API key (looks like: `apk_xxxxxx...`)
3. **Save it securely** (you'll need it multiple times)

### Understanding Apify Actors

- **Apify** = serverless compute platform
- **Actor** = pre-built web scraping tool
- **cheerio-scraper** = actor we'll use (CSS parsing + JS rendering)

### Test Your API Key

Open PowerShell/Terminal and test:
```powershell
$apiKey = "apk_YOUR_API_KEY_HERE"
$headers = @{"Authorization" = "Bearer $apiKey"}

Invoke-WebRequest `
  -Uri "https://api.apify.com/v2/users/me" `
  -Headers $headers
```

**Success**: Returns your Apify account info  
**Failure**: Check API key is correct

---

## Step 1: Prepare Attorney List

### Option A: Use Existing List

If you already have attorney names from research:
1. Create a CSV or JSON file with attorney names
2. Format: `FirstName LastName` (one per line)
3. **Save to**: `C:\Users\ninag\Claude\Projects\attorney_scraper\attorney_list.txt`

### Option B: Generate with Perplexity/ChatGPT

1. Ask: *"Generate a list of 200 civil rights attorneys in California with expertise in defamation, institutional accountability, and civil rights litigation. Format as FirstName LastName, one per line."*
2. Copy results into `attorney_list.txt`

### Example Format
```
John Smith
Mary Johnson
Robert Chen
Lisa Rodriguez
```

---

## Step 2: Run Apify Scraper (Steps 1 + 2)

This is the most time-consuming part (60–90 minutes for 160 attorneys).

### What Happens

1. **Step 1**: Search CA State Bar for each attorney → extract bar number, phone, email
2. **Step 2**: Re-scrape bar profiles → extract firm name, city, address

### Running the Scraper

Unfortunately, **Apify requires manual configuration** via their UI (no simple CLI for initial setup).

#### Option A: Use Apify Web Console (Easiest)

1. **Login** to https://apify.com/console
2. **Search for actor**: `apify/cheerio-scraper`
3. **Create new task**:
   - Name: `Attorney Bar Search Batch 0`
   - Actor: `cheerio-scraper`
   - Input config (see below)
   - **Run task**
4. **Download results** as JSON
5. **Repeat** for batches 1–7

#### Option B: Use Apify API (Programmatic)

If you're comfortable with APIs, use curl/PowerShell to submit batches:

```powershell
$apiKey = "apk_YOUR_KEY"
$actorId = "apify/cheerio-scraper"

$input = @{
    startUrls = @(
        @{url = "https://apps.calbar.ca.gov/attorney/LicenseeSearch/QuickSearch"}
    )
    customData = @{
        attorneys = @("John Smith", "Mary Johnson", "Robert Chen")
    }
    pageFunction = @"
async function pageFunction(context) {
  // See CLAUDE.md for full page function code
  // Extract bar number, phone, email, etc.
}
"@
} | ConvertTo-Json -Depth 10

$response = Invoke-WebRequest `
  -Uri "https://api.apify.com/v2/acts/$actorId/runs" `
  -Method POST `
  -Headers @{"Authorization" = "Bearer $apiKey"} `
  -Body $input `
  -ContentType "application/json"

$runId = ($response.Content | ConvertFrom-Json).data.id
Write-Host "Run ID: $runId"
```

### Expected Output

Each scraper run produces `scraped_b*.json`:
```json
[
  {
    "barNumber": "316492",
    "phone": "213-426-2000",
    "rawEmail": "naghazaryan@hurrell-llpXXXX...@fake1...@fake2...",
    "profileUrl": "https://apps.calbar.ca.gov/attorney/Licensee/Detail/316492"
  }
]
```

### Batch Size Recommendation

- **Attorneys per batch**: ~200 (keeps JSON < 5KB, prevents timeouts)
- **Total batches**: 160 attorneys ÷ 200 = 1 batch (or up to 8 for larger lists)
- **Time per batch**: 15–20 minutes
- **Cost**: Free tier supports 1–2 batches/day; upgrade to paid for more

---

## Step 3: Run Python Scripts

Once you have all `scraped_b*.json` files, process them locally.

### Environment Setup

1. **Install Python** (if not already):
   ```powershell
   python --version  # Should be 3.8+
   ```

2. **Navigate to project folder**:
   ```powershell
   cd "C:\Users\ninag\Claude\Projects\attorney_scraper"
   ```

3. **No external dependencies needed!**
   - Scripts use only Python standard library (json, re, csv, glob, os)

### Run Step 1: Process Scraped Data

```powershell
python process_scraped.py
```

**Expected output**:
```
Loading 8 batch files …
  Total raw items: 1600
  Unique search keys in scraped data: 160
Wrote 160 rows to attorneys_step1.csv
  Matched to profile: 155/160
  Have email: 150/160
  Have phone: 148/160
```

**Check**: Open `attorneys_step1.csv` and verify:
- Names look correct
- Bar numbers are populated
- Emails are not blank

### Run Step 2: Re-scrape for Firm & City

This step requires running the Apify scraper again (simpler this time):

1. **Build bar number URLs** from `attorneys_step1.csv`
2. **Submit to Apify** (same cheerio-scraper actor):
   ```
   https://apps.calbar.ca.gov/attorney/Licensee/Detail/{barNum}
   ```
3. **Download results** as `step2_s2b0.json`, `step2_s2b1.json`, etc.

### Run Step 3: Generate Final CSV with Personalization

```powershell
python build_final_csv.py
```

**Expected output**:
```
Step 2 map: 155 bar numbers
Matched firm: 140/160
Matched city: 142/160

Wrote 160 rows to attorneys_final.csv
```

**Check**: Open `attorneys_final.csv` and verify:
- Columns: Attorney Name, Bar Number, Phone, Email, Firm, City, Personalization
- Personalization sentences are unique per attorney
- Sample row:
  ```
  "Aghazaryan , Nzhdeh",316492,213-426-2000,naghazaryan@hurrell-llp.com,HURRELL-LLP,Los Angeles,"Your work at HURRELL-LLP, based in Los Angeles, with <18 years of California bar experience..."
  ```

---

## Step 4: Email Campaign (Optional)

### Import into Google Sheets

1. **Create new Google Sheet**
2. **File → Import → Upload**
3. Select `attorneys_final.csv`
4. **Columns**: A–H (Attorney Name through Personalization)
5. **Add column J**: "SENT" (header for tracking)

### Add Google Apps Script

1. **Extensions → Apps Script**
2. **Copy code from `send_campaign.gs`** into `Code.gs`
3. **Save project**
4. **Run** → Select `sendAishCaseCampaign` → **Execute**

**Expected behavior**:
- Emails send at ~1 per 5 seconds (rate limiting)
- Column J marks "SENT" for each attorney
- Check logs for errors: **View → Execution log**

---

## Verification Checklist

### After Step 1 (process_scraped.py)
- [ ] `attorneys_step1.csv` exists
- [ ] Contains 150+ attorneys with emails
- [ ] Sample rows have bar numbers, phones, emails

### After Step 2 (Apify re-scrape)
- [ ] `step2_s2b*.json` files exist
- [ ] Contain bar number, firm, address data

### After Step 3 (build_final_csv.py)
- [ ] `attorneys_final.csv` exists
- [ ] Contains 140+ attorneys with firm, city, personalization
- [ ] Personalization sentences vary by attorney

### After Step 4 (Email campaign)
- [ ] Sheet has "SENT" marks in column J
- [ ] Gmail inbox shows test email to yourself
- [ ] Execution log shows no errors

---

## Troubleshooting

### Issue: Apify API key not working

**Error**: `401 Unauthorized`

**Solution**:
1. Verify API key is correct (copy from Apify console again)
2. Check key has no leading/trailing spaces
3. Ensure account is active (not suspended)

### Issue: Apify scraper times out or returns empty results

**Error**: Scraper runs but `scraped_b*.json` is empty

**Solution**:
1. Check CA State Bar website is up (https://apps.calbar.ca.gov)
2. Reduce batch size (try 100 attorneys per batch instead of 200)
3. Add delays between requests in scraper config
4. Check Apify logs for specific errors

### Issue: process_scraped.py finds no emails

**Error**: `attorneys_step1.csv` has empty email column

**Solution**:
1. Check `scraped_b*.json` files have `rawEmail` field
2. Verify email deobfuscation is working (see CLAUDE.md for algorithm)
3. Run scraper again with updated regex pattern

### Issue: Missing firm/city data after Step 3

**Error**: `attorneys_final.csv` has blank Firm/City columns

**Solution**:
1. Verify `step2_s2b*.json` files exist and have data
2. Check bar numbers in Step 1 output match Step 2 input
3. Ensure address regex is extracting correctly (may need tweaking per format)

### Issue: Python script errors

**Common errors**:
- `FileNotFoundError`: Script can't find `scraped_b*.json` files
  - Check files are in same directory as script
  - Run from correct folder: `C:\Users\ninag\Claude\Projects\attorney_scraper\`

- `UnicodeDecodeError`: File encoding issue
  - Ensure JSON files are UTF-8 encoded (usually are by default)

---

## Next Steps After Setup

1. **Review results**: Open `attorneys_final.csv` and check data quality
2. **Customize outreach**: Edit personalization template in `send_campaign.gs`
3. **Send campaign**: Run Google Apps Script to email attorneys
4. **Track responses**: Use Gmail labels or CRM to track replies

---

## Time Estimate

| Step | Time | Notes |
|------|------|-------|
| Apify setup | 15 min | Create account, get API key |
| Run Apify scraper (Steps 1+2) | 90 min | Batches run in parallel; you wait |
| Run Python scripts | 5 min | Fully automated |
| Email campaign setup | 10 min | Import CSV, add script |
| **Total** | **~2 hours** | Mostly waiting for Apify |

---

## Questions?

- **Apify**: See https://apify.com/docs/
- **Regex/email extraction**: See `CLAUDE.md`
- **Python errors**: Check script comments in `process_scraped.py`, `build_final_csv.py`
- **General workflow**: See `README.md`

---

**Ready to start?** Begin with [Step 0: Apify Setup](#step-0-apify-setup-critical--do-this-first) above.
