# Part 1: Data Collection, Explained Simply

Prepared 29 Oct 2026

## 1. What Part 1 does

Part 1 finds businesses in a city, for example **jewellers in Ludhiana** or **doctors in Amritsar**, and gives you a clean spreadsheet (CSV file) with their name, phone number, website, category and address.

Think of it as a helper that:

1. looks up a list of businesses in a free map database,
2. tidies the list (fixes phone numbers, removes repeats),
3. visits each business website, politely, to check it works and to look for a missing phone number,
4. saves the result and a short report on how good the list is.

It does **not** call anyone, send messages or load anything into TeleCRM. That is Part 2.

## 2. The flowchart

Read it from top to bottom. Each box is explained in section 3.

&#91;embedded content: collection flow · 8 steps, 1 decision\]

A record with no usable website skips step 7 and goes straight to the final checks.

## 3. The steps in plain words

The example below is *jewellers in Ludhiana, up to 150 records*.

**Step 1: You choose what to search** You give the source (Overture Maps or OpenStreetMap), the state, the city, the category and how many records you want. You can do this on the web page (`python server.py`) or with a command. Optional settings: a minimum confidence score and a map rectangle (bounding box).

**Step 2: The tool finds the area on the map** It asks a free service called Nominatim for the rectangle that covers Ludhiana. The answer is saved, so the next search for Ludhiana does not ask again. If you typed your own rectangle, this step is skipped.

**Step 3: It gets the businesses** It reads all businesses of that category inside the rectangle from the source you chose. No Google Maps pages are scraped. In your Ludhiana run this step returned 235 raw records.

**Step 4: It cleans each record**

- Phone numbers become one standard format, for example `+911612223344`. Numbers that are not valid are dropped, never guessed.
- Website addresses are tidied (tracking parts removed, `https://` added).
- Extra spaces in names are removed.

**Step 5: It removes duplicates** Two records are merged only when the evidence agrees: the same phone number and a similar name, or a very similar name plus the same website, a place within 200 metres, or a similar address. Two branches of the same shop with different phones or addresses stay separate. It is safer to keep a rare duplicate than to merge two real shops.

**Step 6: It keeps the best records** It measures how many candidates have a phone and a website. Then it puts records with a phone first, then those with a website, then the most confident, and keeps the number you asked for (150). The coverage figures in the report come from **before** this step, so they are honest.

**Step 7: It visits the business websites** For each record that has a website, it:

- skips Facebook, Instagram, TikTok, WhatsApp links, directory pages and email-provider addresses, because those are not the business's own site,
- reads the site's `robots.txt` rules and obeys them,
- opens the home page, and if there is no phone and a Contact page exists, opens up to two more pages (never more than three),
- looks for phone numbers, starting with clickable `tel:` links,
- waits at least one second between requests to the same site. It only fills in a phone number when the record has none.

**Step 8: Final checks and saving** It checks phone formats again, merges any new duplicates that the website numbers revealed, applies your filters (only with phone, only with website) and writes the files.

## 4. What you get

Each search creates its own folder inside `data`:

| File | What it is |
| --- | --- |
| `leads.csv` | The final list. This is what you open in Excel. |
| `report.json` and `report.md` | Quality numbers: how many have phones, websites, duplicates, failures. |
| `stage1_collected.jsonl` | Saved copy after collecting and cleaning. Lets a stopped run resume. |
| `stage2_enriched.jsonl` | Saved progress of the website checks. |
| `run.log` | A log of what happened. |
| `data\cache\geocode.json` | Remembered city rectangles. |

## 5. The columns in the CSV

| Column | Meaning |
| --- | --- |
| `business_name` | Name from the source. |
| `phone` | Phone number in `+91` format. Blank if none was found. |
| `website` | The business website. Blank if none. |
| `category`, `city`, `address` | What the source says. |
| `source`, `source_id`, `source_url` | Where the record came from. |
| `attribution` | Credit line the data licence requires. Keep it if you share the data. |
| `phone_status` | `format_valid`, `invalid_format` or `missing`. This checks the format only. |
| `website_status` | See the table below. |
| `verification_status` | A summary. It always says that ownership and active status are not verified. |
| `phone_source` | Where the number came from: `overture`, `osm` or `website:<domain>`. |
| `extra_phones` | Up to two more numbers found. |
| `collected_at` | Date and time of collection. |
| `lead_key` | A short ID used to spot the same lead later. |

