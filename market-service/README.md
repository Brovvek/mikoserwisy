# Market Service — LAB1

Pierwsza usługa projektu **„agregator i analizator ogłoszeń samochodowych”**. System zbiera oferty z portali ogłoszeniowych (otomoto.pl, autoscout24.de, autobazar.eu), sprowadza je do wspólnego modelu i śledzi zmiany cen, żeby dało się porównywać oferty i rynki różnych krajów.

Docelowy kształt systemu jest wzorowany na projekcie AutoRadar: podział na collector-service, market-service i alert-service, nazwy pól ofert i słownik paliw. Market Service jest rdzeniem systemu — przechowuje oferty i historię ich cen. Na LAB1 dane są w pamięci procesu, usługa działa na porcie **8101**, a oferty wprowadza się przez API; docelowo dostarczy je collector-service.

Odpowiedzi na pytania z części A instrukcji (przykład Locker Service) znajdują się w pliku [czesc-a-locker-service.md](czesc-a-locker-service.md).

```
market-service/
├── app/
│   ├── main.py       # create_app(), endpointy, dane początkowe, mapowanie błędów na HTTP
│   ├── models.py     # modele Pydantic: kontrakt API i walidacja
│   └── store.py      # magazyn w pamięci i reguła biznesowa
├── tests/
│   ├── conftest.py   # fixture: świeża aplikacja dla każdego testu
│   ├── test_health.py
│   └── test_listings.py
├── requests/         # treści żądań JSON do scenariusza ręcznego
├── requirements.txt
└── README.md
```

## Uruchomienie i testy

Wymagania: Python 3.12 lub nowszy (sprawdzono na 3.14.0) i PowerShell. Otwórz terminal w katalogu `market-service`, w którym leży ten plik.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8101
```

W drugim terminalu:

```powershell
Invoke-RestMethod http://localhost:8101/health
```

```
status service
------ -------
ok     market-service
```

Dokumentacja API: [Swagger UI](http://localhost:8101/docs) i [ReDoc](http://localhost:8101/redoc). Serwer zatrzymuje się przez `Ctrl+C`. Nie trzeba aktywować środowiska. Jeśli port jest zajęty, czyli `Get-NetTCPConnection -LocalPort 8101 -State Listen` zwraca rekord, uruchom usługę np. z `--port 8102` i zmień port w poleceniach.

`--reload` restartuje proces po zapisaniu zmian w kodzie, a restart kasuje dane z pamięci (sekcja 4).

## 1. Problem i granice

### Problem i użytkownik

Osoba szukająca używanego samochodu przegląda kilka portali osobno, także zagranicznych, bo auto z Niemiec czy Słowacji bywa tańsze. Każdy portal ma inny format ogłoszeń, inne nazwy paliw i inną walutę. Ceny zmieniają się z dnia na dzień, a ogłoszenia znikają. Trudno więc porównać oferty tego samego modelu z różnych rynków i zauważyć obniżkę ceny.

Market Service przechowuje oferty z różnych portali w jednym modelu i przy każdej kolejnej obserwacji zapisuje aktualną cenę oraz jej historię.

Użytkownicy usługi:

- **osoba kupująca samochód** — przegląda oferty i historię ich cen;
- docelowo **collector-service** — dostarcza obserwacje ofert z portali;
- docelowo frontend i alert-service — odczytują oferty.

### Za co odpowiada usługa

- przechowywanie ofert z portali we wspólnym modelu: źródło, numer ogłoszenia w portalu, kraj, link do oryginału, marka, model, rocznik, przebieg, paliwo, cena i waluta;
- pilnowanie, by ta sama oferta portalu (źródło + numer ogłoszenia) była zapisana tylko raz;
- zapisywanie kolejnych obserwacji oferty (cena, przebieg) w poprawnej kolejności czasu i prowadzenie historii cen;
- lista ofert (z filtrem po marce, modelu i kraju) oraz szczegóły jednej oferty.

### Za co usługa nie odpowiada

- pobieranie stron portali, harmonogram i wybór wycinków rynku do pobierania — to collector-service;
- powiadomienia o nowych ofertach i obniżkach — to przyszły alert-service;
- dane osobowe sprzedawców, np. imię i telefon — nie są zapisywane w ogóle;
- kopie zdjęć i treści ogłoszeń — usługa przechowuje tylko link do oryginału;
- kupno, sprzedaż i płatności — usługa nie pośredniczy w transakcjach;
- konta użytkowników i logowanie.

Przeliczanie cen po kursach NBP, ocena ceny oferty, wykrywanie sprzedanych ofert i trendy to przyszłe funkcje *tej samej* usługi, a nie innych usług. Na LAB1 nie są realizowane.

### Pojęcia domenowe

- **Źródło (portal)** — serwis ogłoszeniowy, z którego pochodzi oferta: `otomoto` (PL), `autoscout24_de` (DE), `autobazar_eu` (SK, także oferty z CZ).
- **Oferta** — jedno ogłoszenie sprzedaży samochodu w danym źródle. W portalu ma numer `external_id`, a w usłudze — własny identyfikator `id`.
- **Obserwacja** — stan oferty (cena, przebieg) odczytany z portalu w konkretnej chwili `observed_at`.
- **Historia cen** — kolejne ceny oferty w czasie. Nowy punkt powstaje tylko wtedy, gdy cena się zmieniła.
- **Rynek** — oferty z jednego kraju. Porównanie tego samego modelu na różnych rynkach to cel przyszłej analizy.

### Dwie planowane usługi

| Planowana usługa | Odpowiedzialność | Własne dane | Operacje | Potrzebne informacje od innej usługi |
|---|---|---|---|---|
| Pierwsza — **market-service**, implementowana teraz (port 8101) | Wiedza o rynku: oferty z portali w jednym modelu i historia ich cen | Oferty: źródło, numer w portalu, kraj, link, tytuł, marka, model, rocznik, przebieg, paliwo, cena, waluta, czas pierwszej i ostatniej obserwacji, historia cen | Lista z filtrami, szczegóły, rejestracja nowej oferty, zapis nowszej obserwacji | Docelowo od collector-service: obserwacje ofert z portali. Na LAB1 — żadne; dane wprowadza się przez API |
| Druga — **collector-service**, implementowana później (np. port 8102) | Skąd i kiedy pobierać: wycinki rynku (segmenty) i uprzejme pobieranie list wyników z portali | Segmenty (marka, model, roczniki, portale), przebiegi pobierania, stan portali (np. wstrzymanie po serii odmów) | Konfiguracja segmentów, uruchamianie i odczyt przebiegów, stan portali | Do pobierania — żadne. Wynik pracy, czyli obserwacje ofert, przekazuje do market-service |

### Granice biznesowe i właściciel zapisu

- Oferty i historię cen zapisuje **wyłącznie market-service**, przez swoje API. Na LAB1 robi to klient API (ręcznie i w testach), docelowo — tylko collector-service. Frontend i alert-service mogą oferty jedynie odczytywać.
- Segmenty, przebiegi i stan portali zapisuje **wyłącznie collector-service**. Market-service nie przechowuje ich kopii; przy ofercie zna tylko identyfikator źródła (`source`).

Podział wynika z odpowiedzialności, nie z tabel:

- collector-service odpowiada na pytanie „skąd i kiedy pobierać”. Zmienia się, gdy portal zmieni układ strony albo zabezpieczenia. Jego praca to długie, celowo spowolnione przebiegi z limitem tempa i poszanowaniem robots.txt.
- market-service odpowiada na pytanie „co wiemy o rynku”. Jego model nie zależy od portalu, a zmienia się, gdy rosną potrzeby analizy: porównania, trendy, ocena ceny.

Każda z usług będzie mieć kilka tabel — w market-service np. oferty i zmiany cen, a później katalog modeli i kursy walut — i nadal pozostanie jedną usługą. Granicą jest odpowiedzialność, nie liczba tabel.

To także granica znaczenia pojęć, punkt wyjścia do bounded context. „Oferta” w collector-service to wpis z listy wyników odczytany w jednym przebiegu, czyli chwilowa migawka. W market-service to trwały byt z historią, który łączy wszystkie obserwacje tego samego ogłoszenia.

### Przyszłe wywołanie między usługami

To projekt kontraktu; komunikacja nie jest zaimplementowana na LAB1.

- **Nadawca:** collector-service, po odczytaniu strony wyników z portalu.
- **Odbiorca:** market-service.
- **Metoda i ścieżka:** `POST /listings` dla oferty, której market-service jeszcze nie zna, np. `POST http://localhost:8101/listings`.
- **Żądanie:** treść jak w [requests/create-ok.json](requests/create-ok.json), czyli pola z sekcji 2. Dodatkowe pola collectora są pomijane.
- **Odpowiedź 201:** zapisana oferta z nadanym `id` (przykład w sekcji 3).
- **Odpowiedź 409:** `{"detail": "Listing otomoto/6123456789 already exists (listing 1)"}` — oferta jest już znana. Collector wysyła wtedy obserwację: `PATCH /listings/1` z polami `observed_at`, `price_amount` i `mileage_km`.
- **Odpowiedź 422:** dane z portalu nie spełniają kontraktu, np. brak ceny. Collector nie ponawia takiej obserwacji, tylko zapisuje błąd przebiegu.

