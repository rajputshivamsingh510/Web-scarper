from leadcollector.costs import estimate_table, google_cost_inr


def test_google_free_cap_and_billing():
    assert google_cost_inr(1000, 90, 0.18) == 0
    assert round(google_cost_inr(2000, 100, 0.0)) == 3500  # 1000 billable * $35/1000 * 100


def test_table_shape():
    rows = estimate_table(90, 0.18)
    assert [r["records"] for r in rows] == [1000, 5000, 10000]