### What `website_status` means

| Value | Meaning |
| --- | --- |
| `reachable` | The site opened normally. |
| `unreachable` | The site did not answer, had a certificate problem or does not exist. |
| `error_404` (or another number) | The site answered with an error. |
| `robots_disallowed` | The site asks robots not to visit, so the tool did not. |
| `social_or_directory_page` | A social profile or listing page, so it was skipped. |
| `missing` | No website in the source. |
| `not_checked` | Website visits were switched off. |

## 6. Settings, explained

- **Source:** Overture Maps is a map database put together by large companies and usually has more phones and websites. OpenStreetMap is built by volunteers and is often thinner in India. You can use both together; duplicates are then merged.
- **Minimum confidence (Overture only):** a score from 0 to 1 for how likely a place is real. 0 keeps everything. Higher gives fewer, cleaner records.
- **Bounding box:** a map rectangle written as south, west, north, east. Leave it empty to use the city's automatic rectangle. Fill it to search one area only.
- **Pilot checks:** after the run, the report says Passed or Not passed against targets in your `.env` file (40% phone, 30% website, 20% both, no more than 25% invalid URLs). The targets are examples; change them.
- **Don't visit websites:** skips Step 7. Faster, but fewer phone numbers.

## 7. Safety rules built in

- Google Maps pages are not scraped.
- `robots.txt` is obeyed, and there is no login or CAPTCHA bypass.
- One request per second per website, with a short wait before trying again.
- A broken website never stops the run. It is counted in the report.
- Nothing is invented. If a phone or website was not found, the cell stays empty.
- Phone checks look at the format only. A number may still be wrong, disconnected or belong to someone else.
- Your keys and email stay in the `.env` file and are not written to logs.

## 8. Results from your two test runs

|  | Ludhiana jewellers | Amritsar doctors |
| --- | --- | --- |
| Raw records | 235 | 204 |
| Duplicates merged | 8 | 8 |
| Final records | 147 | 148 |
| With a website | 69 (46.9%) | 100 (67.6%) |
| Websites checked | 55 | 87 |
| Unreachable sites | 23 (41.8%) | 27 (31.0%) |
| Coverage before keeping the best | not measured (older version) | 97.5% phone, 51.5% website, 51.0% both |

Both runs showed **Not passed** only because of the invalid-URL target of 25%. That figure includes websites that timed out or returned server errors, which are common for small shops. It does not mean the phone numbers are bad. Raise the limit in `.env` if you agree.

The Ludhiana run used the older version, which kept records with phones first and made phone coverage look like 100%. The Amritsar run used the fixed version.

## 9. If something goes wrong

| Problem | What to do |
| --- | --- |
| "Could not find" or a Nominatim error | Set `CONTACT_EMAIL` in `.env`, wait a minute, or type a bounding box. |
| Overture cannot find the data | The release name in `.env` is out of date. Pick a current one on docs.overturemaps.org and set `OVERTURE_RELEASE`. |
| Run stopped half-way | Start again with `--resume --run-name <the same name>`. It continues without repeating. |
| Many sites unreachable | Normal for small shops. Check that your own internet is fine, then continue. |
| The web page does not open | Run `python server.py` and open `http://127.0.0.1:8000`. |
| Few new records | The area may be used up. Try another city or category. |

## 10. What Part 1 does not do yet

These gaps matter once Parts 2 and 3 start:

- It does not remember earlier runs, so a second search can return the same businesses again.
- It has no queue of areas to search, so someone must choose each search.
- It cannot start itself. A person starts every run.
- It does not check TeleCRM or any do-not-contact list.
