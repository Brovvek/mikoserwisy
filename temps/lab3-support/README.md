# Pakiet pomocniczy LAB3

Pakiet zawiera lokalny Eureka Server, minimalny przykład dwóch usług FastAPI oraz testy komunikacji z zamiennikiem klienta. Przykład ilustruje integrację; nie stanowi gotowego projektu semestralnego. Należy rozpakować go obok własnego projektu. Rekord paczkomatu zachowuje pola `id`, `name`, `address`, `city`, `status` z LAB1. Demo używa stałych danych; we własnym projekcie należy zachować bazę i cache z LAB2.

## Wymagania

- Docker Desktop z `docker compose` albo JDK 21 i Maven do lokalnego uruchomienia serwera,
- Python 3.12 lub nowszy,
- wolne porty `8761`, `8101` i `8102`.

Każda osoba uruchamia rejestr na swoim komputerze. Docker nie jest obowiązkowy: rejestr można uruchomić przez JDK 21 i Maven. Należy wybrać jeden wariant. Polecenia są przeznaczone dla PowerShella; usługi Python działają lokalnie w obu wariantach.

## Uruchomienie rejestru Eureka

W katalogu pakietu należy uruchomić:

```powershell
docker compose up --build -d eureka
```

Przy pierwszym uruchomieniu obraz serwera jest budowany lokalnie, a Maven pobiera zależności. Panel znajduje się pod adresem `http://localhost:8761/`. Kontener nie uruchamia usług przykładowych.

Alternatywnie, z katalogu pakietu należy uruchomić serwer przez Maven:

```powershell
Set-Location .\eureka-server
mvn spring-boot:run
```

Maven pobierze zależności przy pierwszym uruchomieniu. Proces można zatrzymać skrótem `Ctrl+C`. Należy wybrać uruchomienie przez Docker Compose albo Maven.

## Uruchomienie dwóch usług

Środowisko Python należy utworzyć, a zależności zainstalować z katalogu pakietu:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

W pierwszym terminalu należy uruchomić `LOCKER-SERVICE`:

```powershell
$env:EUREKA_SERVER_URL = 'http://127.0.0.1:8761'
$env:SERVICE_NAME = 'LOCKER-SERVICE'
$env:SERVICE_PORT = '8101'
.\.venv\Scripts\python.exe -m uvicorn demo.locker_service.app.main:app --port 8101
```

W drugim terminalu należy uruchomić `PARCEL-SERVICE`:

```powershell
$env:EUREKA_SERVER_URL = 'http://127.0.0.1:8761'
$env:SERVICE_NAME = 'PARCEL-SERVICE'
$env:SERVICE_PORT = '8102'
.\.venv\Scripts\python.exe -m uvicorn demo.parcel_service.app.main:app --port 8102
```

Po pojawieniu się obu wpisów `UP` w panelu należy wykonać:

```powershell
Invoke-RestMethod http://127.0.0.1:8102/delivery-check/KRK-1024
```

Oba terminale należy otworzyć w katalogu pakietu. Należy wcześniej zatrzymać własne aplikacje zajmujące porty `8101` i `8102`. Zmienne trzeba ustawić osobno dla każdego procesu; na czas eksperymentu należy pracować bez `--reload`.

`PARCEL-SERVICE` wybiera adres `LOCKER-SERVICE` z lokalnej, okresowo odświeżanej kopii rejestru i wywołuje `GET /lockers/KRK-1024`. Oczekiwana odpowiedź ma status `200`, pole `destination` równe `KRK-1024` oraz `locker.id` równe `KRK-1024`. Eureka nie przekazuje danych paczkomatu.

Kod HTTP `404` dla `GET /delivery-check/UNKNOWN` oznacza brak paczkomatu. Inny błąd HTTP zależności jest mapowany na `502`, a brak połączenia lub timeout na `503`. Limit pojedynczego wywołania HTTP wynosi 3 sekundy. Przy kilku instancjach nie jest to limit czasu całego przepływu.

Należy sprawdzić odpowiedzi przez `curl.exe -i http://127.0.0.1:8102/delivery-check/UNKNOWN` albo dokumentację `/docs`. Po zatrzymaniu `LOCKER-SERVICE` żądanie znanego paczkomatu powinno dać `503`, a `http://127.0.0.1:8102/health` nadal `200`. Po przywróceniu zależności i odświeżeniu rejestru klienta należy ponownie oczekiwać `200` z danymi. Wpis `UP` nie gwarantuje dostępności procesu; aktualizacja rejestru i jego lokalnej kopii nie jest natychmiastowa.

## Testy jednostkowe

Testy nie wymagają działającego serwera Eureka:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Testy sprawdzają wywołanie po nazwie, przekazanie limitu czasu, zachowanie kontraktu paczkomatu, cykl życia klienta oraz odpowiedzi `404`, `502` i `503`. Atrapa nie potwierdza rzeczywistej rejestracji; należy osobno wykonać scenariusze ręczne z instrukcji głównej.

## Zatrzymanie

Oba procesy Uvicorna należy zatrzymać skrótem `Ctrl+C`. Serwer Eureka należy zatrzymać w zależności od wybranej metody:

```powershell
docker compose down
```

Jeśli Eureka działa przez Maven, proces należy zakończyć skrótem `Ctrl+C` w terminalu, w którym uruchomiono `mvn spring-boot:run`.

Adresy i porty można zmieniać przez zmienne środowiskowe, ale port klienta rejestrowany w Eurece musi odpowiadać portowi Uvicorna. `SERVICE_PORT` w przykładzie jest używany przez klienta rejestru; parametr `--port` uruchamia serwer HTTP.
