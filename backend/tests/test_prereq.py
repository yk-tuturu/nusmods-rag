"""Run with: python -m tests.test_prereq (from backend/). No pytest needed."""

from src.rag.prereq import check_prereqs, evaluate_prereqs

CS2040S = {"and": [
    {"or": ["CS1010:D", "CS1010E:D", "CS1010X:D", "CS1101S:D", "CS1010S:D"]},
    {"or": ["CS1231S:D", "CS1231:D", "MA1100:D"]},
]}


def test_and_or_met():
    assert evaluate_prereqs(CS2040S, ["cs1010", "CS1231"])["status"] == "met"


def test_and_partial_reports_missing():
    r = evaluate_prereqs(CS2040S, ["CS1010"])
    assert r["status"] == "not_met"
    assert len(r["missing"]) == 1 and "CS1231" in r["missing"][0]


def test_no_tree_is_met():
    assert evaluate_prereqs(None, [])["status"] == "met"


def test_nof():
    tree = {"nOf": [2, ["A1:D", "B1:D", "C1:D"]]}
    assert evaluate_prereqs(tree, ["A1", "C1"])["status"] == "met"
    assert evaluate_prereqs(tree, ["A1"])["status"] == "not_met"


def test_wildcard():
    assert evaluate_prereqs({"or": ["AN%:D"]}, ["AN1101"])["status"] == "met"
    assert evaluate_prereqs({"or": ["AN%:D"]}, ["CS1010"])["status"] == "not_met"


def test_cohort_is_unknown():
    tree = {"or": [{"cohort": {"rule": "MUST_BE_IN", "years": ["S:2017"]}}]}
    assert evaluate_prereqs(tree, [])["status"] == "unknown"


def test_programtype_then():
    tree = {"programType": {"rule": "IF_IN", "types": ["CPE"]}, "then": "ADS5101:D"}
    assert evaluate_prereqs(tree, ["ADS5101"])["status"] == "met"
    assert evaluate_prereqs(tree, [])["status"] == "unknown"


def test_unknown_not_masked_by_false():
    tree = {"and": [{"cohort": {"rule": "MUST_BE_IN", "years": []}}, "X1:D"]}
    assert evaluate_prereqs(tree, [])["status"] == "not_met"


def test_real_course_lookup():
    r = check_prereqs("CS2040S", ["CS1010", "CS1231S"])
    assert r["status"] == "met", r
    r = check_prereqs("CS3230", ["CS1010"])
    assert r["status"] == "not_met" and r["missing"], r
    assert "error" in check_prereqs("ZZ9999", [])


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("PASS", name)
    print(f"{len(tests)} passed")
