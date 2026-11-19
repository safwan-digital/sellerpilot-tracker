# SellerPilot Price Watch v0.2 — GitHub Actions edition

This distribution has TWO folders:

- `extension/` — load **this folder** in Chrome using `chrome://extensions` → Developer mode → **Load unpacked**.
- `github-repo/` — upload the contents of **this folder** to a GitHub repository to enable scheduled checks.

## Step 1: Update the Chrome extension

1. Extract the ZIP fully; do not select the ZIP itself.
2. Visit `chrome://extensions` and switch on Developer mode.
3. Remove the old v0.1 extension (your locally saved products may be deleted!) **or preferably back up your CSV and watchlist first**.
4. Click **Load unpacked** and select `extension/` (containing `manifest.json`).
5. Scan and save a real product, visually checking the displayed price.
6. Click **Export watchlist JSON**. This creates `watchlist.json`.

**IMPORTANT:** Updating an unpacked extension at a *different path* typically changes the Chrome extension ID and loses access to old `chrome.storage.local` data. To preserve it, copy these updated extension files into the exact old extension folder and click Reload on `chrome://extensions`; export your v0.1 CSV first either way. The CSV file is a backup but v0.2 does not include a CSV-history import feature.

## Step 2: Set up free GitHub checks

1. Sign in at https://github.com and create a repository, for example `sellerpilot-tracker`.
2. Decide visibility carefully: **public repository = tracked product links, historical prices, and scripts are public**. GitHub Actions standard runners are free for public repositories; private repositories have included-minute allowances and may accrue charges over quota.
3. Upload **the contents** of `github-repo/` to the repository root, preserving `.github/workflows/price-check.yml` (hidden folders must be included). Easiest with GitHub Desktop or Git: copy contents to a local repository and commit/push.
4. Back in Chrome, save your products and click **Export watchlist JSON**.
5. Replace `config/watchlist.json` on GitHub with the exported file. Each time you add/remove tracked products, repeat this export and upload. The extension cannot upload directly to GitHub in this version.
6. Go to **repository Settings → Actions → General → Workflow permissions** and allow **Read and write permissions** if required for commit-back. This permission allows the workflow to commit `docs/latest.json` and `docs/history.json` using the repo's built-in `GITHUB_TOKEN` (no personal access token needed).
7. In **Actions**, select **Scheduled competitor price checks** → **Run workflow**. Inspect logs and `docs/latest.json` for results. GitHub scheduled runs will start automatically once the workflow is on the default `main` branch.
8. In the Chrome extension, enter `YOUR_GITHUB_USERNAME/sellerpilot-tracker` and click **Save repository**, then **Sync from GitHub**. It imports up to 120 successful historical checks per URL from public `docs/history.json`.

**Default schedule:** `17 2,8,14,20 * * *` (UTC), about every six hours; exact execution time is NOT guaranteed. Change the cron line in `.github/workflows/price-check.yml` if desired. Scheduled workflows in inactive public repos may be disabled after 60 days, and cron can be delayed or skipped.

### Private repo option

`Sync from GitHub` works with a **PUBLIC** repository only. If you need private watchlists and reports, keep your repo private. Run the workflow and download `docs/latest.json` through the private GitHub UI, then use **Import results JSON** in Chrome. **Do not paste GitHub access tokens into the extension.** For the full history in a private repo, data in `docs/history.json` is intended for the public sync format and needs manual transformation; v0.2 imports `latest.json` directly.

### What the script can and cannot do

- Checks at most 100 HTTPS product URLs sequentially, with timeouts and robot rules respected.
- Extracts `Product.offers.price` from JSON-LD or recognized HTML price meta tags. Results with a mismatched currency are rejected.
- No CAPTCHA bypass, proxy rotation, login, private pages, hidden APIs, or aggressive scraping.
- Amazon/Noon and other marketplace pages may block robots, automated access, return a CAPTCHA, or require JavaScript rendering. For those pages **the script records an error rather than a fake price**. The Chrome manual scanner can still work when the browser shows a price.
- A successful fetch is not guaranteed to reflect a selected variant, delivery, coupon, tax or checkout price. Verify prices before acting.
- No push alerts yet. Chrome sync is user-initiated, but checks run while your browser is closed.
- Public repo history includes competitor URLs and captured prices and therefore may reveal research interests.
- Private repo Actions usage may be charged if you exceed current included allowances; review GitHub Billing settings.

### Example result

```json
{
  "schema_version": 1,
  "generated_at": "2026-11-19T10:00:00Z",
  "products": [{"url":"https://example.com/product","title":"Example","checked_at":"2026-11-19T10:00:00Z","status":"ok","price":84.99,"currency":"AED","source":"JSON-LD Product offers"}]
}
```

### Troubleshooting

- **Manifest missing:** choose the `extension/` folder, not the ZIP root.
- **No GitHub data:** ensure the workflow is on the `main` branch, Actions are enabled, and `config/watchlist.json` includes actual product URLs.
- **Permission denied on push:** enable workflow **Read and write permissions** in repo Settings → Actions → General.
- **404 during sync:** repo may be private, not named `owner/repo`, or files may not be on `main`.
- **HTTP 403 / robot denial / missing price metadata:** the site cannot be checked using this simple free checker; do not assume the price is unchanged.

### Security and privacy

No customer login, credentials, paid scraping API or third-party tracking is included. The extension fetches GitHub public history only when you click Sync. GitHub Actions has write access only to its own repository as configured in the workflow. Do not upload sensitive price/cost strategies to a public repository.
