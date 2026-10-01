"""Failing tests for daari_core.graph (T2), written against the real T0
seed taxonomy and the deterministic embeddings fixture (D18). Hours/ids
referenced below match data/taxonomy/skills.yaml exactly; if that file
changes, these numbers must move with it.
"""

import random

from daari_core import graph, taxonomy
from tests.fixtures.embeddings import seeded_embedding


def _all_embeddings(skills_data) -> dict:
    return {node["id"]: seeded_embedding(node["id"]) for node in skills_data}


def _edge_set(g: "graph.Graph") -> set[tuple[str, str, str, float]]:
    return {(u, v, data["kind"], round(float(data["weight"]), 6)) for u, v, data in g.nx.edges(data=True)}


def test_prereq_edge_weight_is_hours(skills_data, roles_data):
    tax = taxonomy.load(skills_data, roles_data)
    g = graph.build(tax, _all_embeddings(skills_data), pmi=None)

    excel_advanced_hours = tax.skills["excel_advanced"].hours
    edges = [
        (u, v, data)
        for u, v, data in g.nx.edges(data=True)
        if data["kind"] == "prereq" and u == "ms_excel_basic" and v == "excel_advanced"
    ]
    assert len(edges) == 1, "expected exactly one prereq edge ms_excel_basic -> excel_advanced"
    assert edges[0][2]["weight"] == excel_advanced_hours


def test_adjacency_edge_iff_cosine_ge_0_75_and_weight_is_0_3_hours(skills_data, roles_data):
    tax = taxonomy.load(skills_data, roles_data)
    g = graph.build(tax, _all_embeddings(skills_data), pmi=None)

    tableau_hours = tax.skills["data_visualization_tableau"].hours
    powerbi_hours = tax.skills["data_visualization_powerbi"].hours
    expected_weight = 0.3 * ((tableau_hours + powerbi_hours) / 2.0)

    above = [
        (u, v, data)
        for u, v, data in g.nx.edges(data=True)
        if data["kind"] == "adjacency"
        and {u, v} == {"data_visualization_tableau", "data_visualization_powerbi"}
    ]
    assert len(above) == 2, "expected an adjacency edge in both directions (cosine 0.85 >= 0.75)"
    for _, _, data in above:
        assert round(data["weight"], 6) == round(expected_weight, 6)

    below = [
        (u, v, data)
        for u, v, data in g.nx.edges(data=True)
        if data["kind"] == "adjacency" and {u, v} == {"mobile_app_usage", "route_navigation_gps"}
    ]
    assert below == [], "cosine 0.30 < 0.75 must not produce an adjacency edge"


def test_transferability_edge_iff_pmi_ge_1_and_count_ge_5_weight_hours_times_1_minus_min_pmi_over_3_0_5(
    skills_data, roles_data
):
    tax = taxonomy.load(skills_data, roles_data)
    pmi = {
        ("python_programming", "statistics_fundamentals"): (1.5, 5),  # qualifies
        ("sql_querying", "python_programming"): (0.9, 10),  # pmi below threshold
        ("cash_handling", "cash_reconciliation"): (2.0, 3),  # count below threshold
    }
    g = graph.build(tax, _all_embeddings(skills_data), pmi=pmi)

    qualifying = [
        (u, v, data)
        for u, v, data in g.nx.edges(data=True)
        if data["kind"] == "transferability" and (u, v) == ("python_programming", "statistics_fundamentals")
    ]
    assert len(qualifying) == 1
    expected_weight = tax.skills["statistics_fundamentals"].hours * (1 - min(1.5 / 3, 0.5))
    assert round(qualifying[0][2]["weight"], 6) == round(expected_weight, 6)

    non_qualifying = [
        (u, v, data)
        for u, v, data in g.nx.edges(data=True)
        if data["kind"] == "transferability"
        and (u, v) in {("sql_querying", "python_programming"), ("cash_handling", "cash_reconciliation")}
    ]
    assert non_qualifying == []


def test_edges_added_today_is_counted_not_hardcoded(skills_data, roles_data):
    tax = taxonomy.load(skills_data, roles_data)
    embeddings = _all_embeddings(skills_data)

    off = graph.build(tax, embeddings, pmi=None)
    assert off.edges_added_today == 0
    assert off.edges_added_today_reason == "transferability off"

    two_pairs = {
        ("python_programming", "statistics_fundamentals"): (1.5, 5),
        ("data_cleaning", "data_visualization_tableau"): (1.2, 6),
    }
    g_two = graph.build(tax, embeddings, pmi=two_pairs)
    assert g_two.edges_added_today == 2
    assert g_two.edges_added_today_reason is None

    three_pairs = dict(two_pairs)
    three_pairs[("customer_service_basic", "time_management")] = (2.5, 8)
    g_three = graph.build(tax, embeddings, pmi=three_pairs)
    assert g_three.edges_added_today == 3, "count must track the real input, not a hardcoded number"


def test_graph_build_is_deterministic_under_permuted_input(skills_data, roles_data):
    tax_a = taxonomy.load(skills_data, roles_data)

    shuffled_skills = list(skills_data)
    shuffled_roles = list(roles_data)
    random.Random(42).shuffle(shuffled_skills)
    random.Random(7).shuffle(shuffled_roles)
    tax_b = taxonomy.load(shuffled_skills, shuffled_roles)

    embeddings_a = _all_embeddings(skills_data)
    embeddings_b = dict(reversed(list(embeddings_a.items())))

    pmi = {
        ("python_programming", "statistics_fundamentals"): (1.5, 5),
        ("data_cleaning", "data_visualization_tableau"): (1.2, 6),
    }
    pmi_b = dict(reversed(list(pmi.items())))

    g_a = graph.build(tax_a, embeddings_a, pmi=pmi)
    g_b = graph.build(tax_b, embeddings_b, pmi=pmi_b)

    assert _edge_set(g_a) == _edge_set(g_b)
    assert g_a.edges_added_today == g_b.edges_added_today
