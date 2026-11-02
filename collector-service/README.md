# Collector Service — LAB3

Druga usługa projektu **„agregator i analizator ogłoszeń samochodowych”**. Odpowiada na pytanie „skąd i kiedy pobierać”: zna portale ogłoszeniowe i ich stan oraz decyduje, czy ofertę można teraz ponownie pobrać. Ofert nie przechowuje — należą do [market-service](../market-service/README.md), które odnajduje w Eurece po nazwie `MARKET-SERVICE`.

Na tym etapie usługa ma mały, stały zestaw danych o portalach, bez bazy i bez pobierania stron. Plan dalszego rozwoju (segmenty, przebiegi, wysyłanie obserwacji, wzorowane na AutoRadar) opisuje README market-service.

Wspólną dokumentację LAB3 — granice usług, kontrakt, konfigurację, wyniki awarii, ograniczenia i źródła — zawiera [sekcja 9 README market-service](../market-service/README.md#9-lab3--rejestracja-i-odnajdywanie-usług).

```
collector-service/
├── app/
│   ├── main.py     # create_app(), lifespan, endpointy, reguła find_blocker, wywołanie MARKET-SERVICE
│   ├── models.py   # modele Pydantic: Source, ListingReference, RefreshCheck
│   └── eureka.py   # klient rejestru z konfiguracji środowiska (z paczki LAB3)
├── tests/
│   └── test_refresh_check.py  # testy z zamiennikiem klienta Eureki, bez sieci
├── requirements.txt
└── README.md
```

## API

| Metoda | Ścieżka | Opis | Kody |
|---|---|---|---|
| GET | `/health` | Czy proces działa | 200 |
| GET | `/sources` | Stan wszystkich portali | 200 |
| GET | `/sources/{source_id}` | Stan jednego portalu | 200, 404 |
| GET | `/refresh-check/{listing_id}` | Czy ofertę można teraz ponownie pobrać | 200, 404, 422, 502, 503 |

Dokumentacja: [Swagger UI](http://localhost:8102/docs).

## Uruchomienie i testy

Wymagania: Python 3.12 lub nowszy (sprawdzono na 3.14.0). Testy nie wymagają Eureki. Do działania `refresh-check` potrzebne są Eureka Server i market-service. Terminal otwórz w katalogu `collector-service`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q

$env:EUREKA_SERVER_URL = 'http://127.0.0.1:8761'
$env:SERVICE_NAME = 'COLLECTOR-SERVICE'
$env:SERVICE_PORT = '8102'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8102
```

`SERVICE_PORT` i `--port` muszą być równe. `INSTANCE_IP` i `INSTANCE_HOST` mają domyślnie wartości `127.0.0.1` i `localhost`. Serwer zatrzymuje się przez `Ctrl+C`.
