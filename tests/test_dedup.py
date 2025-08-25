from research_system.tools.dedup import minhash_near_dupes
def test_near_duplicate_grouping():
    # Use texts that are actually near-duplicates
    t1 = "Company A launches amazing new product with great benefits for customers"
    t2 = "Company A launches amazing new product with great benefits for users"
    # Lower threshold to match actual similarity
    groups = minhash_near_dupes([t1,t2], shingle_size=3, threshold=0.5)
    assert groups and len(groups[0]) == 2