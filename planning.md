# FitFindr — planning.md

> Complete this document before writing any implementation code.

---

## Tools

### Tool 1: search_listings

**What it does:**
Searches `data/listings.json` for secondhand items matching a natural language
description, optional size, and optional price ceiling. Scores each listing by
keyword overlap with the description, filters by size and price, drops
zero-score results, and returns the survivors ranked best-first. No LLM — pure
Python.

**Input parameters:**

- `description` (str): Keywords describing the item (e.g. `"vintage graphic tee"`).
  Matched case-insensitively against each listing's `title`, `description`,
  `style_tags` (list of str), `category` (str), and `colors` (list of str).
- `size` (str | None): Size string to filter by (e.g. `"M"`). Case-insensitive
  substring match against the listing's `size` field, which can be values like
  `"M"`, `"S/M"`, `"W30 L30"`, `"XL (oversized)"`, `"One Size"`, `"US 7"`.
  Pass `None` to skip size filtering.
- `max_price` (float | None): Maximum price inclusive (e.g. `30.0`). Compared
  against the listing's `price` field (always a float, e.g. `18.0`, `38.0`).
  Pass `None` to skip price filtering.

**What it returns:**
A list of listing dicts sorted by relevance score descending. Each dict has:

| Field | Type | Example |
|---|---|---|
| `id` | str | `"lst_006"` |
| `title` | str | `"Graphic Tee — 2003 Tour Bootleg Style"` |
| `description` | str | `"Vintage-style bootleg tee with faded graphic..."` |
| `category` | str | `"tops"` |
| `style_tags` | list[str] | `["graphic tee", "vintage", "grunge", "streetwear", "band tee"]` |
| `size` | str | `"L"` |
| `condition` | str | `"good"` |
| `price` | float | `24.0` |
| `colors` | list[str] | `["black"]` |
| `brand` | str or null | `null` |
| `platform` | str | `"depop"` |

Returns `[]` if nothing matches — never raises an exception.

**What happens if it fails or returns nothing:**
`run_agent` checks the result immediately. If `[]`, it sets
`session["error"] = "No listings matched your search. Try a broader
description, a different size, or raising your price limit."` and returns the
session early. `suggest_outfit` and `create_fit_card` are never called.

---

### Tool 2: suggest_outfit

**What it does:**
Calls the Groq LLM to suggest 1–2 outfits that pair the thrifted item with
pieces from the user's existing wardrobe. Handles an empty wardrobe gracefully
by switching to general styling advice.

**Input parameters:**

- `new_item` (dict): A listing dict from `search_listings`. Key fields used:
  `title`, `style_tags`, `colors`, `category`, `condition`, `brand`.
- `wardrobe` (dict): A wardrobe dict with an `"items"` key containing a list
  of wardrobe item dicts. Each wardrobe item has:

  | Field | Type | Example |
  |---|---|---|
  | `id` | str | `"w_001"` |
  | `name` | str | `"Baggy straight-leg jeans, dark wash"` |
  | `category` | str | `"bottoms"` |
  | `colors` | list[str] | `["dark blue", "indigo"]` |
  | `style_tags` | list[str] | `["denim", "streetwear", "baggy"]` |
  | `notes` | str or null | `"High-waisted, sits above the hip"` |

  `wardrobe["items"]` may be `[]` for a new user — handle this without crashing.

