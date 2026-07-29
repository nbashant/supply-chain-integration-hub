from fastapi.testclient import TestClient


def _create_reference_data(client: TestClient) -> tuple[str, str, str]:
    supplier_response = client.post(
        "/api/v1/suppliers",
        json={"code": "supplier_a", "name": "Supplier A"},
    )
    assert supplier_response.status_code == 201

    product_response = client.post(
        "/api/v1/products",
        json={
            "sku": "ip16-256-blk",
            "name": "Example Phone 256 GB - Black",
            "base_unit": "EACH",
        },
    )
    assert product_response.status_code == 201

    warehouse_response = client.post(
        "/api/v1/warehouses",
        json={
            "code": "lax-01",
            "name": "Los Angeles Distribution Center",
            "timezone": "America/Los_Angeles",
        },
    )
    assert warehouse_response.status_code == 201

    return (
        supplier_response.json()["id"],
        product_response.json()["id"],
        warehouse_response.json()["id"],
    )


def test_complete_phase_one_vertical_slice(client: TestClient) -> None:
    supplier_id, product_id, warehouse_id = _create_reference_data(client)

    duplicate_supplier = client.post(
        "/api/v1/suppliers",
        json={"code": "SUPPLIER_A", "name": "Duplicate"},
    )
    assert duplicate_supplier.status_code == 409

    inventory_response = client.put(
        f"/api/v1/inventory/{warehouse_id}/{product_id}",
        json={
            "on_hand_quantity": "120.000",
            "reserved_quantity": "35.000",
        },
    )
    assert inventory_response.status_code == 200
    inventory = inventory_response.json()
    assert inventory["available_quantity"] == "85.000"
    assert inventory["version"] == 1

    updated_inventory_response = client.put(
        f"/api/v1/inventory/{warehouse_id}/{product_id}",
        json={
            "on_hand_quantity": "130.000",
            "reserved_quantity": "40.000",
        },
    )
    assert updated_inventory_response.status_code == 200
    assert updated_inventory_response.json()["version"] == 2

    purchase_order_response = client.post(
        "/api/v1/purchase-orders",
        json={
            "supplier_id": supplier_id,
            "external_reference": "PO-2026-0001",
            "expected_date": "2026-08-15",
            "lines": [
                {
                    "product_id": product_id,
                    "ordered_quantity": "250.000",
                }
            ],
        },
    )
    assert purchase_order_response.status_code == 201
    purchase_order = purchase_order_response.json()
    assert purchase_order["status"] == "submitted"
    assert purchase_order["lines"][0]["line_number"] == 1

    shipment_response = client.post(
        "/api/v1/shipments",
        json={
            "supplier_id": supplier_id,
            "purchase_order_id": purchase_order["id"],
            "tracking_reference": "TRACK-0001",
        },
    )
    assert shipment_response.status_code == 201
    shipment = shipment_response.json()
    shipment_id = shipment["id"]
    assert shipment["status"] == "planned"
    assert shipment["events"] == []

    invalid_event_response = client.post(
        f"/api/v1/shipments/{shipment_id}/events",
        json={
            "external_event_id": "C-EVT-INVALID",
            "event_type": "delivered",
            "occurred_at": "2026-07-29T20:00:00Z",
        },
    )
    assert invalid_event_response.status_code == 422
    assert invalid_event_response.json()["error"]["code"] == ("domain_validation_error")

    events = [
        ("C-EVT-0001", "picked_up", "2026-07-29T20:00:00Z"),
        ("C-EVT-0002", "in_transit", "2026-07-30T08:00:00Z"),
        ("C-EVT-0003", "delivered", "2026-08-01T18:00:00Z"),
    ]
    for expected_event_count, (
        external_event_id,
        event_type,
        occurred_at,
    ) in enumerate(events, start=1):
        event_response = client.post(
            f"/api/v1/shipments/{shipment_id}/events",
            json={
                "external_event_id": external_event_id,
                "event_type": event_type,
                "occurred_at": occurred_at,
            },
        )
        assert event_response.status_code == 201
        assert len(event_response.json()["events"]) == expected_event_count

    delivered_shipment = client.get(f"/api/v1/shipments/{shipment_id}")
    assert delivered_shipment.status_code == 200
    delivered = delivered_shipment.json()
    assert delivered["status"] == "delivered"
    assert delivered["shipped_at"] == "2026-07-29T20:00:00Z"
    assert delivered["delivered_at"] == "2026-08-01T18:00:00Z"
    assert len(delivered["events"]) == 3

    duplicate_event = client.post(
        f"/api/v1/shipments/{shipment_id}/events",
        json={
            "external_event_id": "C-EVT-0003",
            "event_type": "delivered",
            "occurred_at": "2026-08-01T18:00:00Z",
        },
    )
    assert duplicate_event.status_code == 409


def test_health_endpoints(client: TestClient) -> None:
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/health/ready").json() == {
        "status": "ready",
        "database": "available",
        "redis": "available",
        "object_storage": "available",
    }
