from datetime import timedelta

from app.clock import today
from app.config import get_settings
from app.models import Recurrence
from tests.conftest import JPEG, PNG


def make_plant(client):
    return client.post("/api/plants", json={"name": "Ficus"}).json()


def stored_files():
    return sorted(p for p in get_settings().photos_dir.rglob("*") if p.is_file() and ".staging" not in p.parts)


def test_manual_entry(client):
    plant = make_plant(client)
    response = client.post(f"/api/plants/{plant['id']}/diary", data={"body": "Prime foglie nuove"})
    assert response.status_code == 201
    entry = response.json()
    assert entry["kind"] == "manual" and entry["body"] == "Prime foglie nuove" and entry["category"] is None


def test_manual_entry_with_category_and_past_date(client):
    plant = make_plant(client)
    entry = client.post(
        f"/api/plants/{plant['id']}/diary",
        data={"body": "Potatura di formazione", "category": "pruning", "occurred_at": "2025-05-01T10:00:00+02:00"},
    ).json()
    assert entry["category"] == "pruning"
    assert entry["occurred_at"].startswith("2025-05-01T08:00:00")


def test_empty_entry_is_rejected(client):
    plant = make_plant(client)
    assert client.post(f"/api/plants/{plant['id']}/diary", data={"body": "  "}).status_code == 422


def test_entry_with_multiple_photos(client):
    plant = make_plant(client)
    entry = client.post(
        f"/api/plants/{plant['id']}/diary",
        data={"body": "Foto"},
        files=[("files", ("../../etc/passwd.jpg", JPEG, "image/jpeg")), ("files", ("b.png", PNG, "image/png"))],
    ).json()
    assert [photo["mime_type"] for photo in entry["photos"]] == ["image/jpeg", "image/png"]
    files = stored_files()
    assert len(files) == 2
    assert all("passwd" not in file.name for file in files)

    download = client.get(entry["photos"][0]["url"])
    assert download.status_code == 200
    assert download.headers["content-type"] == "image/jpeg"
    assert download.content == JPEG


def test_unsupported_file_is_rejected(client):
    plant = make_plant(client)
    response = client.post(
        f"/api/plants/{plant['id']}/diary",
        data={"body": "x"},
        files=[("files", ("finta.jpg", b"<html>no</html>", "image/jpeg"))],
    )
    assert response.status_code == 422
    assert "JPEG" in response.json()["detail"]
    assert client.get(f"/api/plants/{plant['id']}/diary").json()["items"] == []
    assert stored_files() == []


def test_oversized_file_is_rejected(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "photo_max_mb", 0)
    plant = make_plant(client)
    response = client.post(
        f"/api/plants/{plant['id']}/diary", files=[("files", ("a.jpg", JPEG, "image/jpeg"))]
    )
    assert response.status_code == 422
    assert stored_files() == []


def test_photo_limit_per_entry(client):
    plant = make_plant(client)
    files = [("files", (f"{i}.jpg", JPEG, "image/jpeg")) for i in range(11)]
    assert client.post(f"/api/plants/{plant['id']}/diary", files=files).status_code == 422


def test_delete_single_photo_removes_file(client):
    plant = make_plant(client)
    entry = client.post(
        f"/api/plants/{plant['id']}/diary",
        data={"body": "Due foto"},
        files=[("files", ("a.jpg", JPEG, "image/jpeg")), ("files", ("b.jpg", JPEG, "image/jpeg"))],
    ).json()
    assert client.delete(f"/api/photos/{entry['photos'][0]['id']}").status_code == 204
    assert len(stored_files()) == 1
    items = client.get(f"/api/plants/{plant['id']}/diary").json()["items"]
    assert len(items[0]["photos"]) == 1


def test_delete_manual_entry_removes_photos(client):
    plant = make_plant(client)
    entry = client.post(
        f"/api/plants/{plant['id']}/diary", files=[("files", ("a.jpg", JPEG, "image/jpeg"))]
    ).json()
    assert client.delete(f"/api/diary/{entry['id']}").status_code == 204
    assert stored_files() == []


def test_completion_event_in_diary_with_note_and_photos(client):
    plant = make_plant(client)
    task = client.post(
        f"/api/plants/{plant['id']}/tasks",
        json={"name": "Concimazione", "task_type": "fertilizing", "recurrence": Recurrence.ONCE, "start_date": str(today())},
    ).json()
    occurrence_id = task["pending"][0]["id"]
    result = client.post(f"/api/occurrences/{occurrence_id}/complete").json()
    entry_id = result["diary_entry_id"]

    client.patch(f"/api/diary/{entry_id}", json={"body": "Concime organico"})
    client.post(f"/api/diary/{entry_id}/photos", files=[("files", ("a.jpg", JPEG, "image/jpeg"))])

    items = client.get(f"/api/plants/{plant['id']}/diary").json()["items"]
    assert len(items) == 1
    event = items[0]
    assert event["kind"] == "task_completion"
    assert event["title"] == "Concimazione"
    assert event["body"] == "Concime organico"
    assert event["occurrence_id"] == occurrence_id
    assert len(event["photos"]) == 1
    assert client.delete(f"/api/diary/{entry_id}").status_code == 409

    client.post(f"/api/occurrences/{occurrence_id}/reopen")
    assert client.get(f"/api/plants/{plant['id']}/diary").json()["items"] == []
    assert stored_files() == []


