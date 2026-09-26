from trade_simulator.adapters.text_links import split_links


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
