"""
test_questions.py

A small hardcoded set of test queries with the course code they should
retrieve. Runs retrieval (not generation, which costs API credits) and
checks whether the expected course's chunks come back in the top-k.

For hallucination checking of generated answers, run with --generate to
also call the LLM and manually eyeball the output against the reviews.

USAGE
-----
python -m src.eval.test_questions              # retrieval-only check
python -m src.eval.test_questions --generate    # also generate answers
"""

from __future__ import annotations

import argparse

from src.rag.retriever import retrieve

TEST_CASES = [
    {"query": "Is CS2030 hard for beginners?", "expected_code": "CS2030"},
    {"query": "What is the workload like for CS2040?", "expected_code": "CS2040"},
    {"query": "How difficult is CS1101S for someone new to programming?", "expected_code": "CS1101S"},
    {"query": "Do I need a strong math background for MA1521?", "expected_code": "MA1521"},
    {"query": "Is GEA1000 an easy GE module?", "expected_code": "GEA1000"},
    {"query": "How much programming/algorithms background do I need before CS3230?", "expected_code": "CS3230"},
    {"query": "What do students say about the professors teaching IS1108?", "expected_code": "IS1108"},
    {"query": "Which modules have manageable weekly lab assignments?", "expected_code": None},
    {"query": "Tell me about the prerequisites for CS2030", "expected_code": "CS2030"},
    {"query": "What's a good easy module to fulfil GE requirements?", "expected_code": None},
]


def run_retrieval_eval() -> dict:
    passed = 0
    for case in TEST_CASES:
        chunks = retrieve(case["query"], k=5)
        codes_returned = {c["course_code"] for c in chunks}

        if case["expected_code"] is None:
            ok = len(chunks) > 0
        else:
            ok = case["expected_code"] in codes_returned

        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(f"[{status}] \"{case['query']}\" -> expected={case['expected_code']} got={codes_returned}")

    print(f"\n{passed}/{len(TEST_CASES)} retrieval checks passed")
    return {"passed": passed, "total": len(TEST_CASES)}


def run_generation_eval():
    from src.rag.generate import answer_question

    for case in TEST_CASES:
        print(f"\n=== {case['query']} ===")
        result = answer_question(case["query"])
        print(result["answer"])
        print(f"(based on {len(result['sources'])} source chunks)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true", help="also run generation (uses API credits)")
    args = parser.parse_args()

    run_retrieval_eval()
    if args.generate:
        run_generation_eval()


if __name__ == "__main__":
    main()
