from research_system.tools.embed_cluster import hybrid_clusters
def test_paraphrases_cluster():
    texts = [
        "International tourist arrivals grew 5% in Q1 2025",
        "International tourist arrivals increased by 5% in the first quarter of 2025",
        "Tourist arrivals up 5% in first quarter 2025",
    ]
    clusters = hybrid_clusters(texts)
    assert any(len(c)>=2 for c in clusters)