import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe, load_listings

# Tool 1 tests
def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)

def test_search_size_filter():
    results = search_listings("tee", size="M", max_price=None)
    assert all("m" in item["size"].lower() for item in results)

def test_search_top_result_most_relevant():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    top = results[0]
    searchable = (top["title"] + " " + " ".join(top["style_tags"])).lower()
    assert "graphic" in searchable or "tee" in searchable

# Tool 2 tests
def test_suggest_outfit_with_wardrobe():
    item = load_listings()[0]
    result = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0

def test_suggest_outfit_empty_wardrobe():
    item = load_listings()[0]
    result = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0

# Tool 3 tests
def test_fit_card_returns_string():
    item = load_listings()[0]
    result = create_fit_card("Pair with baggy jeans and white sneakers.", item)
    assert isinstance(result, str)
    assert len(result) > 0

def test_fit_card_empty_outfit():
    item = load_listings()[0]
    result = create_fit_card("", item)
    assert "Error" in result

def test_fit_card_varies():
    item = load_listings()[0]
    outfit = "Pair with baggy jeans and white sneakers."
    result1 = create_fit_card(outfit, item)
    result2 = create_fit_card(outfit, item)
    assert result1 != result2