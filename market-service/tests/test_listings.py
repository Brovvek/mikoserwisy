import pytest
from fastapi.testclient import TestClient

from app.main import create_app

# Każdy test zaczyna od danych początkowych:
# 1 — otomoto, BMW Seria 3, 104 900 PLN, ostatnia obserwacja 2026-10-20 08:00 UTC;
# 2 — autoscout24_de, BMW Seria 3, 22 400 EUR; 3 — autobazar_eu, Skoda Octavia, 15 900 EUR.


def listing_payload(**changes):
    """Poprawna, nowa oferta z otomoto."""
    payload = {
        "source": "otomoto",
        "external_id": "6123456790",
        "country": "PL",
        "url": "https://www.otomoto.pl/osobowe/oferta/bmw-seria-3-ID6123456790.html",
        "title": "BMW Seria 3 320i Sport Line",
        "make": "BMW",
        "model": "Seria 3",
        "year": 2021,
        "mileage_km": 45000,
        "fuel": "petrol",
        "price_amount": 129900,
        "currency": "PLN",
        "observed_at": "2026-10-21T08:00:00Z",
    }
    return payload | changes


def listing_ids(client, **params):
    response = client.get("/listings", params=params)
    assert response.status_code == 200
    return [listing["id"] for listing in response.json()]


def test_list_and_details_return_initial_listings(client):
    assert listing_ids(client) == [1, 2, 3]

    response = client.get("/listings/1")

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "source": "otomoto",
        "external_id": "6123456789",
        "country": "PL",
        "url": "https://www.otomoto.pl/osobowe/oferta/bmw-seria-3-ID6123456789.html",
        "title": "BMW Seria 3 320d xDrive M Sport",
        "make": "BMW",
        "model": "Seria 3",
        "year": 2019,
        "mileage_km": 98500,
        "fuel": "diesel",
        "price_amount": 104900,
        "currency": "PLN",
        "first_seen_at": "2026-10-20T08:00:00Z",
        "last_seen_at": "2026-10-20T08:00:00Z",
        "price_history": [{"at": "2026-10-20T08:00:00Z", "amount": 104900}],
    }


def test_filtered_list_may_be_empty(client):
    assert listing_ids(client, make="BMW", model="Seria 3") == [1, 2]
    assert listing_ids(client, country="SK") == [3]
    assert listing_ids(client, make="Audi") == []


