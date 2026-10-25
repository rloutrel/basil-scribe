"""Similarity search: cosine top-k over stored vectors."""

from precedents.index import cosine_top_k


def test_top_k_orders_by_cosine():
    query = [1.0, 0.0]
    candidates = [
        (1, [0.9, 0.1]),
        (2, [0.1, 0.9]),
        (3, [1.0, 0.0]),
        (4, [-1.0, 0.0]),
    ]
    top = cosine_top_k(query, candidates, k=3)
    assert [cid for cid, _ in top] == [3, 1, 2]
    assert top[0][1] == pytest_approx(1.0)


def pytest_approx(value):
    import pytest

    return pytest.approx(value)


def test_top_k_excludes_ids():
    query = [1.0, 0.0]
    candidates = [(1, [1.0, 0.0]), (2, [0.9, 0.1])]
    top = cosine_top_k(query, candidates, k=3, exclude_ids={1})
    assert [cid for cid, _ in top] == [2]


def test_top_k_handles_bad_vectors():
    query = [1.0, 0.0]
    candidates = [
        (1, "not a vector"),
        (2, [1.0]),  # wrong shape
        (3, [0.0, 0.0]),  # zero norm
        (4, [float("nan"), 1.0]),
        (5, [1.0, 0.0]),
    ]
    top = cosine_top_k(query, candidates, k=3)
    assert [cid for cid, _ in top] == [5]


def test_top_k_empty_query_norm():
    assert cosine_top_k([0.0, 0.0], [(1, [1.0, 0.0])]) == []
