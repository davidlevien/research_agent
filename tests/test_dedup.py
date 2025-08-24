from research_system.tools.dedup import minhash_near_dupes
def test_near_duplicate_grouping():
    t1 = "Press release: Company A launches product. Great benefits."
    t2 = "Company A launches product. Great benefits. (Press release)"
    groups = minhash_near_dupes([t1,t2], shingle_size=5, threshold=0.9)
    assert groups and len(groups[0]) == 2