def test_unknown_listing_returns_404(client):
    response = client.get("/listings/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Listing 999 not found"}

    response = client.patch(
        "/listings/999", json={"observed_at": "2026-10-22T08:00:00Z", "price_amount": 99900}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Listing 999 not found"}


def test_non_numeric_listing_id_returns_422(client):
    response = client.get("/listings/abc")

    assert response.status_code == 422
    assert [error["loc"] for error in response.json()["detail"]] == [["path", "listing_id"]]


def test_create_then_read(client):
    response = client.post("/listings", json=listing_payload())

    assert response.status_code == 201
    created = response.json()
    sent = {key: value for key, value in listing_payload().items() if key != "observed_at"}
    assert created == {
        "id": 4,
        **sent,
        "first_seen_at": "2026-10-21T08:00:00Z",
        "last_seen_at": "2026-10-21T08:00:00Z",
        "price_history": [{"at": "2026-10-21T08:00:00Z", "amount": 129900}],
    }

    response = client.get("/listings/4")
    assert response.status_code == 200
    assert response.json() == created
    assert listing_ids(client) == [1, 2, 3, 4]


@pytest.mark.parametrize(
    ("changes", "invalid_field"),
    [
        ({"year": 1949}, "year"),
        ({"mileage_km": -1}, "mileage_km"),
        ({"price_amount": 0}, "price_amount"),
        ({"country": "pl"}, "country"),
        ({"currency": "zł"}, "currency"),
        ({"fuel": "gas"}, "fuel"),
        ({"url": "otomoto.pl/oferta"}, "url"),
        ({"title": "   "}, "title"),  # po obcięciu spacji pusty tekst
        ({"observed_at": "2026-10-21T08:00:00"}, "observed_at"),  # czas bez strefy
    ],
)
def test_invalid_listing_returns_422_and_does_not_change_state(client, changes, invalid_field):
    before = client.get("/listings").json()

    response = client.post("/listings", json=listing_payload(**changes))

    assert response.status_code == 422
    assert [error["loc"] for error in response.json()["detail"]] == [["body", invalid_field]]
    assert client.get("/listings").json() == before


def test_unknown_fields_are_ignored(client):
    # Klient nie nada identyfikatora, a dane spoza kontraktu (np. telefon sprzedawcy) nie są zapisywane.
    response = client.post(
        "/listings", json=listing_payload(id=77, seller_phone="+48 600 000 000")
    )

    assert response.status_code == 201
    assert response.json()["id"] == 4
    assert "seller_phone" not in client.get("/listings/4").json()


def test_duplicate_listing_returns_409_and_does_not_change_state(client):
    before = client.get("/listings").json()

    # Ta sama oferta portalu co oferta 1 (otomoto/6123456789), tylko z inną ceną.
    response = client.post(
        "/listings", json=listing_payload(external_id="6123456789", price_amount=101900)
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Listing otomoto/6123456789 already exists (listing 1)"}
    assert client.get("/listings").json() == before
    # Odrzucony zapis nie zużył numeru: kolejna nowa oferta dostaje id 4.
    assert client.post("/listings", json=listing_payload()).json()["id"] == 4


def test_same_external_id_in_another_source_is_another_listing(client):
    response = client.post(
        "/listings",
        json=listing_payload(
            source="autobazar_eu", external_id="6123456789", country="SK", currency="EUR"
        ),
    )

    assert response.status_code == 201
    assert response.json()["id"] == 4


def test_newer_observation_updates_price_and_history(client):
    response = client.patch(
        "/listings/1",
        json={"observed_at": "2026-10-22T08:00:00Z", "price_amount": 99900, "mileage_km": 98700},
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["price_amount"] == 99900
    assert updated["mileage_km"] == 98700
    assert updated["first_seen_at"] == "2026-10-20T08:00:00Z"
    assert updated["last_seen_at"] == "2026-10-22T08:00:00Z"
    assert updated["price_history"] == [
        {"at": "2026-10-20T08:00:00Z", "amount": 104900},
        {"at": "2026-10-22T08:00:00Z", "amount": 99900},
    ]
    assert client.get("/listings/1").json() == updated


def test_newer_observation_with_the_same_price_keeps_history(client):
    response = client.patch(
        "/listings/1", json={"observed_at": "2026-10-22T08:00:00Z", "price_amount": 104900}
    )

    assert response.status_code == 200
    listing = client.get("/listings/1").json()
    assert listing["last_seen_at"] == "2026-10-22T08:00:00Z"
    assert listing["mileage_km"] == 98500  # obserwacja bez przebiegu nie zmienia go
    assert listing["price_history"] == [{"at": "2026-10-20T08:00:00Z", "amount": 104900}]


def test_older_observation_returns_409_and_does_not_change_state(client):
    before = client.get("/listings/1").json()

    # Ostatnia obserwacja oferty 1 jest z 2026-10-20, a ta — o dzień starsza.
    response = client.patch(
        "/listings/1", json={"observed_at": "2026-10-19T08:00:00Z", "price_amount": 109900}
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Observation from 2026-10-19T08:00:00+00:00 is not newer than "
        "the last observation of listing 1 (2026-10-20T08:00:00+00:00)"
    }
    assert client.get("/listings/1").json() == before


def test_repeated_last_observation_changes_nothing(client):
    observation = {"observed_at": "2026-10-22T08:00:00Z", "price_amount": 99900}
    assert client.patch("/listings/1", json=observation).status_code == 200
    before = client.get("/listings/1").json()

    # Ponowione żądanie, np. po przekroczeniu czasu odpowiedzi, jest dozwolone i niczego nie zmienia.
    response = client.patch("/listings/1", json=observation)
    assert response.status_code == 200
    assert response.json() == before

    # Ta sama chwila, ale inna cena — sprzeczne dane.
    response = client.patch("/listings/1", json=observation | {"price_amount": 98900})
    assert response.status_code == 409
    assert client.get("/listings/1").json() == before


@pytest.mark.parametrize(
    ("observation", "invalid_field"),
    [
        ({"observed_at": "2026-10-22T08:00:00", "price_amount": 99900}, "observed_at"),
        ({"observed_at": "2026-10-22T08:00:00Z", "price_amount": 0}, "price_amount"),
        ({"observed_at": "2026-10-22T08:00:00Z", "price_amount": 99900, "mileage_km": -5}, "mileage_km"),
        ({"price_amount": 99900}, "observed_at"),  # brak wymaganego pola
    ],
)
def test_invalid_observation_returns_422_and_does_not_change_state(
    client, observation, invalid_field
):
    before = client.get("/listings/1").json()

    response = client.patch("/listings/1", json=observation)

    assert response.status_code == 422
    assert [error["loc"] for error in response.json()["detail"]] == [["body", invalid_field]]
    assert client.get("/listings/1").json() == before


def test_each_application_has_its_own_store():
    with TestClient(create_app()) as first, TestClient(create_app()) as second:
        assert first.post("/listings", json=listing_payload()).status_code == 201

        assert first.get("/listings/4").status_code == 200
        assert second.get("/listings/4").status_code == 404
