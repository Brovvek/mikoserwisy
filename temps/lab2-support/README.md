# Kod pomocniczy — LAB2

To uzupełnienie projektu z LAB1. Rozpakuj obok swojej usługi. Nie nadpisuj całej aplikacji. Przykład operuje na paczkomacie z tekstowym ID KRK-1024; pokazuje mechanizm bazy i cache, nie pełną usługę HTTP ani reguły skrytek.

## Uruchomienie

Python 3.12+, PowerShell. W tym katalogu:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
$env:DATABASE_URL = 'sqlite:///./demo.db'
$env:CACHE_PREFIX = 'lab2:album12345:demo' # wpisz własny numer albumu
$env:CACHE_TTL_SECONDS = '60'
```

Wybierz jeden wariant Redis. Dla lokalnego Dockera:

```powershell
docker run --name lab2-redis -p 127.0.0.1:6379:6379 -d redis:7-alpine
$env:REDIS_URL = 'redis://localhost:6379/0'
```

Jeśli kontener już istnieje, użyj `docker start lab2-redis`. Alternatywnie użyj WSL2, Memurai lub serwera uczelnianego. Dla serwera uczelnianego ustaw `REDIS_URL` na pełny adres przekazany przez prowadzącego zamiast adresu lokalnego. Nie zapisuj sekretów w repozytorium ani nie zatrzymuj wspólnego serwera. Polecenia dla wariantów są w sekcji 3 instrukcji głównej.

Po konfiguracji, w tym samym terminalu:

```powershell
.\.venv\Scripts\python.exe demo.py seed
.\.venv\Scripts\python.exe demo.py get
.\.venv\Scripts\python.exe demo.py get
.\.venv\Scripts\python.exe demo.py rename --name 'Nowa nazwa'
.\.venv\Scripts\python.exe demo.py get
```

Oczekiwane wyniki: MISS, HIT, udane unieważnienie, MISS z nową nazwą. Każde polecenie uruchamia nowy proces. Baza jest plikiem demo.db w katalogu uruchomienia. Seed nie nadpisuje istniejącego rekordu.

MISS na początku wymaga pustego cache. Jeśli pozostał wpis, usuń tylko `${env:CACHE_PREFIX}:locker:KRK-1024` zgodnie z instrukcją główną. Demo ponownie czyta konfigurację przy każdym wywołaniu. Własny Uvicorn trzeba zatrzymać i ponownie uruchomić w terminalu ze zmienionymi zmiennymi środowiska.

## Pliki i integracja

- database.py: wspólna baza modeli ORM i fabryka sesji (włącza PRAGMA foreign_keys=ON dla SQLite).
- cache.py: adapter JSON; obsługuje GET, SET i DELETE, krótkie timeouty i brak ponowień.
- demo.py: tabela, repozytorium, warstwa cache oraz program konsolowy.
- tests/test_storage.py: izolowana baza w tmp_path i zamiennik Redis.
- README-LAB2-template.md: uzupełnienie dokumentacji istniejącego projektu.

Przenieś mechanizm do własnego app/database.py i app/cache.py. Modele domenowe oraz zapytania napisz samodzielnie. Jeśli przenosisz importy do pakietu app, dopasuj je, np. from app.database import Base. Zachowaj create_app(), modele Pydantic, endpointy, regułę i testy z LAB1. Repozytorium demonstracyjne zwraca słowniki; możesz zamiast nich zwracać modele Pydantic.

Własna aplikacja musi także obsłużyć walidację i mapowanie wyjątków na HTTP. Demo nie waliduje wejścia jak FastAPI i nie jest gotowym rozwiązaniem do oddania.

## Ograniczenia i testy ręczne

Testy nie wymagają Redis. Zamiennik nie symuluje upływu TTL. Wykonaj osobno:
1. PING prawdziwego Redis.
2. MISS → HIT oraz GET i TTL własnego klucza.
3. Odczyt po wygaśnięciu TTL.
4. Odłączenie klienta → get daje BYPASS: zapisz `$workingRedisUrl = $env:REDIS_URL`, następnie ustaw niedostępny adres, np. `$env:REDIS_URL = 'redis://127.0.0.1:9999/0'` (nieużywany port).
5. Rename przy awarii → zapis pozostaje w bazie mimo cache_invalidated=False.
6. Przywrócenie adresu przez `$env:REDIS_URL = $workingRedisUrl` i sprawdzenie starej wartości, a po wygaśnięciu TTL — aktualnej wartości z bazy.

Aby powtarzalnie zaobserwować starą wartość, pozostaw serwer włączony, przed odłączeniem wypełnij cache i wykonaj kroki 4–6 przed upływem TTL. Kompletny scenariusz z tymczasowym TTL 300 sekund i przywróceniem konfiguracji jest w kroku 3 części A instrukcji głównej. Sam restart serwera może usunąć wpis, więc nie dowodzi poprawnego unieważniania.

Nieudane unieważnienie może pozostawić starą wartość aż do TTL. Test failed_invalidation pokazuje to ograniczenie. Współbieżność nie jest rozwiązana: prosty cache-aside nie gwarantuje ścisłej spójności.

Baza powstaje przez create_all; zmiana kolumn wymaga migracji. Demo nie odtwarza skrytek ani całego API z LAB1. Lokalna baza i środowisko nie należą do oddawanego repozytorium.
