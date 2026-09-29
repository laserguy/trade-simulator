from trade_simulator.adapters.text_links import find_urls, keep_known, split_links


def test_markdown_links_become_plain_labels_and_urls_are_collected():
    text, urls = split_links(
        "Markets were mixed. Sources: [CNBC](https://www.cnbc.com/a), [U.S. Bank](https://www.usbank.com/b)."
    )

    assert text == "Markets were mixed."
    assert urls == ["https://www.cnbc.com/a", "https://www.usbank.com/b"]


def test_inline_links_keep_their_label_in_the_sentence():
    text, urls = split_links("Per [Reuters](https://reuters.com/x), NVDA beat estimates.")

    assert text == "Per Reuters, NVDA beat estimates."
    assert urls == ["https://reuters.com/x"]


def test_bare_urls_are_moved_out_of_the_text():
    text, urls = split_links("NVDA beat estimates (https://reuters.com/x).")

    assert text == "NVDA beat estimates."
    assert urls == ["https://reuters.com/x"]


def test_plain_text_is_unchanged():
    assert split_links("No links here.") == ("No links here.", [])


def test_find_urls_reads_links_from_json_tool_output():
    output = '[{"headline": "Beat", "url": "https://finnhub.io/api/news?id=abc123"}, {"url": "https://r.com/x"}]'

    assert find_urls(output) == {"https://finnhub.io/api/news?id=abc123", "https://r.com/x"}


def test_find_urls_ignores_trailing_punctuation_in_prose():
    assert find_urls("See https://r.com/x. Also (https://r.com/y), fine.") == {"https://r.com/x", "https://r.com/y"}


def test_keep_known_drops_sources_no_tool_returned():
    known = {"https://finnhub.io/api/news?id=" + "a" * 64, "https://r.com/x/"}

    kept = keep_known(("https://finnhub.io/api/news?id=" + "a" * 34, "https://r.com/x", "https://made.up/z"), known)

    assert kept == ("https://r.com/x",)  # a trailing slash difference still matches
