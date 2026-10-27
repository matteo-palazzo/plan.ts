from app.clock import today

from app.config import get_settings
from app.models import Recurrence
from tests.conftest import JPEG


def create_plant(client, **values):
    response = client.post("/api/plants", json={"name": "Acero"} | values)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_with_name_only(client):
    plant = create_plant(client)
    assert plant["name"] == "Acero"
    assert plant["status"] == "active"
    assert plant["species"] is None and plant["group"] is None and plant["tags"] == []
    assert plant["created_at"] and plant["updated_at"]


def test_name_is_required(client):
    response = client.post("/api/plants", json={"name": "   "})
    assert response.status_code == 422
    assert response.json()["detail"] == "Campo obbligatorio"


def test_update_optional_fields(client):
    plant = create_plant(client)
    payload = {
        "name": "Acero tridente",
        "common_name": "Acero",
        "species": "Acer buergerianum",
        "acquired_on": "2021-04-10",
        "substrate": "Akadama 70%, pomice 30%",
        "location": "Balcone sud",
        "pot": "Tokoname 25 cm",
        "style": "Moyogi",
        "notes": "Teme il sole pomeridiano",
        "tag_ids": [],
    }
    response = client.put(f"/api/plants/{plant['id']}", json=payload)
    assert response.status_code == 200
    body = response.json()
    for key, value in payload.items():
        if key != "tag_ids":
            assert body[key] == value

    cleared = client.put(f"/api/plants/{plant['id']}", json={"name": "Acero tridente", "species": ""}).json()
    assert cleared["species"] is None and cleared["notes"] is None


def test_group_and_multiple_tags(client):
    group = client.post("/api/groups", json={"name": "Balcone sud"}).json()
    bonsai = client.post("/api/tags", json={"name": "Bonsai", "color": "#2f855a"}).json()
    conifer = client.post("/api/tags", json={"name": "Conifera"}).json()
    plant = create_plant(client, group_id=group["id"], tag_ids=[bonsai["id"], conifer["id"], bonsai["id"]])
    assert plant["group"]["name"] == "Balcone sud"
    assert [tag["name"] for tag in plant["tags"]] == ["Bonsai", "Conifera"]

    groups = client.get("/api/groups").json()
    assert groups[0]["plant_count"] == 1

    client.delete(f"/api/tags/{conifer['id']}")
    assert [tag["name"] for tag in client.get(f"/api/plants/{plant['id']}").json()["tags"]] == ["Bonsai"]

    client.delete(f"/api/groups/{group['id']}")
    assert client.get(f"/api/plants/{plant['id']}").json()["group"] is None


def test_duplicate_tag_name_conflicts(client):
    client.post("/api/tags", json={"name": "Bonsai"})
    assert client.post("/api/tags", json={"name": "Bonsai"}).status_code == 409


def test_unknown_group_is_rejected(client):
    assert client.post("/api/plants", json={"name": "X", "group_id": 999}).status_code == 422


def test_search_by_name_species_group_and_tag(client):
    group = client.post("/api/groups", json={"name": "Serra"}).json()
    tag = client.post("/api/tags", json={"name": "Conifera"}).json()
    create_plant(client, name="Ginepro", species="Juniperus chinensis", tag_ids=[tag["id"]])
    create_plant(client, name="Ficus", group_id=group["id"])
    create_plant(client, name="Olivo")

    def names(q):
        return [plant["name"] for plant in client.get("/api/plants", params={"q": q}).json()]

    assert names("gine") == ["Ginepro"]
    assert names("juniperus") == ["Ginepro"]
    assert names("serra") == ["Ficus"]
    assert names("conif") == ["Ginepro"]
    assert names("%") == []


def test_archive_keeps_data_and_hides_from_lists(client):
    plant = create_plant(client)
    client.post(f"/api/plants/{plant['id']}/diary", data={"body": "Nuove gemme"})
    client.post(
        f"/api/plants/{plant['id']}/measurements",
        json={"kind": "height", "measured_on": str(today()), "value": "250"},
    )
    task = client.post(
        f"/api/plants/{plant['id']}/tasks",
        json={"name": "Innaffiare", "recurrence": Recurrence.ONCE, "start_date": str(today())},
    ).json()

    assert client.post(f"/api/plants/{plant['id']}/archive").json()["status"] == "archived"
    assert client.get("/api/plants").json() == []
    assert [p["id"] for p in client.get("/api/plants", params={"status": "archived"}).json()] == [plant["id"]]
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["due_today"] == [] and dashboard["overdue"] == []

    assert len(client.get(f"/api/plants/{plant['id']}/diary").json()["items"]) == 2
    assert len(client.get(f"/api/plants/{plant['id']}/measurements").json()) == 1
    assert client.get(f"/api/tasks/{task['id']}").status_code == 200

    assert client.post(f"/api/plants/{plant['id']}/restore").json()["status"] == "active"
    assert len(client.get("/api/dashboard").json()["due_today"]) == 1


def test_delete_requires_confirmation_and_removes_files(client):
    plant = create_plant(client)
    entry = client.post(
        f"/api/plants/{plant['id']}/diary", files=[("files", ("a.jpg", JPEG, "image/jpeg"))]
    ).json()
    photo_path = get_settings().photos_dir
    files_before = [p for p in photo_path.rglob("*") if p.is_file()]
    assert len(files_before) == 1

    assert client.delete(f"/api/plants/{plant['id']}", params={"confirm": "Sbagliato"}).status_code == 422
    assert client.delete(f"/api/plants/{plant['id']}", params={"confirm": "Acero"}).status_code == 204
    assert client.get(f"/api/plants/{plant['id']}").status_code == 404
    assert [p for p in photo_path.rglob("*") if p.is_file()] == []
    assert client.get(f"/api/photos/{entry['photos'][0]['id']}/file").status_code == 404