def test_diary_order_and_pagination(client):
    plant = make_plant(client)
    for day in (3, 1, 2):
        client.post(
            f"/api/plants/{plant['id']}/diary",
            data={"body": f"giorno {day}", "occurred_at": f"2026-01-0{day}T10:00:00+01:00"},
        )
    page = client.get(f"/api/plants/{plant['id']}/diary", params={"limit": 2}).json()
    assert [item["body"] for item in page["items"]] == ["giorno 3", "giorno 2"]
    assert page["has_more"]
    rest = client.get(f"/api/plants/{plant['id']}/diary", params={"limit": 2, "offset": 2}).json()
    assert [item["body"] for item in rest["items"]] == ["giorno 1"] and not rest["has_more"]


def test_measurement_in_mm_and_cm(client):
    plant = make_plant(client)
    mm = client.post(
        f"/api/plants/{plant['id']}/measurements",
        json={"kind": "height", "measured_on": str(today()), "value": "312.5"},
    ).json()
    assert mm["value_mm"] == "312.50" and mm["input_unit"] == "mm"
    cm = client.post(
        f"/api/plants/{plant['id']}/measurements",
        json={"kind": "trunk_diameter", "measured_on": str(today()), "value": "4.2", "unit": "cm"},
    ).json()
    assert cm["value_mm"] == "42.00"


def test_measurement_with_past_date_and_future_rejected(client):
    plant = make_plant(client)
    past = str(today() - timedelta(days=40))
    response = client.post(
        f"/api/plants/{plant['id']}/measurements", json={"kind": "width", "measured_on": past, "value": "100"}
    )
    assert response.status_code == 201
    future = str(today() + timedelta(days=1))
    assert client.post(
        f"/api/plants/{plant['id']}/measurements", json={"kind": "width", "measured_on": future, "value": "100"}
    ).status_code == 422
    assert client.post(
        f"/api/plants/{plant['id']}/measurements", json={"kind": "width", "measured_on": past, "value": "-1"}
    ).status_code == 422


def test_measurement_update_delete_and_diary_link(client):
    plant = make_plant(client)
    created = client.post(
        f"/api/plants/{plant['id']}/measurements",
        json={"kind": "height", "measured_on": str(today()), "value": "200"},
    ).json()
    diary = client.get(f"/api/plants/{plant['id']}/diary").json()["items"]
    assert diary[0]["kind"] == "measurement" and diary[0]["measurement"]["id"] == created["id"]

    past = today() - timedelta(days=10)
    updated = client.put(
        f"/api/measurements/{created['id']}", json={"kind": "height", "measured_on": str(past), "value": "210"}
    ).json()
    assert updated["value_mm"] == "210.00"
    diary = client.get(f"/api/plants/{plant['id']}/diary").json()["items"]
    assert diary[0]["measurement"]["value_mm"] == "210.00"
    assert diary[0]["occurred_at"].startswith(str(past)) or diary[0]["occurred_at"][:10] == str(past)

    assert client.delete(f"/api/measurements/{created['id']}").status_code == 204
    assert client.get(f"/api/plants/{plant['id']}/diary").json()["items"] == []


def test_measurements_are_sorted_and_chart_data(client):
    plant = make_plant(client)
    base = today()
    for offset, value in ((400, "100"), (200, "150"), (20, "180"), (5, "190"), (5, "195")):
        client.post(
            f"/api/plants/{plant['id']}/measurements",
            json={"kind": "height", "measured_on": str(base - timedelta(days=offset)), "value": value},
        )
    client.post(
        f"/api/plants/{plant['id']}/measurements",
        json={"kind": "width", "measured_on": str(base), "value": "90"},
    )
    listed = client.get(f"/api/plants/{plant['id']}/measurements").json()
    dates = [item["measured_on"] for item in listed]
    assert dates == sorted(dates, reverse=True)

    full = client.get(f"/api/plants/{plant['id']}/measurements/charts", params={"range": "all"}).json()
    heights = full["series"]["height"]
    assert [point["value_mm"] for point in heights] == ["100.00", "150.00", "180.00", "195.00"]
    assert full["series"]["trunk_diameter"] == []
    assert len(full["series"]["width"]) == 1

    year = client.get(f"/api/plants/{plant['id']}/measurements/charts", params={"range": "year"}).json()
    assert [point["value_mm"] for point in year["series"]["height"]] == ["150.00", "180.00", "195.00"]
    month = client.get(f"/api/plants/{plant['id']}/measurements/charts", params={"range": "month"}).json()
    assert [point["value_mm"] for point in month["series"]["height"]] == ["180.00", "195.00"]