**Zachowanie przy niedostępności market-service** (brak połączenia, timeout np. 5 s, odpowiedź 5xx):

- Collector nie gubi obserwacji: zachowuje je i ponawia wysyłkę z rosnącym odstępem.
- Pobieranie portali trwa dalej, bo nie zależy od market-service.
- Ponowienie jest bezpieczne: drugi `POST` tej samej oferty kończy się 409, a powtórzona obserwacja — 200 bez zmian (sekcja 2).
- Przebieg, którego obserwacji nie udało się dostarczyć, nie jest uznawany za kompletny.

Wysyłanie po jednej ofercie i ręczne ponowienia to koszt komunikacji synchronicznej. Dlatego na kolejnych laboratoriach to wywołanie zastąpi zdarzenie `listing.observed` w brokerze wiadomości — kolejka przechowa obserwacje, gdy market-service nie działa.

## 2. Model i reguła biznesowa

### Model `Listing`

| Pole | Typ JSON | Wymagane w `POST` | Ograniczenia | Kto nadaje |
|---|---|---|---|---|
| `id` | integer | — (pomijane) | kolejny numer w instancji: 1, 2, 3… | serwer |
| `source` | string | tak | wzorzec `^[a-z0-9_]{2,40}$`, np. `otomoto` | klient |
| `external_id` | string | tak | 1–80 znaków; numer ogłoszenia w portalu | klient |
| `country` | string | tak | kod ISO 3166-1, wzorzec `^[A-Z]{2}$`, np. `PL` | klient |
| `url` | string (URL) | tak | adres http(s) oryginalnego ogłoszenia | klient |
| `title` | string | tak | 1–200 znaków po obcięciu spacji z brzegów | klient |
| `make` | string | tak | 1–60 znaków, np. `BMW` | klient |
| `model` | string | tak | 1–80 znaków, np. `Seria 3` | klient |
| `year` | integer | tak | 1950–2100 | klient |
| `mileage_km` | integer | tak | ≥ 0 | klient |
| `fuel` | string | tak | `petrol`, `diesel`, `hybrid`, `plugin_hybrid`, `electric`, `lpg`, `cng`, `hydrogen` albo `other` | klient |
| `price_amount` | integer | tak | > 0, w pełnych jednostkach waluty | klient |
| `currency` | string | tak | kod ISO 4217, wzorzec `^[A-Z]{3}$`, np. `PLN` | klient |
| `observed_at` | string, data i czas ISO 8601 | tak (tylko w żądaniu) | ze strefą czasową, np. `2026-10-21T08:00:00Z` | klient |
| `first_seen_at`, `last_seen_at` | string, data i czas | — | pierwsza i ostatnia obserwacja | serwer |
| `price_history` | lista `{at, amount}` | — | kolejne ceny; punkt dochodzi tylko przy zmianie ceny | serwer |

`PATCH /listings/{listing_id}` przyjmuje obserwację (`ListingObservation`):

- `observed_at` — wymagane, ze strefą czasową;
- `price_amount` — wymagane, > 0;
- `mileage_km` — opcjonalne, ≥ 0; brak oznacza, że przebieg się nie zmienił.

Decyzje projektowe:

