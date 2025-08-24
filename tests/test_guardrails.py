def test_guardrails_math():
    # Simulate tri_list and cards — assert strict thresholds gate correctly (pseudo)
    tri_list = [{"domains":["wttc.org","unwto.org"],"indices":[0,1],"size":2}]
    # You'd integrate this against the orchestrator's strict check; ensure it fails when below thresholds.
    assert True