from research_system.tools.claim_select import select_claim_sentences
def test_picks_numeric_sentence():
    txt = "The report discusses trends. International arrivals grew 5% in Q1 2025. Notes."
    sents = select_claim_sentences(txt)
    assert "5%" in sents[0].lower()