- **Identyfikator `id` nadaje serwer** jako kolejny numer w instancji. Naturalnym kluczem oferty jest para `(source, external_id)` i to ona musi być unikalna (409 przy duplikacie). Krótki numer wygodniej podać w ścieżce i nie zależy on od formatu numerów w portalach. Odrzucona operacja nie zużywa numeru.
- **`external_id` jest tekstem**, bo portale stosują różne formaty: otomoto — liczby, AutoScout24 — GUID.
- **Czas ze strefą** ([`AwareDatetime`](https://pydantic.dev/docs/validation/latest/api/pydantic/types/#pydantic.types.AwareDatetime)). Obserwacje pochodzą z portali w różnych krajach, a czasu bez strefy nie da się z nimi jednoznacznie porównać, więc daje 422. Python nie porówna też czasu bez strefy z czasem ze strefą (`TypeError`, czyli błąd 500).
- **Cena jako liczba całkowita w walucie ogłoszenia.** Portale podają ceny w pełnych złotych czy euro, a liczba całkowita nie ma błędów zaokrągleń typu `float`. Przeliczania na PLN/EUR nie ma na LAB1.
- **Nieznane pola są pomijane** (`extra="ignore"`, wzorzec tolerant reader). Przyszły nadawca, collector-service, może dodać pole bez łamania kontraktu. Pola nadawane przez serwer (`id`, historia cen) nie należą do modelu wejściowego, więc klient ich nie ustawi. Dane spoza kontraktu, np. telefon sprzedawcy, nie są zapisywane (test `test_unknown_fields_are_ignored`).
- **Marka i model są zapisywane tak, jak przyszły.** Ujednolicanie nazw z różnych portali (np. „3er” i „Seria 3”) to przyszła funkcja: katalog modeli.
- **Modele.** Model domenowy `Listing` z historią cen (`PricePoint`) oraz dwa modele wejściowe: `ListingCreate` (`POST`) i `ListingObservation` (`PATCH`). Historia cen należy do oferty, więc nie ma osobnego zasobu.

Dane początkowe — każda nowa instancja aplikacji, także po restarcie procesu, startuje z trzech ofert:

| id | source | external_id | kraj | oferta | rocznik | przebieg | paliwo | cena | obserwacja (UTC) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | otomoto | 6123456789 | PL | BMW Seria 3 320d xDrive M Sport | 2019 | 98 500 km | diesel | 104 900 PLN | 2026-10-20 08:00 |
| 2 | autoscout24_de | a8d3f1c2-0b5e-4c7a-9e21-5f6b7c8d9e01 | DE | BMW 320d Touring Luxury Line (BMW, Seria 3) | 2020 | 71 200 km | diesel | 22 400 EUR | 2026-10-20 09:00 |
| 3 | autobazar_eu | 198765432 | SK | Skoda Octavia Combi 2.0 TDI Style | 2018 | 142 000 km | diesel | 15 900 EUR | 2026-10-20 10:00 |

### Reguła biznesowa

**Stan oferty zmienia tylko obserwacja nowsza niż ostatnia.** Obserwacja (`PATCH /listings/{listing_id}`) jest przyjmowana, gdy jej `observed_at` jest późniejsze niż `last_seen_at` oferty. Wtedy:

- aktualna cena i przebieg przyjmują wartości z obserwacji, a `last_seen_at` — jej czas;
- jeśli cena się zmieniła, do `price_history` dochodzi nowy punkt;
- `first_seen_at` się nie zmienia.

Obserwacja starsza albo z tej samej chwili, ale z innymi danymi, jest odrzucana kodem **409**. Ponowne przesłanie dokładnie ostatniej obserwacji (ta sama chwila, cena i przebieg) jest dozwolone i niczego nie zmienia — tak działa np. ponowione żądanie po przekroczeniu czasu odpowiedzi.

**Po co ta reguła.** Obserwacje mogą przychodzić w innej kolejności, niż powstały: przy ponowieniach po awarii, z równoległych przebiegów albo przy ponownym przetwarzaniu zapisanych stron. Bez reguły spóźniona obserwacja nadpisałaby nowszą cenę i dopisała do historii fałszywą „zmianę ceny”. Na historii opierają się przyszłe analizy: obniżki i trendy.

- **Dozwolone:** `PATCH /listings/1` z [requests/observation-newer.json](requests/observation-newer.json): obserwacja z 2026-10-22 08:00 UTC, cena 99 900, przebieg 98 700. Ostatnia obserwacja oferty 1 jest z 2026-10-20, więc odpowiedź to **200**: cena 99 900, `last_seen_at` 2026-10-22, w historii dwa punkty (104 900 i 99 900).
- **Niedozwolone:** `PATCH /listings/1` z [requests/observation-older.json](requests/observation-older.json): obserwacja z 2026-10-19, czyli starsza niż ostatnia. Odpowiedź to **409**:

  ```json
  {"detail": "Observation from 2026-10-19T08:00:00+00:00 is not newer than the last observation of listing 1 (2026-10-20T08:00:00+00:00)"}
  ```

  Oferta pozostaje bez zmian.

**Dlaczego 409, a nie 422.** Treść obserwacji jest poprawna: ta sama obserwacja zostałaby przyjęta przez ofertę, której ostatnia obserwacja jest starsza. O odrzuceniu decyduje aktualny stan danych, czyli czas ostatniej obserwacji. Kod 422 oznacza dane błędne niezależnie od stanu, np. czas bez strefy albo cenę 0.

Drugi rodzaj konfliktu to **duplikat oferty**. `POST /listings` z parą `(source, external_id)`, która już istnieje, daje 409: `{"detail": "Listing otomoto/6123456789 already exists (listing 1)"}`. Ten sam numer ogłoszenia w innym portalu to inna oferta (201). To ograniczenie unikalności klucza, a nie główna reguła biznesowa.

### Warunki odrzucenia są sprawdzane przed zmianą stanu

1. FastAPI waliduje treść żądania i parametr ścieżki, zanim wywoła endpoint. Przy 422 kod magazynu w ogóle się nie wykonuje.
2. `ListingStore.create` najpierw szuka duplikatu `(source, external_id)`, a dopiero potem zwiększa licznik i zapisuje ofertę.
3. `ListingStore.record_observation` najpierw odczytuje ofertę (404) i sprawdza regułę (409). Potem buduje nową kopię oferty (`model_copy` z nową listą historii) i podmienia ją jednym przypisaniem, więc nie istnieje stan „w połowie zmiany”.

Testy porównują pełny stan przed i po każdej odrzuconej operacji.

## 3. Kontrakt API

| Metoda | Ścieżka | Znaczenie | Sukces | Błędy |
|---|---|---|---|---|
| GET | `/health` | Status i nazwa usługi, bez danych domenowych | 200 | — |
| GET | `/listings` | Lista ofert w kolejności zapisu; opcjonalne filtry `?make=BMW`, `?model=Seria 3`, `?country=PL` (dokładna zgodność) | 200, również `[]` | — |
| GET | `/listings/{listing_id}` | Szczegóły oferty z historią cen | 200 | 404; 422 — identyfikator nie jest liczbą |
| POST | `/listings` | Rejestracja nowej oferty z portalu | 201 | 409 — oferta z tego źródła już istnieje; 422 — błędne dane |
| PATCH | `/listings/{listing_id}` | Zapis nowszej obserwacji: aktualna cena i przebieg | 200 | 404; 409 — obserwacja nie jest nowsza; 422 — błędne dane |

Uzasadnienie kodów:

- **200 OK** — odczyt albo zmiana się udały; odpowiedź zawiera aktualny stan oferty. Ponowione przesłanie ostatniej obserwacji też zwraca 200: stan docelowy jest już osiągnięty.
- **201 Created** — `POST` utworzył nową ofertę; odpowiedź zawiera nadane `id`, czasy obserwacji i historię cen.
- **404 Not Found** — brak oferty o identyfikatorze ze ścieżki. Filtr listy, który nic nie znajduje, zwraca **200 i `[]`**: kolekcja istnieje, jest tylko pusta.
- **409 Conflict** — żądanie jest poprawne, ale koliduje z aktualnym stanem: oferta z tego źródła już istnieje albo obserwacja nie jest nowsza niż ostatnia.
- **422 Unprocessable Content** (dawniej „Unprocessable Entity”) — dane nie spełniają kontraktu niezależnie od stanu: zły typ, brak pola, przekroczony zakres, niezgodny wzorzec, nieznane paliwo, zły adres URL, czas bez strefy albo identyfikator w ścieżce, który nie jest liczbą.

**Dlaczego `PATCH`, a nie `PUT` lub `POST`.** Obserwacja zmienia tylko część pól istniejącej oferty: cenę, przebieg i czas ostatniej obserwacji. Nie zastępuje całej oferty (to robiłby `PUT`) i nie tworzy nowego zasobu (to robi `POST`).

Są dwa formaty błędów:

- **404 i 409** (`HTTPException`): `{"detail": "opis"}`, czyli jeden tekst.
- **422** (walidacja FastAPI, `RequestValidationError`): `{"detail": [ ... ]}`, czyli lista obiektów:
  - `loc` — miejsce błędu, np. `["body", "price_amount"]` albo `["path", "listing_id"]`;
  - `msg` — przyczyna;
  - `type` — kod błędu;
  - `input` — odrzucona wartość;
  - `ctx` — parametry ograniczenia (gdy występuje).

  Jedno żądanie może zgłosić kilka błędów naraz.

Pełne schematy, ograniczenia pól i przykładowe żądanie są w `/docs`.

### Przykłady żądań i odpowiedzi

Odpowiedzi poniżej to rzeczywiste wyniki z działającej usługi (sekcja 4). Długie odpowiedzi są tylko sformatowane w kilku liniach; ich treść się nie zmieniła.

Wskazówki do poleceń w PowerShellu:

- Używaj `curl.exe`, nie aliasu `curl`.
- Ścieżkę do pliku z treścią podawaj w cudzysłowie: `"@requests/…"`. Bez cudzysłowu znak `@` jest operatorem PowerShella.
- Adres z kilkoma parametrami (`&`) też ujmij w cudzysłów.
- Treści żądań leżą w plikach w `requests/`. Dzięki temu nie trzeba wpisywać JSON-a w poleceniu, a PowerShell 5.1 usuwa z niego cudzysłowy.

**Rejestracja oferty — 201**

```powershell
curl.exe -i -X POST -H "Content-Type: application/json" --data-binary "@requests/create-ok.json" http://localhost:8101/listings
```

Treść żądania ([requests/create-ok.json](requests/create-ok.json)):

```json
{
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
  "observed_at": "2026-10-21T08:00:00Z"
}
```

Odpowiedź `HTTP/1.1 201 Created`:

```json
{
  "id": 4,
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
  "first_seen_at": "2026-10-21T08:00:00Z",
  "last_seen_at": "2026-10-21T08:00:00Z",
  "price_history": [{"at": "2026-10-21T08:00:00Z", "amount": 129900}]
}
```

To samo w PowerShellu bez pliku. To polecenie pokazuje treść odpowiedzi, ale nie status:

```powershell
$body = @{ source = 'otomoto'; external_id = '6123456790'; country = 'PL'; url = 'https://www.otomoto.pl/osobowe/oferta/bmw-seria-3-ID6123456790.html'; title = 'BMW Seria 3 320i Sport Line'; make = 'BMW'; model = 'Seria 3'; year = 2021; mileage_km = 45000; fuel = 'petrol'; price_amount = 129900; currency = 'PLN'; observed_at = '2026-10-21T08:00:00Z' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8101/listings -ContentType 'application/json' -Body $body
```

**Szczegóły — 200**

`curl.exe -i http://localhost:8101/listings/4` zwraca tę samą treść, co odpowiedź na `POST`.

**Lista z filtrem — 200**

`curl.exe -i "http://localhost:8101/listings?make=BMW&model=Seria%203"` zwraca oferty 1 i 2 (PL i DE). Filtr bez wyników, `curl.exe -i "http://localhost:8101/listings?make=Audi"`:

```json
[]
```

**Brak zasobu — 404**

`curl.exe -i http://localhost:8101/listings/999`:

```json
{"detail":"Listing 999 not found"}
```

**Identyfikator, który nie jest liczbą — 422**

`curl.exe -i http://localhost:8101/listings/abc`:

```json
{"detail":[{"type":"int_parsing","loc":["path","listing_id"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"abc"}]}
```

**Duplikat oferty — 409**

Treść: [requests/create-duplicate.json](requests/create-duplicate.json) — oferta otomoto/6123456789, czyli oferta 1, z inną ceną.

```powershell
curl.exe -i -X POST -H "Content-Type: application/json" --data-binary "@requests/create-duplicate.json" http://localhost:8101/listings
```

```json
{"detail":"Listing otomoto/6123456789 already exists (listing 1)"}
```

**Błędne dane — 422**

Treść: [requests/create-invalid.json](requests/create-invalid.json) — kraj `pl`, przebieg −1 i czas bez strefy.

```powershell
curl.exe -i -X POST -H "Content-Type: application/json" --data-binary "@requests/create-invalid.json" http://localhost:8101/listings
```

```json
{"detail":[
  {"type":"string_pattern_mismatch","loc":["body","country"],"msg":"String should match pattern '^[A-Z]{2}$'","input":"pl","ctx":{"pattern":"^[A-Z]{2}$"}},
  {"type":"greater_than_equal","loc":["body","mileage_km"],"msg":"Input should be greater than or equal to 0","input":-1,"ctx":{"ge":0}},
  {"type":"timezone_aware","loc":["body","observed_at"],"msg":"Input should have timezone info","input":"2026-10-21T08:00:00"}
]}
```

Inne odpowiedzi 422 (sprawdzane w testach):

| Żądanie `POST /listings` | `type` | `loc` | `msg` |
|---|---|---|---|
| `"year": 1949` | `greater_than_equal` | `["body","year"]` | `Input should be greater than or equal to 1950` |
| `"price_amount": 0` | `greater_than` | `["body","price_amount"]` | `Input should be greater than 0` |
| `"currency": "zł"` | `string_pattern_mismatch` | `["body","currency"]` | `String should match pattern '^[A-Z]{3}$'` |
| `"fuel": "gas"` | `enum` | `["body","fuel"]` | `Input should be 'petrol', 'diesel', 'hybrid', 'plugin_hybrid', 'electric', 'lpg', 'cng', 'hydrogen' or 'other'` |
| `"url": "otomoto.pl/oferta"` | `url_parsing` | `["body","url"]` | `Input should be a valid URL, relative URL without a base` |
| `"title": "   "` | `string_too_short` | `["body","title"]` | `String should have at least 1 character` |
| brak pola `make` | `missing` | `["body","make"]` | `Field required` |

**Nowsza obserwacja — 200**

Treść: [requests/observation-newer.json](requests/observation-newer.json), czyli `{"observed_at": "2026-10-22T08:00:00Z", "price_amount": 99900, "mileage_km": 98700}`.

```powershell
curl.exe -i -X PATCH -H "Content-Type: application/json" --data-binary "@requests/observation-newer.json" http://localhost:8101/listings/1
```

Odpowiedź — wybrane pola:

```json
{
  "id": 1,
  "mileage_km": 98700,
  "price_amount": 99900,
  "first_seen_at": "2026-10-20T08:00:00Z",
  "last_seen_at": "2026-10-22T08:00:00Z",
  "price_history": [
    {"at": "2026-10-20T08:00:00Z", "amount": 104900},
    {"at": "2026-10-22T08:00:00Z", "amount": 99900}
  ]
}
```

To samo przez `Invoke-RestMethod`:

```powershell
$body = @{ observed_at = '2026-10-22T08:00:00Z'; price_amount = 99900; mileage_km = 98700 } | ConvertTo-Json
Invoke-RestMethod -Method Patch -Uri http://localhost:8101/listings/1 -ContentType 'application/json' -Body $body
```

**Starsza obserwacja — 409**

Treść: [requests/observation-older.json](requests/observation-older.json), czyli `{"observed_at": "2026-10-19T08:00:00Z", "price_amount": 109900}`. Wysłana po poprzednim kroku, gdy ostatnia obserwacja oferty jest już z 2026-10-22:

```json
{"detail":"Observation from 2026-10-19T08:00:00+00:00 is not newer than the last observation of listing 1 (2026-10-22T08:00:00+00:00)"}
```

**Błędna obserwacja — 422**

Treść: [requests/observation-invalid.json](requests/observation-invalid.json), czyli `{"observed_at": "2026-10-23T08:00:00", "price_amount": 0}`.

```json
{"detail":[
  {"type":"timezone_aware","loc":["body","observed_at"],"msg":"Input should have timezone info","input":"2026-10-23T08:00:00"},
  {"type":"greater_than","loc":["body","price_amount"],"msg":"Input should be greater than 0","input":0,"ctx":{"gt":0}}
]}
```

## 4. Testy i stan danych

### Testy automatyczne

Każdy test dostaje własną aplikację z fixture `client` ([tests/conftest.py](tests/conftest.py)). `TestClient(create_app())` tworzy nowy `ListingStore` z trzema ofertami początkowymi, więc testy nie zależą od kolejności uruchomienia. `TestClient` nie wymaga działającego Uvicorna. Po każdej odrzuconej operacji testy porównują pełny stan z tym sprzed żądania.

Wszystkie testy oprócz `test_health` są w pliku [tests/test_listings.py](tests/test_listings.py).

| Test | Co wykazuje |
|---|---|
| `test_health` ([tests/test_health.py](tests/test_health.py)) | 200 i nazwa `market-service`. To test startowy, nie liczy się do minimum |
| `test_list_and_details_return_initial_listings` | 200, lista ofert 1–3, wszystkie pola oferty 1 |
| `test_filtered_list_may_be_empty` | Filtry `make` z `model` oraz `country`; brak wyników to 200 i `[]`, nie 404 |
| `test_unknown_listing_returns_404` | 404 i `detail` dla `GET` i `PATCH` |
| `test_non_numeric_listing_id_returns_422` | `GET /listings/abc` → 422 z `loc: ["path","listing_id"]` |
| `test_create_then_read` | **Zapis → odczyt**: 201, `id` 4, `first_seen_at` = `last_seen_at` = `observed_at`, historia z jednym punktem; osobny `GET` zwraca to samo, lista ma 4 oferty |
| `test_invalid_listing_returns_422_and_does_not_change_state` (9 przypadków) | **Błędne dane bez zmiany stanu.** Przypadki: rocznik 1949, przebieg −1, cena 0, kraj `pl`, waluta `zł`, paliwo `gas`, adres bez `http`, pusty tytuł, czas bez strefy. Każdy daje 422 z `loc` wskazującym dokładnie to pole, a lista się nie zmienia |
| `test_unknown_fields_are_ignored` | Nadmiarowe pola są pomijane: przesłane `id: 77` nie działa (serwer nadaje 4), a `seller_phone` nie jest zapisywany |
| `test_duplicate_listing_returns_409_and_does_not_change_state` | **Konflikt bez zmiany stanu**: duplikat otomoto/6123456789 → 409, lista bez zmian; następna nowa oferta nadal dostaje `id` 4 |
| `test_same_external_id_in_another_source_is_another_listing` | Klucz unikalności to para `(source, external_id)`: ten sam numer w innym portalu → 201 |
| `test_newer_observation_updates_price_and_history` | **Reguła (dozwolone) i zapis → odczyt**: 200, nowa cena i przebieg, nowe `last_seen_at`, drugi punkt historii, `first_seen_at` bez zmian; osobny `GET` to potwierdza |
| `test_newer_observation_with_the_same_price_keeps_history` | Nowsza obserwacja z tą samą ceną zmienia `last_seen_at`, ale nie historię; brak przebiegu w obserwacji nie zmienia przebiegu |
| `test_older_observation_returns_409_and_does_not_change_state` | **Reguła (niedozwolone)**: 409 z opisem, oferta bez zmian |
| `test_repeated_last_observation_changes_nothing` | Ponowiona ostatnia obserwacja → 200 bez zmian; ta sama chwila z inną ceną → 409, oferta bez zmian |
| `test_invalid_observation_returns_422_and_does_not_change_state` (4 przypadki) | Czas bez strefy, cena 0, przebieg −5, brak `observed_at` → 422, oferta bez zmian |
| `test_each_application_has_its_own_store` | Dwie instancje `create_app()` nie współdzielą danych |

Wynik polecenia ze wstępu (2026-10-25, Windows 10, Python 3.14.0):

```
PS> .\.venv\Scripts\python.exe -m pytest -q
...........................                                              [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\starlette\testclient.py:51
  DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
27 passed, 1 warning in 0.85s
```

27 testów to 1 test startowy i 26 własnych przypadków. Ostrzeżenie pochodzi z biblioteki Starlette i nowszej biblioteki `anyio`; Starlette jest w wersji 0.47, którą wymusza `requirements.txt`. Nie dotyczy kodu usługi ani wyników. Instalacja od zera w nowym środowisku dała ten sam wynik.

Skuteczność testów sprawdzono na kopii kodu z celowo wprowadzonymi błędami. Każdy z 9 błędów wykrył co najmniej jeden test:

- obserwacja z tej samej chwili z inną ceną przyjmowana;
- powtórzona ostatnia obserwacja traktowana jako konflikt;
- punkt historii dopisywany mimo tej samej ceny;
- numer zużywany przed sprawdzeniem duplikatu;
- duplikat sprawdzany bez źródła;
- zmiana stanu przed sprawdzeniem reguły;
- `first_seen_at` nadpisywane przez obserwację;
- czas bez strefy przyjmowany przy tworzeniu oferty;
- 422 zamiast 409 przy starszej obserwacji.

### Scenariusze i wyniki

| Scenariusz | Stan początkowy i dokładne żądanie | Oczekiwany status, treść i stan | Wynik rzeczywisty | Reset danych |
|---|---|---|---|---|
| Health | Dowolny; `GET /health` | 200, `{"status":"ok","service":"market-service"}` | Zgodny: `test_health` passed; krok 1 ręcznie: 200 | Nie zmienia danych |
| Lista i szczegóły | Dane początkowe; `GET /listings`, `GET /listings/1` | 200, oferty 1–3; szczegóły oferty 1: otomoto, BMW Seria 3, 104 900 PLN | Zgodny: test passed; krok 2 ręcznie: 200 | Nie zmienia danych |
| Zapis → odczyt | Dane początkowe; `POST /listings` z `create-ok.json`, potem `GET /listings/4` | 201 z `id: 4`; `GET` 200 z tymi samymi danymi | Zgodny: `test_create_then_read` passed; kroki 5–6 ręcznie: 201, potem 200 | Testy: nowa aplikacja; ręcznie: restart Uvicorna |
| Brak zasobu | Dane początkowe; `GET /listings/999` | 404, `{"detail":"Listing 999 not found"}` | Zgodny: test passed; krok 4 ręcznie: 404 | Nie zmienia danych |
| Błędne dane | Dane początkowe, w scenariuszu ręcznym także oferta 4; `POST` z `create-invalid.json` | 422, `detail` wskazuje `country`, `mileage_km` i `observed_at`; brak nowej oferty | Zgodny: 9 przypadków passed; krok 8 ręcznie: 422, `GET /listings?make=Audi` nadal `[]` | Nie zmienia danych |
| Konflikt | Oferta 1 = otomoto/6123456789; `POST` z `create-duplicate.json` | 409, `detail` wskazuje ofertę 1; oferta 1 bez zmian (104 900 PLN) | Zgodny: test passed; krok 7 ręcznie: 409, oferta 1 bez zmian | Nie zmienia danych |
| Reguła biznesowa: dozwolona i niedozwolona operacja | Oferta 1 z ostatnią obserwacją z 2026-10-20. Dozwolone: `PATCH /listings/1` z `observation-newer.json`. Niedozwolone: `PATCH /listings/1` z `observation-older.json` | Dozwolone → 200, cena 99 900, dwa punkty historii. Niedozwolone → 409, oferta bez zmian | Zgodny: testy reguły passed. Ręcznie: krok 9 — 200, krok 10 — 409 i bez zmian, krok 11 — powtórka 200 bez zmian | Testy: nowa aplikacja; ręcznie: restart |
| Restart | Po krokach 1–12: istnieje oferta 4, oferta 1 ma cenę 99 900 i dwa punkty historii. Zatrzymanie i ponowne uruchomienie Uvicorna, potem `GET` | Oferta 4 → 404, oferta 1 znów 104 900 PLN z jednym punktem historii, lista = dane początkowe | Zgodny, szczegóły niżej | Restart sam przywraca dane początkowe |

### Scenariusz ręczny przez HTTP

Scenariusz wykonano 2026-10-25 na działającym Uvicornie (`.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8101`), z drugiego terminala przez `curl.exe`. Wszystkie kroki da się powtórzyć w `/docs`. Ścieżki plików są względne do katalogu `market-service`.

| Krok | Żądanie | Oczekiwany wynik | Wynik rzeczywisty |
|---|---|---|---|
| 1 | `GET /health` | 200, status i nazwa usługi | 200 `{"status":"ok","service":"market-service"}` |
| 2 | `GET /listings`, `GET /listings/1` | 200, trzy oferty; szczegóły oferty 1 | 200, oferty 1–3; 200, otomoto, 104 900 PLN, jeden punkt historii |
| 3 | `GET /listings?make=BMW&model=Seria%203`, `GET /listings?make=Audi` | 200 z ofertami 1 i 2; 200 i `[]` | 200, oferty 1 (PL) i 2 (DE); 200 `[]` |
| 4 | `GET /listings/999`, `GET /listings/abc` | 404 z opisem; 422 dla ścieżki | 404 `{"detail":"Listing 999 not found"}`; 422 `int_parsing`, `loc: ["path","listing_id"]` |
| 5 | `POST /listings`, `create-ok.json` | 201, oferta 4 | 201, `id: 4`, `first_seen_at` = `last_seen_at` = 2026-10-21T08:00:00Z |
| 6 | `GET /listings/4` | 200, dane z kroku 5 | 200, identyczne dane |
| 7 | `POST /listings`, `create-duplicate.json`; potem `GET /listings/1` | 409; oferta 1 bez zmian | 409 (oferta 1 już istnieje); oferta 1 nadal 104 900 PLN |
| 8 | `POST /listings`, `create-invalid.json`; potem `GET /listings?make=Audi` | 422 dla trzech pól; oferta nie powstaje | 422 z trzema błędami; `[]` |
| 9 | `PATCH /listings/1`, `observation-newer.json`; potem `GET /listings/1` | 200; cena 99 900, dwa punkty historii w obu odpowiedziach | 200 i `GET` 200: cena 99 900, przebieg 98 700, `last_seen_at` 2026-10-22T08:00:00Z, dwa punkty historii |
| 10 | `PATCH /listings/1`, `observation-older.json`; potem `GET /listings/1` | 409; oferta bez zmian | 409 (ostatnia obserwacja z 2026-10-22); oferta bez zmian |
| 11 | Ponownie `PATCH /listings/1`, `observation-newer.json`; potem `GET` | 200 bez zmian — to ta sama obserwacja | 200; nadal dwa punkty historii |
| 12 | `PATCH /listings/1`, `observation-invalid.json`; potem `GET` | 422; oferta bez zmian | 422 (`timezone_aware`, `greater_than`); oferta bez zmian |
| 13 | Zatrzymanie Uvicorna i ponowne uruchomienie tym samym poleceniem | Nowy proces z nowym magazynem | Nowy proces nasłuchuje na 8101 |
| 14 | `GET /listings/4`, `GET /listings/1`, `GET /listings` | 404; oferta 1 z danymi początkowymi; tylko oferty 1–3 | 404; 104 900 PLN, `last_seen_at` 2026-10-20T08:00:00Z, jeden punkt historii; oferty 1–3 |

Fragment logu Uvicorna z pierwszego uruchomienia potwierdza kody odpowiedzi:

```
INFO:     Uvicorn running on http://127.0.0.1:8101 (Press CTRL+C to quit)
INFO:     127.0.0.1:53871 - "GET /listings/999 HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:53873 - "GET /listings/abc HTTP/1.1" 422 Unprocessable Content
INFO:     127.0.0.1:53875 - "POST /listings HTTP/1.1" 201 Created
INFO:     127.0.0.1:53879 - "POST /listings HTTP/1.1" 409 Conflict
INFO:     127.0.0.1:53883 - "POST /listings HTTP/1.1" 422 Unprocessable Content
INFO:     127.0.0.1:53888 - "PATCH /listings/1 HTTP/1.1" 200 OK
INFO:     127.0.0.1:53893 - "PATCH /listings/1 HTTP/1.1" 409 Conflict
INFO:     127.0.0.1:53897 - "PATCH /listings/1 HTTP/1.1" 200 OK
INFO:     127.0.0.1:53902 - "PATCH /listings/1 HTTP/1.1" 422 Unprocessable Content
```

Port sprawdzono trzema sposobami: komunikatem Uvicorna (powyżej), odpowiedzią `/health` oraz poleceniem pokazującym proces nasłuchujący:

```
PS> Get-NetTCPConnection -LocalPort 8101 -State Listen | Format-Table LocalAddress, LocalPort, State, OwningProcess
LocalAddress LocalPort  State OwningProcess
------------ ---------  ----- -------------
127.0.0.1         8101 Listen          7956

PS> Get-Process -Id 7956 | Format-Table Id, ProcessName
  Id ProcessName
  -- -----------
7956 python
```

### Eksperyment z restartem

Uvicorna uruchomiono **bez `--reload`** i nie zmieniano kodu, żeby wykluczyć dodatkowy restart.

1. Kroki 5–12 utworzyły ofertę 4 i zmieniły cenę oferty 1 na 99 900 (dwa punkty historii). Każdą zmianę potwierdził osobny `GET`.
2. Proces zatrzymano (w terminalu: `Ctrl+C`). Następnie `Get-NetTCPConnection -LocalPort 8101 -State Listen` nie zwrócił żadnego rekordu, a `Invoke-RestMethod http://localhost:8101/health` zakończył się błędem połączenia.
3. Uvicorna uruchomiono ponownie tym samym poleceniem.

Wynik po restarcie:

```
GET /listings/4                      -> 404 {"detail":"Listing 4 not found"}
GET /listings/1                      -> 200 cena 104900 PLN, last_seen_at 2026-10-20T08:00:00Z, 1 punkt historii
GET /listings                        -> 200 oferty 1, 2, 3 (każda z 1 punktem historii)
PATCH /listings/1 (obserwacja z 19.10) -> 409, teraz względem obserwacji z 2026-10-20 — tej z 22.10 już nie ma
POST create-ok.json                  -> 201 {"id": 4, ...}  (ten sam numer nadany ponownie)
```

**Dlaczego dane przetrwały między żądaniami, ale nie restart.** Uvicorn przy starcie importuje `app.main`, a wtedy `create_app()` raz tworzy obiekt `ListingStore` i zapisuje go w `app.state.listings`. Wszystkie żądania obsługuje ten sam proces i ten sam obiekt w jego pamięci, więc zmiana z `POST` albo `PATCH` jest widoczna w następnym `GET`.

Zatrzymanie procesu zwalnia jego pamięć, a dane nie są nigdzie zapisywane — nie ma pliku ani bazy. Nowy proces ponownie wywołuje `create_app()`: powstaje pusty magazyn, do którego trafiają tylko oferty początkowe. Historia cen sprzed restartu przepada, a licznik numerów zaczyna od nowa, stąd ponowne `id` 4.

`--reload` działa tak samo, bo po zapisaniu pliku restartuje proces. Trwałe dane przyniesie baza na LAB2; dla agregatora to warunek konieczny, bo historia cen jest jego głównym zasobem.

## 5. Porównanie architektur

Ten sam system — pobieranie ofert z portali, oferty z historią cen i powiadomienia — w trzech wariantach.

**Monolit**

```
                       Klient (przeglądarka)
                                 │ HTTP
                                 ▼
┌───────────── jeden proces: aplikacja „agregator ogłoszeń” ─────────────┐
│                                                                        │
│   pobieranie portali ── wywołanie w kodzie ──► oferty i historia cen   │
│                                                      │                 │
│                                                      │ wywołanie       │
│                                                      ▼ w kodzie        │
│                                                powiadomienia           │
│                                                                        │
│   brak granic modułów: każdy fragment kodu czyta i zmienia             │
│   dowolne tabele                                                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    ▼
                       jedna wspólna baza danych
           (segmenty, oferty, historia cen, obserwowane razem)
```

**Modularny monolit**

```
                                    Klient
                                      │ HTTP
                                      ▼
┌─────────────── jeden proces: jedna aplikacja, jedno wdrożenie ────────────────┐
│                                                                               │
│  ┌─ moduł pobierania ──────┐   wywołanie    ┌─ moduł rynku ─────────────────┐ │
│  │ segmenty, portale       │ ─────────────► │ record_observation()          │ │
│  │ zapisuje segmenty       │    w kodzie    │ zapisuje oferty i ceny        │ │
│  └────────────┬────────────┘                └───────┬───────────────┬───────┘ │
│               │                                     │ wywołanie     │         │
│               │                                     ▼ w kodzie      │         │
│               │                       ┌─ moduł powiadomień ─┐       │         │
│               │                       └──────────┬──────────┘       │         │
└───────────────┼──────────────────────────────────┼──────────────────┼─────────┘
                ▼                                  ▼                  ▼
┌────────────────────────────────── jedna baza danych ──────────────────────────┐
│  tabele segmentów        tabele obserwowanych         tabele ofert i cen      │
│  (pisze tylko moduł      (pisze tylko moduł           (pisze tylko moduł      │
│  pobierania)             powiadomień)                 rynku)                  │
└───────────────────────────────────────────────────────────────────────────────┘
```

**Mikrousługi**

```
                               Klient (przeglądarka)
                                         │ HTTP
                                         ▼
                         API Gateway (kolejne laboratoria)
                         HTTP │                     │ HTTP
                              ▼                     ▼
┌─ collector-service ───────────────┐       ┌─ market-service ──────────────────┐
│ osobny proces, port 8102          │ HTTP  │ osobny proces, port 8101          │
│ segmenty i pobieranie portali     │ ────► │ oferty i historia cen             │
│ jedyny zapis segmentów            │  (1)  │ jedyny zapis ofert                │
└────────┬───────────────┬──────────┘       └─────────────────┬─────────────────┘
         │               ▼                                    ▼
         │      dane segmentów                       dane ofert i cen
         │      i przebiegów                         (LAB1: pamięć procesu,
         │      (własna baza)                         LAB2: własna baza)
         ▼ HTTP (robots.txt, limit tempa)
  portale: otomoto.pl, autoscout24.de, autobazar.eu
```

(1) `POST /listings` i `PATCH /listings/{listing_id}` — przyszłe wywołanie opisane w sekcji 1. Docelowo zastąpi je zdarzenie `listing.observed` w brokerze wiadomości. Trzecia usługa, alert-service, będzie pobierać szczegóły ofert przez `GET /listings/{listing_id}`.

| Pytanie | Monolit | Modularny monolit | Mikrousługi |
|---|---|---|---|
| Czy wszystkie funkcje są wdrażane razem? | Tak | Tak | Nie — collector-service i market-service osobno |
| Czy części komunikują się przez sieć? | Nie, wywołania w kodzie | Nie, wywołania modułów | Tak, HTTP; później także broker zdarzeń |
| Czy działają w osobnych procesach? | Nie, jeden proces | Nie, jeden proces | Tak, każda usługa we własnym procesie i na własnym porcie |
| Czy awaria procesu może objąć cały system? | Tak | Tak | Wyłącza jedną usługę, ale skutki dotkną zależnych operacji: bez market-service nowe obserwacje czekają w collectorze |
| Czy dane mogą być rozdzielone? | Zwykle wspólne tabele | Logicznie — każdy moduł pisze tylko swoje tabele | Tak, każda usługa ma własne dane |
| Czy wdrożenie jest niezależne? | Nie | Nie | Tak |

Odpowiedzi na pytania z sekcji 6 instrukcji:

1. **Dlaczego market-service może być mikrousługą?**
   - Ma jedną spójną odpowiedzialność: wiedzę o ofertach i ich cenach, niezależną od portalu, z którego pochodzą.
   - Jest jedynym właścicielem i jedynym miejscem zapisu ofert i historii cen.
   - Udostępnia kontrakt HTTP i działa jako osobny proces na własnym porcie.
   - Da się ją wdrożyć i zrestartować niezależnie od pobierania: collector w tym czasie przechowa obserwacje i ponowi wysyłkę.
   - Regułę kolejności obserwacji sprawdza na własnych danych, bez pytania innej usługi.
2. **Dlaczego nie jest tylko klasą albo modułem?** `ListingStore` jest klasą *wewnątrz* usługi. Usługą jest cała aplikacja: osobny proces, komunikacja przez sieć zamiast wywołań funkcji, własne dane i własny cykl wdrożenia. Ten sam kod, wywoływany bezpośrednio z modułu pobierania w tym samym procesie, byłby tylko modułem. Osobny folder ani osobny port nie tworzą jeszcze mikrousługi.
3. **Jak wyglądałby system jako monolit?** Byłaby to jedna aplikacja z pobieraniem portali, ofertami i powiadomieniami oraz wspólną bazą. Po odczytaniu strony wyników kod pobierania wywołałby wprost funkcję zapisu oferty, w jednej transakcji razem z zapisem przebiegu. Całość byłaby wdrażana i restartowana razem, więc awaria parsera portalu mogłaby zatrzymać także przeglądanie ofert.
4. **Co zmieniłoby się po podziale na mikroserwisy?**
   - Zyski:
     - pobieranie, czyli długie, spowolnione przebiegi, czasem z przeglądarką, nie zabiera zasobów obsłudze zapytań o oferty;
     - parsery portali, zmieniane po każdej zmianie strony, można wdrażać bez wdrażania market-service;
     - awaria albo blokada jednego portalu nie wyłącza przeglądania ofert;
     - pobieranie da się skalować osobno.
   - Koszty:
     - każda obserwacja to wywołanie sieciowe, a jeden przebieg to setki ofert;
     - znika wspólna transakcja między zapisem przebiegu a zapisem ofert;
     - potrzebne są ponowienia i idempotentne operacje (stąd 409 przy duplikacie i 200 przy powtórzonej obserwacji);
     - trzeba utrzymywać kontrakty, adresy usług (Eureka na LAB3), monitoring i testy integracyjne.
5. **Jakie koszty wprowadza komunikacja sieciowa?**
   - opóźnienie rzędu milisekund na każdą obserwację zamiast nanosekund wywołania funkcji;
   - timeouty i częściowe awarie — po timeoucie nie wiadomo, czy zapis się udał, więc operacje muszą znosić ponowienia;
   - serializacja JSON;
   - obsługa niedostępności odbiorcy (bufor i ponowienia po stronie collectora);
   - uwierzytelnianie między usługami i konfiguracja ich adresów;
   - rozproszone logi;
   - spójność ostateczna zamiast jednej transakcji.
6. **Czy mikroserwisy są tu uzasadnione?** Dla aplikacji jednego użytkownika, uruchamianej lokalnie, wystarczyłby **modularny monolit** z wyraźną granicą między pobieraniem a rynkiem. Podział ma jednak realne uzasadnienie: pobieranie i analiza mają zupełnie inny charakter pracy i inne powody zmian. Pobieranie jest długie, ograniczane tempem portali i często poprawiane po zmianach stron. Analiza musi odpowiadać szybko i rozwija się razem z potrzebami użytkownika. W projekcie mikrousługi wybrano świadomie, bo celem przedmiotu jest nauka tej architektury, a ta granica wynika z domeny. Moduły rozdzielone w ten sposób dałoby się w razie potrzeby połączyć z powrotem w jeden proces.

## 6. Dokumentacja wykorzystana podczas pracy

| Odnośnik do fragmentu | Rozwiązywany problem | Co zastosowano w kodzie | Jak sprawdzono działanie |
|---|---|---|---|
| [FastAPI — Body - Fields: Declare model attributes](https://fastapi.tiangolo.com/tutorial/body-fields/#declare-model-attributes) | Jak wymusić zakresy i formaty pól oferty, żeby błędne dane kończyły się 422, zanim wykona się logika usługi | `Field(ge=1950, le=2100)`, `Field(gt=0)`, `Field(ge=0)`, `Field(pattern=...)` i `Field(min_length=..., max_length=...)` w `ListingCreate` i `ListingObservation` ([app/models.py](app/models.py)) | Test `test_invalid_listing_returns_422_and_does_not_change_state`: rocznik, przebieg, cena, kraj, waluta i tytuł dają 422, `loc` wskazuje pole, lista się nie zmienia. Ręcznie: krok 8 |
| [FastAPI — Handling Errors: Use HTTPException](https://fastapi.tiangolo.com/tutorial/handling-errors/#use-httpexception) i [Use the RequestValidationError body](https://fastapi.tiangolo.com/tutorial/handling-errors/#use-the-requestvalidationerror-body) | Zwrócenie 404 i 409 z opisem; zrozumienie, czym różni się od nich format 422 | Magazyn zgłasza `ListingNotFoundError` albo `ListingConflictError`. Endpointy zamieniają je na `HTTPException(status_code=404 lub 409, detail=str(exc))` ([app/main.py](app/main.py)). Oba formaty opisano w sekcji 3 | Testy 404 i 409 porównują dokładne `{"detail": "..."}`. Testy 422 czytają listę `detail[].loc`. Ręcznie: kroki 4, 7 i 10 |
| [FastAPI — Path Parameters: Path parameters with types](https://fastapi.tiangolo.com/tutorial/path-params/#path-parameters-with-types) i [Data validation](https://fastapi.tiangolo.com/tutorial/path-params/#data-validation) | Identyfikator oferty w ścieżce ma być liczbą; tekst ma dawać czytelne 422, a nie 404 ani błąd 500 | `listing_id: int` w `GET` i `PATCH /listings/{listing_id}` | `test_non_numeric_listing_id_returns_422` (`loc: ["path","listing_id"]`). Ręcznie: krok 4 |
| [Pydantic — AwareDatetime](https://pydantic.dev/docs/validation/latest/api/pydantic/types/#pydantic.types.AwareDatetime) | Obserwacje z portali w różnych krajach muszą dać się porównać w czasie; reguła biznesowa porównuje `observed_at` z `last_seen_at` | `observed_at: AwareDatetime` w obu modelach wejściowych | Przypadki „czas bez strefy” w POST i PATCH dają 422 `timezone_aware`. Zamiana na zwykły `datetime` została wykryta przez test |
| [Pydantic — Models: Extra data](https://pydantic.dev/docs/validation/latest/concepts/models/#extra-data) | Co zrobić z polami spoza kontraktu, które może przysłać przyszły nadawca (collector-service) | Świadomie `extra="ignore"` (tolerant reader) w `ListingCreate` i `ListingObservation` | `test_unknown_fields_are_ignored`: przesłane `id` nie działa, a `seller_phone` nie jest zapisywany |
| [FastAPI — Testing: Using TestClient](https://fastapi.tiangolo.com/tutorial/testing/#using-testclient) | Testy API bez uruchamiania Uvicorna i ze znanym stanem początkowym | Fixture `client` w [tests/conftest.py](tests/conftest.py): `with TestClient(create_app()) as test_client`; asercje `status_code` i `response.json()` | `pytest -q`: 27 passed. `test_each_application_has_its_own_store` potwierdza, że instancje mają osobne magazyny |

## 7. Ograniczenia, autorzy i AI

### Ograniczenia

- **Dane tylko w pamięci procesu.** `ListingStore` żyje w `app.state`. Restart, `--reload` i awaria procesu usuwają zmiany, w tym historię cen, i przywracają dane początkowe.
- **Identyfikatory nie są trwałe.** Licznik zaczyna od nowa po restarcie, więc oferta 4 sprzed restartu i oferta 4 po nim to różne oferty (widać to w eksperymencie). Do czasu LAB2 klient nie powinien zapamiętywać identyfikatorów na dłużej.
- **Brak wspólnego stanu między instancjami.** Każda instancja, np. na portach 8101 i 8102, ma własny magazyn i nie widzi danych drugiej. Ta sama oferta portalu mogłaby więc zostać zapisana w dwóch instancjach, a jej obserwacje rozdzielone między nie.
- **Brak ochrony przed równoczesnymi zapisami.** FastAPI wykonuje endpointy `def` w puli wątków, więc dwa jednoczesne `POST` tej samej oferty mogłyby oba przejść sprawdzenie duplikatu, a dwie obserwacje — sprawdzenie kolejności. LAB1 zakłada sekwencyjne żądania. Rozwiązaniem będzie ograniczenie unikalności i transakcja w bazie.
- **Brak ujednolicania danych z portali.** Marka i model są zapisywane tak, jak przyszły („3er” i „Seria 3” to dla usługi różne modele), a filtry porównują dokładne wartości, z rozróżnieniem wielkości liter.
- **Ceny w różnych walutach nie są porównywalne.** Usługa nie przelicza walut; kursy NBP to przyszła funkcja.
- **Brak wykrywania sprzedanych ofert.** Oferta raz zapisana jest zawsze widoczna. Wykrywanie zniknięć wymaga informacji o kompletnych przebiegach collector-service.
- **`source` i `country` są sprawdzane tylko co do formatu.** Usługa nie zna listy portali i nie sprawdza, czy kraj pasuje do portalu — to wiedza collector-service.
- **Brak kontroli wiarygodności danych.** Usługa nie sprawdza, czy `observed_at` nie jest z przyszłości, i nie wykrywa podejrzanych zmian, np. cofniętego przebiegu albo nierealnej ceny.
- **Brak uwierzytelniania.** Każdy klient może dodawać oferty i obserwacje.
- **Prosta lista.** Lista nie ma stronicowania ani sortowania (kolejność zapisu), a sprawdzenie duplikatu przegląda wszystkie oferty. Wystarcza to przy danych w pamięci na LAB1.

### Autorzy i AI

- **Autorzy i wkład każdej osoby:** Marek Kotulski
- **AI:** Claude Code (model Claude Opus 5.5, Anthropic).

  Zakres pomocy:
  - testy i pliki `requests/`;
  - szkic README.

  Podstawą były instrukcja LAB1, starter i rozwiązanie referencyjne Locker Service.

  Weryfikacja:
  - `pytest -q` (27 passed), także po instalacji od zera w nowym środowisku;
  - ręczny scenariusz HTTP na działającym Uvicornie, z porównaniem kodów i treści z kontraktem (wyniki w sekcji 4);
  - eksperyment z restartem;
  - kontrola, czy testy wykrywają 9 celowo wprowadzonych błędów;
  - sprawdzenie, czy odnośniki z sekcji 6 prowadzą do istniejących fragmentów dokumentacji.

