import pytest

from src.replenishment import inventory_position, portfolio_sensitivity, simulate_replenishment


def test_replenishment_formula_uses_forecast_plus_safety_stock():
    result = simulate_replenishment([10, 10, 10], residual_sigma=0, lead_time_days=3, service_level=0.95, on_hand_inventory=12)
    assert result["lead_time_demand"] == pytest.approx(30)
    assert result["safety_stock"] == pytest.approx(0)
    assert result["reorder_point"] == pytest.approx(30)
    assert result["recommended_order_qty"] == pytest.approx(18)


def test_replenishment_rejects_invalid_service_level():
    with pytest.raises(ValueError):
        simulate_replenishment([1], 1, 7, 1.0, 0)


def test_portfolio_sensitivity_counts_skus_with_a_theoretical_shortfall():
    result = portfolio_sensitivity({"A": ([10], 0), "B": ([1], 0)}, on_hand_inventory=5,
                                   lead_times=[1], service_levels=[0.95],
                                   holding_cost_per_unit=1, stockout_cost_per_unit=2)
    assert result[0]["high_risk_sku_count"] == 1
    assert result[0]["total_recommended_order_qty"] == pytest.approx(5)


def test_inventory_position_and_supply_constraints_are_applied():
    assert inventory_position(10, inbound_inventory=5, reserved_inventory=4, backorder_qty=3) == pytest.approx(8)
    result = simulate_replenishment(
        [10, 10], residual_sigma=0, lead_time_days=2, service_level=0.95, on_hand_inventory=8,
        min_order_qty=20, pack_size=6,
    )
    assert result["unconstrained_order_qty"] == pytest.approx(12)
    assert result["recommended_order_qty"] == pytest.approx(24)


def test_lead_time_variability_increases_safety_stock():
    stable = simulate_replenishment([10, 10, 10], 2, 3, 0.95, on_hand_inventory=0, lead_time_std_days=0)
    variable = simulate_replenishment([10, 10, 10], 2, 3, 0.95, on_hand_inventory=0, lead_time_std_days=2)
    assert variable["safety_stock"] > stable["safety_stock"]
