# FitFindr 🛍️

A secondhand shopping agent that takes a natural language query, finds matching
listings, suggests an outfit using your existing wardrobe, and generates a
shareable fit card — all in one interaction.

Built with Python, Groq (llama-3.3-70b-versatile), and Gradio.

---

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── tests/
│   └── test_tools.py          # pytest tests for all three tools
├── planning.md                # Agent design spec — written before implementation
├── agent.py                   # Planning loop — run_agent()
├── app.py                     # Gradio UI — handle_query()
├── tools.py                   # Three agent tools
└── requirements.txt           # Python dependencies
```

---

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py
```

Open the URL shown in your terminal (usually `http://localhost:7860`).

---

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories
(tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k,
grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`,
`size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:

```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a
user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:

```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

---

## Tool Inventory

### Tool 1: `search_listings(description, size, max_price)`

**Purpose:** Searches `data/listings.json` for items matching the user's
request. Pure Python — no LLM call.

**Inputs:**
- `description` (str): Keywords describing the item (e.g. `"vintage graphic tee"`).
  Matched case-insensitively against each listing's `title`, `description`,
  `style_tags`, `category`, and `colors`.
- `size` (str | None): Size to filter by (e.g. `"M"`). Substring match against
  the listing's `size` field. Pass `None` to skip size filtering.
- `max_price` (float | None): Maximum price inclusive (e.g. `30.0`). Pass
  `None` to skip price filtering.

**Output:** A list of listing dicts sorted by relevance score descending.
Returns `[]` if nothing matches — never raises an exception.

---

### Tool 2: `suggest_outfit(new_item, wardrobe)`

**Purpose:** Uses the Groq LLM to suggest 1–2 outfit combinations pairing the
thrifted item with pieces from the user's existing wardrobe. Falls back to
general styling advice if the wardrobe is empty.

**Inputs:**
- `new_item` (dict): A listing dict from `search_listings`. Key fields used:
  `title`, `style_tags`, `colors`, `category`, `condition`, `brand`.
- `wardrobe` (dict): A wardrobe dict with an `"items"` key containing a list
  of wardrobe item dicts (each with `name`, `category`, `colors`, `style_tags`,
  `notes`). May be empty.

**Output:** A non-empty string with outfit suggestions. Either specific combos
using named wardrobe pieces, or general styling advice if the wardrobe is empty.

---

### Tool 3: `create_fit_card(outfit, new_item)`

**Purpose:** Uses the Groq LLM at higher temperature to generate a 2–4
sentence Instagram/TikTok-style caption for the outfit.

**Inputs:**
- `outfit` (str): The outfit suggestion string from `suggest_outfit`.
- `new_item` (dict): The listing dict. Key fields used: `title`, `price`,
  `platform`.

**Output:** A 2–4 sentence caption string mentioning the item name, price, and
platform naturally (once each). Returns a descriptive error string if `outfit`
is empty — never raises an exception.

---

## How the Planning Loop Works

The planning loop in `run_agent()` runs linearly with one early-exit branch:

1. **Parse** the user's query using the LLM to extract `description`, `size`,
   and `max_price` as JSON. LLM parsing is used instead of regex because
   listing sizes are inconsistent (`"W30 L30"`, `"S/M"`, `"XL (oversized)"`,
   `"US 7"`) and users phrase sizes naturally ("size medium", "fits like a small").

2. **Call `search_listings()`** with the parsed parameters.
   - If result is `[]` → set a helpful error message in the session and return
     immediately. `suggest_outfit` and `create_fit_card` are never called.
   - If results exist → take `results[0]` as `selected_item`.

3. **Call `suggest_outfit()`** with the selected item and wardrobe.

4. **Call `create_fit_card()`** with the outfit suggestion and selected item.

5. **Return** the completed session dict.

---

## State Management

All state lives in a single session dict created at the start of each
`run_agent()` call. No tool receives raw user input directly — everything
flows through the session.

| Step | Reads | Writes |
|------|-------|--------|
| Parse query | `session["query"]` | `session["parsed"]` → `{description, size, max_price}` |
| search_listings | `session["parsed"]` | `session["search_results"]`, `session["selected_item"]` |
| suggest_outfit | `session["selected_item"]`, `session["wardrobe"]` | `session["outfit_suggestion"]` |
| create_fit_card | `session["outfit_suggestion"]`, `session["selected_item"]` | `session["fit_card"]` |

---

## Error Handling

### `search_listings` — no results
Returns `[]`. `run_agent` catches this immediately and sets:
```
"No listings matched your search. Try a broader description, a different size,
or raising your price limit."
```
`suggest_outfit` and `create_fit_card` are never called. `session["fit_card"]`
remains `None`.

**Verified with:**
```bash
python -c "
from agent import run_agent
from utils.data_loader import get_example_wardrobe
session = run_agent('designer ballgown size XXS under 5 dollars', get_example_wardrobe())
print('error:', session['error'])
print('fit_card:', session['fit_card'])
"
# error: No listings matched your search. Try a broader description...
# fit_card: None
```

### `suggest_outfit` — empty wardrobe
Switches to a different LLM prompt asking for general styling advice. Always
returns a non-empty string — never crashes.

**Verified with:**
```bash
python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(results[0], get_empty_wardrobe()))
"
# Returns: general styling advice paragraphs, no exception
```

### `create_fit_card` — empty outfit string
Returns `"Error: outfit suggestion is missing — cannot generate fit card."`
immediately, skips the LLM call entirely.

**Verified with:**
```bash
python -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
"
# Error: outfit suggestion is missing — cannot generate fit card.
```

---

## Running Tests

```bash
pytest tests/ -v
```

10 tests covering all three tools and their failure modes.

---

## Spec Reflection

**One way the spec helped:** Writing the state management table in `planning.md`
before implementing `run_agent()` made the planning loop straightforward to
code. Knowing exactly what each step reads and writes meant there was no
ambiguity about which session fields to populate or in what order.

**One way implementation diverged from the spec:** The spec described LLM query
parsing as a simple JSON extraction step. In practice, the LLM occasionally
returns JSON wrapped in markdown fences (` ```json ... ``` `) which causes
`json.loads()` to fail. The implementation added a cleanup step to strip
markdown formatting before parsing — a runtime quirk not visible at planning time.

---

## AI Usage

### Instance 1 — Implementing `search_listings`
**Input to AI:** The Tool 1 spec block from `planning.md` (inputs with types,
scoring logic, failure mode) plus 3 sample listings from `data/listings.json`.

**What it produced:** A complete implementation using `load_listings()`,
filtering by price and size with substring matching, scoring by keyword overlap
across 5 fields, and returning a sorted list.

**What I verified:** The size filter used `size.lower() in item["size"].lower()`
— correct for handling `"S/M"` when the user asks for `"M"`. Confirmed by
running `pytest tests/` and checking all 5 Tool 1 tests passed.

### Instance 2 — Implementing `run_agent()` planning loop
**Input to AI:** The Planning Loop section, State Management table, and
Architecture diagram from `planning.md`.

**What it produced:** A complete `run_agent()` implementation with LLM query
parsing, early exit on empty results, and correct session dict writes at each
step.

**What I revised:** Added a markdown-fence strip step before `json.loads()` to
handle cases where the LLM wraps its JSON response in ` ```json ``` `. Also
verified that `results[0]` was stored as `session["selected_item"]` before
being passed to `suggest_outfit` — confirming state flowed correctly rather
than being re-fetched.