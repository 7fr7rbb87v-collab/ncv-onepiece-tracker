# NCV eBay API Upgrade

This version pulls live eBay Browse API listings into the GitHub Pages dashboard.

## Required GitHub Secrets

Repo → Settings → Secrets and variables → Actions → Secrets:

- `EBAY_CLIENT_ID`
- `EBAY_CLIENT_SECRET`

Use Production keys from eBay Developer unless you intentionally want sandbox.

## Recommended GitHub Variables

Repo → Settings → Secrets and variables → Actions → Variables:

- `ENABLE_EBAY` = `1`
- `EBAY_MARKETPLACE_ID` = `EBAY_US`
- `EBAY_RESULTS_PER_PRODUCT` = `10`

## Upload

Upload the contents of this folder to your repo, not the ZIP itself.

Then run:

Actions → Update Deals → Run workflow

## Check status

Open:

`https://YOURUSERNAME.github.io/ncv-onepiece-tracker/data/ebay_status.json`

If there are errors, they will show in that file.

## Target math

- Offer Target = current listing price × 0.80
- Sale Target = current listing price × 1.35
- Target Spread = sale target - offer target

No auto-checkout. Manual review only.
