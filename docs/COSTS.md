# Cost estimate (Indian rupees)

Generated with `python -m leadcollector costs --usd-inr 90 --tax-rate 0.18`.
**ASSUMPTIONS (not verified):** 1 USD = Rs 90; 18% tax on foreign cloud services; only about half of each Google result page is new
(overlapping searches); nothing else billed on the Google project this month. Edit `.env` (`USD_INR`, `TAX_RATE`) with real figures.

| Records | Overture | OSM/Overpass | Site enrichment | Google (requests -> Rs) | Licensed provider example (Rs) |
|---|---|---|---|---|---|
| 1,000 | Rs 0 | Rs 0 | Rs 0 (own PC) | 101 -> Rs 0 | Rs 796 |
| 5,000 | Rs 0 | Rs 0 | Rs 0 (own PC) | 501 -> Rs 0 | Rs 7,168 |
| 10,000 | Rs 0 | Rs 0 | Rs 0 (own PC) | 1001 -> Rs 4 | Rs 15,134 |

## How to read this

- **Overture / OSM / enrichment:** no fees. Your costs are your own internet and PC time. Enrichment is slow, not expensive.
- **Google:** the figures assume USD 35 per 1,000 Text Search Enterprise requests (third-party-reported, matches Google's SKU tiers) and the 1,000 free Enterprise events per month. They look near zero **only because of the free cap**; the cost is the terms (storage/use restrictions), not the rupees. Going past the cap costs roughly Rs 3,700 per extra 1,000 requests including assumed tax.
- **Licensed provider example:** a *placeholder* based on one third-party-reported price (USD 15 per 1,000 calls after 500 free). Real quotes will differ and may bill per record or per credit. Get quotes for your geography.
- **Hosting:** Rs 0 on your Windows PC. A small cloud VM would add a monthly fee (not priced here - no verified quote). 
- **PostgreSQL:** free if local; managed hosting is extra.
- **Completeness:** not promised. Phone and website will be missing for many businesses; the pilot reports the real percentages and cost per record with a phone.

## Zero-cost prototype

Overture (or OSM) + website enrichment + CSV on your own PC. Cost when scaling to 10,000: still Rs 0 in fees, but expect
longer runtimes (enrichment is rate-limited by design), and you may need to cover several cities or a licensed list to reach 10,000
records that have phones.