**What it returns:**
A non-empty string with outfit suggestions. If the wardrobe has items, the
response names specific pieces from the wardrobe (e.g. "pair with your baggy
dark-wash jeans and black combat boots"). If the wardrobe is empty, returns
general styling advice for the item's aesthetic and style tags.

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is `[]`, the LLM is still called — with a different
prompt asking for general styling ideas rather than wardrobe-specific combos.
The function always returns a non-empty string and never raises an exception.

---

### Tool 3: create_fit_card

**What it does:**
Calls the Groq LLM (at higher temperature, e.g. `0.9`) to generate a 2–4
sentence outfit caption that sounds like a real OOTD post, not a product
description. Each call should feel distinct.

**Input parameters:**

- `outfit` (str): The outfit suggestion string from `suggest_outfit`.
- `new_item` (dict): The listing dict. Key fields used: `title` (str),
  `price` (float), `platform` (str, e.g. `"depop"`, `"poshmark"`,
  `"thredUp"`).

**What it returns:**
A 2–4 sentence string that mentions the item name, price, and platform
naturally (once each) and captures the outfit vibe in specific terms.
Returns a descriptive error string if `outfit` is empty — does not raise
an exception.

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace-only, returns
`"Error: outfit suggestion is missing — cannot generate fit card."`
and skips the LLM call.

---

### Additional Tools (if any)

None for the base implementation.

---

## Planning Loop

The loop is **linear and deterministic** — tools always run in order 1 → 2 → 3,
with one early-exit point after Tool 1.

1. **Parse** the user's query with the LLM (see State Management for why).
   Store `{description, size, max_price}` in `session["parsed"]`.

2. **Call `search_listings()`** with the parsed parameters.
   - If result is `[]` → set `session["error"]` with a helpful retry message,
     return the session immediately. Do not proceed.
   - If result is non-empty → set `session["search_results"] = results`,
     set `session["selected_item"] = results[0]`.

3. **Call `suggest_outfit(selected_item, wardrobe)`**.
   Store the returned string in `session["outfit_suggestion"]`.

4. **Call `create_fit_card(outfit_suggestion, selected_item)`**.
   Store the returned string in `session["fit_card"]`.

5. **Return** the completed session dict.

The agent does not re-rank results using the LLM. `search_listings` handles
ranking via keyword scoring; the agent simply trusts `results[0]`.

---

## State Management

All state lives in the session dict created by `_new_session()`. No tool
receives raw user input directly — everything flows through the session.

| Step | Reads from session | Writes to session |
|---|---|---|
| Parse query | `session["query"]` | `session["parsed"]` → `{description, size, max_price}` |
| search_listings | `session["parsed"]` | `session["search_results"]` (list of dicts) |
| Select item | `session["search_results"]` | `session["selected_item"]` (single dict) |
| suggest_outfit | `session["selected_item"]`, `session["wardrobe"]` | `session["outfit_suggestion"]` (str) |
| create_fit_card | `session["outfit_suggestion"]`, `session["selected_item"]` | `session["fit_card"]` (str) |

**On query parsing — why LLM, not regex:**
The listings dataset shows that size values are highly inconsistent
(`"W30 L30"`, `"S/M"`, `"XL (oversized)"`, `"One Size"`, `"US 7"`). A user
might say "size medium", "fits like a small", or "men's large". Regex can't
reliably normalize these. A short LLM call (asked to return JSON with keys
`description`, `size`, `max_price`) handles natural language variation much
better. The tradeoff is one extra Groq call per interaction, which is
acceptable.

---

## Error Handling

| Tool | Failure mode | Agent response |
|---|---|---|
| `search_listings` | Returns `[]` — no listings match the query | Sets `session["error"] = "No listings matched your search. Try a broader description, a different size, or raising your price limit."` Returns the session immediately. Tools 2 and 3 are never called. |
| `suggest_outfit` | `wardrobe["items"]` is `[]` | Switches to a different LLM prompt asking for general styling advice (what vibes suit the item, what kinds of pieces pair well). Always returns a non-empty string — no early exit. |
| `create_fit_card` | `outfit` param is empty or whitespace | Returns `"Error: outfit suggestion is missing — cannot generate fit card."` immediately, skips the LLM call entirely. |

---

## Architecture

```
User Query (str)
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  run_agent(query, wardrobe)                         │
│                                                     │
│  1. Parse query via LLM                             │
│     → session["parsed"]                             │
│       {description: str, size: str|None,            │
│        max_price: float|None}                       │
│                                                     │
│  2. search_listings(description, size, max_price)   │──► results == []
│     → session["search_results"]                     │        │
│     → session["selected_item"] = results[0]         │        ▼
│                                                 session["error"] = "No
│  3. suggest_outfit(selected_item, wardrobe)     │    listings matched..."
│     → session["outfit_suggestion"]              │        │
│       (wardrobe empty? → general styling advice)│        ▼
│                                                 │    return session (early)
│  4. create_fit_card(outfit_suggestion,          │
│                     selected_item)              │
│     → session["fit_card"]                       │
│                                                 │
│  5. return session                              │
└─────────────────────────────────────────────────┘
         │
         ▼
  Caller reads session["fit_card"]
  (or session["error"] if set)
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

For `search_listings`: Give Claude the Tool 1 block from this file (inputs,
return value, failure mode) plus 3 sample listings from `data/listings.json`.
Ask it to implement the function using `load_listings()` from
`utils/data_loader.py`. Verify the generated code: (a) filters by `max_price`
and `size` before scoring, (b) scores by keyword overlap across `title`,
`description`, `style_tags`, `category`, and `colors`, (c) drops zero-score
results, (d) returns `[]` on no match. Test with 3 queries: one that returns
results, one with a price too low, one with an unusual size.

For `suggest_outfit`: Give Claude the Tool 2 block from this file plus the
wardrobe schema from `data/wardrobe_schema.json`. Ask it to implement both
prompt branches (wardrobe present vs. empty). Verify the output names specific
wardrobe items by their `name` field when wardrobe is non-empty, and gives
general style advice when `items` is `[]`.

For `create_fit_card`: Give Claude the Tool 3 block from this file. Ask it to
set temperature to `0.9` and write a prompt that specifies: casual OOTD tone,
mention `title`/`price`/`platform` once each, 2–4 sentences. Verify the
caption doesn't sound like a product listing and that it changes across
multiple calls.

**Milestone 4 — Planning loop and state management:**

Give Claude the Planning Loop section, State Management table, and Architecture
diagram from this file. Ask it to implement `run_agent()` in `agent.py`.
Verify: (a) `_new_session()` is called first, (b) empty results from
`search_listings` triggers early return with an error message, (c) `results[0]`
is stored as `selected_item`, (d) tools are called in the correct order with
the correct session fields as arguments.

---

## A Complete Interaction (Step by Step)

**In plain terms:** FitFindr takes a natural language shopping request and the
user's current wardrobe, finds matching secondhand listings by keyword
relevance, uses an LLM to suggest how to style the best match with the user's
existing clothes, then generates a shareable caption. Each tool's output feeds
directly into the next via the session dict. If search returns nothing,
FitFindr gives a specific retry suggestion and stops — it never passes empty
data to the LLM tools.

**Example user query:**
`"I'm looking for a vintage graphic tee under $30, size M. I mostly wear baggy jeans and chunky sneakers."`

**Step 1 — Parse + Search:**
The LLM parses the query and extracts:
`{description: "vintage graphic tee", size: "M", max_price: 30.0}`.
`search_listings("vintage graphic tee", size="M", max_price=30.0)` loads all
40 listings, filters to those with `price ≤ 30.0` and `size` containing `"M"`.
Each survivor is scored by how many of the words "vintage", "graphic", "tee"
appear across its searchable fields. Top result:
`lst_006 — "Graphic Tee — 2003 Tour Bootleg Style", $24, depop, size L`
(note: size L passes the "M" filter if the substring match is loose — otherwise
lst_002 or lst_033 would rank higher at size S/M and L respectively).

**Step 2 — Outfit suggestion:**
`suggest_outfit(new_item=lst_006_dict, wardrobe=example_wardrobe)`.
Wardrobe has 10 items. LLM prompt includes the tee's style tags
(`vintage, grunge, graphic tee, streetwear, band tee`) and the wardrobe list.
LLM returns: `"Pair this with your baggy dark-wash jeans and black combat boots
for a classic 90s grunge look. Tuck the front corner slightly for shape and
throw your vintage black denim jacket over top if it's cold."`

**Step 3 — Fit card:**
`create_fit_card(outfit=<suggestion>, new_item=lst_006_dict)`.
LLM (temperature 0.9) returns:
`"thrifted this 2003 bootleg tee off depop for $24 and it just lives with my
baggy jeans now 🖤 the grunge is real. full fit in my stories"`

**Error path:**
If Step 1 returned `[]` (e.g. query was `"designer ballgown size XXS under $5"`),
the agent sets `session["error"] = "No listings matched your search. Try a
broader description, a different size, or raising your price limit."` and
returns immediately. Steps 2 and 3 are never called.

**Final output to user:**
```
Found: Graphic Tee — 2003 Tour Bootleg Style ($24.00, depop)

Outfit: Pair this with your baggy dark-wash jeans and black combat boots for a
classic 90s grunge look. Tuck the front corner slightly for shape and throw
your vintage black denim jacket over top if it's cold.

Fit card: thrifted this 2003 bootleg tee off depop for $24 and it just lives
with my baggy jeans now 🖤 the grunge is real. full fit in my stories
```