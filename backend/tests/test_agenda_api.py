def make_plant(client, name="Ginepro"):
    return client.post("/api/plants", json={"name": name}).json()


def make_task(client, plant, **values):
    payload = {"name": "Innaffiare", "recurrence": "once", "start_date": "2026-03-10"} | values
    response = client.post(f"/api/plants/{plant['id']}/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_dashboard_buckets_and_order(client, at):
    at("2026-03-10 09:00")
    ginepro = make_plant(client)
    acero = make_plant(client, "Acero")
    make_task(client, ginepro, name="Oggi", start_date="2026-03-10")
    make_task(client, acero, name="Ritardo", start_date="2026-03-05")
    make_task(client, ginepro, name="Ritardo vecchio", start_date="2026-03-01")
    make_task(client, acero, name="Tra tre giorni", start_date="2026-03-13")
    make_task(client, acero, name="Troppo lontano", start_date="2026-03-30")

    body = client.get("/api/dashboard").json()
    assert body["today"] == "2026-03-10" and body["days"] == 7
    assert [item["task_name"] for item in body["overdue"]] == ["Ritardo vecchio", "Ritardo"]
    assert all(item["status"] == "overdue" for item in body["overdue"])
    assert [item["task_name"] for item in body["due_today"]] == ["Oggi"]
    assert body["due_today"][0]["plant_name"] == "Ginepro"
    assert [item["task_name"] for item in body["upcoming"]] == ["Tra tre giorni"]
    assert len(client.get("/api/dashboard", params={"days": 31}).json()["upcoming"]) == 2


def test_complete_and_skip_from_dashboard(client, at):
    at("2026-03-10 09:00")
    plant = make_plant(client)
    make_task(client, plant, name="A")
    make_task(client, plant, name="B")
    first, second = client.get("/api/dashboard").json()["due_today"]

    completed = client.post(f"/api/occurrences/{first['id']}/complete").json()
    assert completed["occurrence"]["status"] == "completed" and not completed["already_completed"]
    again = client.post(f"/api/occurrences/{first['id']}/complete").json()
    assert again["already_completed"] and again["diary_entry_id"] == completed["diary_entry_id"]

    assert client.post(f"/api/occurrences/{second['id']}/skip").json()["status"] == "skipped"
    assert client.post(f"/api/occurrences/{second['id']}/complete").status_code == 409
    assert client.get("/api/dashboard").json()["due_today"] == []


def test_suspended_task_hidden_and_resumed(client, at):
    at("2026-03-10 09:00")
    plant = make_plant(client)
    task = make_task(client, plant, recurrence="interval", interval_days=7)
    suspended = client.post(f"/api/tasks/{task['id']}/suspend", json={"days": 5}).json()
    assert suspended["is_suspended"] and suspended["suspended_until"] == "2026-03-15"
    assert client.get("/api/dashboard").json()["due_today"] == []

    resumed = client.post(f"/api/tasks/{task['id']}/resume").json()
    assert not resumed["is_suspended"]
    assert len(client.get("/api/dashboard").json()["due_today"]) == 1


def test_suspend_until_date_and_validation(client, at):
    at("2026-03-10 09:00")
    plant = make_plant(client)
    task = make_task(client, plant)
    assert client.post(f"/api/tasks/{task['id']}/suspend", json={"until": "2026-03-09"}).status_code == 422
    assert client.post(f"/api/tasks/{task['id']}/suspend", json={}).status_code == 422
    body = client.post(f"/api/tasks/{task['id']}/suspend", json={"until": "2026-04-01"}).json()
    assert body["suspended_until"] == "2026-04-01"
    at("2026-04-01 09:00")
    assert len(client.get("/api/dashboard").json()["due_today"]) == 1


def test_task_validation_messages(client, at):
    at("2026-03-10 09:00")
    plant = make_plant(client)
    response = client.post(
        f"/api/plants/{plant['id']}/tasks", json={"name": "X", "recurrence": "interval", "start_date": "2026-03-10"}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Indica ogni quanti giorni ripetere il task"
    response = client.post(
        f"/api/plants/{plant['id']}/tasks",
        json={"name": "X", "recurrence": "calendar", "start_date": "2026-03-10", "calendar_rule": {"kind": "weekly", "weekdays": [9]}},
    )
    assert response.status_code == 422


def test_task_edit_keeps_history(client, at):
    at("2026-03-02 09:00")
    plant = make_plant(client)
    task = make_task(
        client, plant, recurrence="calendar", calendar_rule={"kind": "weekly", "weekdays": [0]}, start_date="2026-03-02"
    )
    client.post(f"/api/occurrences/{task['pending'][0]['id']}/complete")
    at("2026-03-04 09:00")
    updated = client.put(
        f"/api/tasks/{task['id']}",
        json={
            "name": "Controllo parassiti",
            "recurrence": "calendar",
            "calendar_rule": {"kind": "weekly", "weekdays": [2]},
            "start_date": "2026-03-02",
        },
    ).json()
    assert updated["pending"][0]["due_date"] == "2026-03-04"
    history = client.get(f"/api/tasks/{task['id']}/history").json()
    assert [(item["due_date"], item["status"]) for item in history] == [("2026-03-02", "completed")]
    diary = client.get(f"/api/plants/{plant['id']}/diary").json()["items"]
    assert diary[0]["title"] == "Innaffiare"


def test_delete_task_keeps_diary(client, at):
    at("2026-03-10 09:00")
    plant = make_plant(client)
    task = make_task(client, plant)
    client.post(f"/api/occurrences/{task['pending'][0]['id']}/complete")
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 204
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404
    assert len(client.get(f"/api/plants/{plant['id']}/diary").json()["items"]) == 1


def test_disable_and_enable_task(client, at):
    at("2026-03-10 09:00")
    plant = make_plant(client)
    task = make_task(client, plant)
    assert client.post(f"/api/tasks/{task['id']}/active", json={"active": False}).json()["status"] == "disabled"
    assert client.get("/api/dashboard").json()["due_today"] == []
    assert client.post(f"/api/tasks/{task['id']}/active", json={"active": True}).json()["status"] == "active"
    assert len(client.get("/api/dashboard").json()["due_today"]) == 1


def test_calendar_includes_history_projection_and_filters(client, at):
    at("2026-03-01 09:00")
    group = client.post("/api/groups", json={"name": "Serra"}).json()
    tag = client.post("/api/tags", json={"name": "Bonsai"}).json()
    ginepro = client.post("/api/plants", json={"name": "Ginepro", "group_id": group["id"], "tag_ids": [tag["id"]]}).json()
    acero = make_plant(client, "Acero")
    weekly = make_task(
        client, ginepro, name="Innaffiare", task_type="watering", recurrence="calendar",
        calendar_rule={"kind": "weekly", "weekdays": [0]}, start_date="2026-03-01",
    )
    make_task(client, acero, name="Rinvaso", task_type="repotting", start_date="2026-03-03")
    client.post(f"/api/occurrences/{weekly['pending'][0]['id']}/complete")
    at("2026-03-12 09:00")

    items = client.get("/api/calendar", params={"start": "2026-03-01", "end": "2026-05-31"}).json()
    by_date = {(item["due_date"], item["task_name"]): item for item in items}
    assert by_date[("2026-03-02", "Innaffiare")]["status"] == "completed"
    assert by_date[("2026-03-09", "Innaffiare")]["status"] == "overdue"
    assert by_date[("2026-03-03", "Rinvaso")]["status"] == "overdue"
    assert by_date[("2026-03-16", "Innaffiare")]["status"] == "todo"
    assert by_date[("2026-05-25", "Innaffiare")]["status"] == "planned"
    assert by_date[("2026-05-25", "Innaffiare")]["id"] is None

    def names(**params):
        rows = client.get("/api/calendar", params={"start": "2026-03-01", "end": "2026-03-31"} | params).json()
        return {item["task_name"] for item in rows}

    assert names(plant_id=acero["id"]) == {"Rinvaso"}
    assert names(group_id=group["id"]) == {"Innaffiare"}
    assert names(tag_id=tag["id"]) == {"Innaffiare"}
    assert names(task_type="repotting") == {"Rinvaso"}
    completed = client.get(
        "/api/calendar", params={"start": "2026-03-01", "end": "2026-03-31", "status": ["completed"]}
    ).json()
    assert [item["due_date"] for item in completed] == ["2026-03-02"]
    assert client.get("/api/calendar", params={"start": "2026-01-01", "end": "2027-12-31"}).status_code == 422


def test_plant_tasks_show_overdue_and_next(client, at):
    at("2026-03-01 09:00")
    plant = make_plant(client)
    make_task(
        client, plant, recurrence="calendar", calendar_rule={"kind": "weekly", "weekdays": [0]}, start_date="2026-03-01"
    )
    at("2026-03-18 09:00")
    listed = client.get(f"/api/plants/{plant['id']}/tasks").json()
    pending = [(item["due_date"], item["status"]) for item in listed[0]["pending"]]
    assert pending == [
        ("2026-03-02", "overdue"),
        ("2026-03-09", "overdue"),
        ("2026-03-16", "overdue"),
        ("2026-03-23", "todo"),
    ]


def test_reopen_completion_from_api(client, at):
    at("2026-03-10 09:00")
    plant = make_plant(client)
    task = make_task(client, plant, recurrence="interval", interval_days=10)
    occurrence_id = task["pending"][0]["id"]
    client.post(f"/api/occurrences/{occurrence_id}/complete")
    assert client.get(f"/api/tasks/{task['id']}").json()["pending"][0]["due_date"] == "2026-03-20"
    reopened = client.post(f"/api/occurrences/{occurrence_id}/reopen").json()
    assert reopened["status"] == "todo"
    assert client.get(f"/api/tasks/{task['id']}").json()["pending"][0]["due_date"] == "2026-03-10"
