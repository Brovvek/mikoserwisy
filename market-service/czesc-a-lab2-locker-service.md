# LAB2 — część A: persystencja i cache na przykładzie paczkomatu

Odpowiedzi na pytania z sekcji 1.1 („Analiza odpowiedzialności za dane”) i sekcji 4 („Analiza skutków niedostępności cache”) instrukcji LAB2 oraz wyniki uruchomienia kodu pomocniczego (`demo.py`). Własna usługa jest opisana w [README.md](README.md), w sekcji 8.

## Analiza odpowiedzialności za dane

**1. Co dzieje się ze zmianą statusu skrytki po restarcie wersji z LAB1?**
Zmiana znika. Stan skrytek żył w słowniku w pamięci procesu, więc po restarcie wracają dane początkowe. Skrytka, w której leży paczka, znów jest `free` i może zostać przydzielona drugiej paczce. To ten sam efekt, który market-service pokazał w eksperymencie z restartem LAB1: znikała oferta 4 i historia cen.

**2. Która usługa powinna zapisywać stan skrytki?**
Wyłącznie Locker Service, bo to ona pilnuje reguły przejść statusów (free → reserved → occupied → free). Parcel Service czy Delivery Service proszą o rezerwację albo zajęcie skrytki przez API Locker Service i nie piszą do jej tabel. Gdyby pisały bezpośrednio, mogłyby ominąć regułę.

**3. Czy historia paczki należy do tych samych danych?**
Nie. Historia paczki (nadanie, transport, odbiór) należy do Tracking Service albo Parcel Service. Locker Service zna tylko stan skrytki i co najwyżej identyfikator rezerwacji. Historia paczki zmienia się z innych powodów, ma innego właściciela i inny czas życia: skrytka jest zwalniana, a historia przesyłki zostaje.

**4. Czy nieaktualny opis paczkomatu ma te same konsekwencje co nieaktualna informacja o wolnej skrytce?**
Nie.

- **Opis paczkomatu** (nazwa, adres, miasto) zmienia się rzadko. Stara nazwa pokazywana jeszcze przez TTL to drobna niedogodność, więc to dobry kandydat do cache.
- **Informacja o wolnej skrytce** zmienia się często. Decyzja podjęta na starej kopii może przydzielić tę samą skrytkę dwóm paczkom. O przydziale musi decydować baza, w transakcji, z aktualnym stanem. Cache może najwyżej podpowiadać orientacyjną liczbę wolnych skrytek.

## Uruchomienie przykładu

Środowisko: Windows 10, PowerShell, Python 3.14.0, SQLAlchemy 2.0.55, redis-py 6.4.0, Redis 7 w Dockerze (`docker run --name lab2-redis -p 127.0.0.1:6379:6379 -d redis:7-alpine`, `docker exec lab2-redis redis-cli ping` → `PONG`). Wykonano 2026-10-26 w katalogu kodu pomocniczego, z konfiguracją:

```powershell
$env:DATABASE_URL = 'sqlite:///./demo.db'
$env:CACHE_PREFIX = 'lab2:mkotulski:demo'
$env:CACHE_TTL_SECONDS = '60'
$env:REDIS_URL = 'redis://localhost:6379/0'
```

Testy paczki: `8 passed`.

**Krok 1 — zapis i odczyt.** `seed`, `get`, `get` — każde polecenie to nowy proces:

```
{'id': 'KRK-1024', 'name': 'Krakow Galeria', 'address': 'ul. Dluga 10', 'city': 'Krakow', 'status': 'online'}
MISS {'id': 'KRK-1024', 'name': 'Krakow Galeria', ...}
HIT {'id': 'KRK-1024', 'name': 'Krakow Galeria', ...}
```

**Krok 2 — zmiana i unieważnienie.** `rename --name 'Nowa Nazwa'`, `get`, `get`:

```
cache_invalidated= True {'id': 'KRK-1024', 'name': 'Nowa Nazwa', ...}
MISS {'id': 'KRK-1024', 'name': 'Nowa Nazwa', ...}
HIT {'id': 'KRK-1024', 'name': 'Nowa Nazwa', ...}
```

**Krok 3 — TTL i awaria.**

1. Sprawdzenie TTL: `docker exec lab2-redis redis-cli TTL $demoKey` → `57`.
2. Po `docker stop lab2-redis`:
   - `get` → `BYPASS` z nazwą z bazy (`Nowa Nazwa`) i ostrzeżenie `Cache unavailable; reading database`;
   - `rename --name 'Zapis bez cache'` → `cache_invalidated= False`, zapis w bazie zatwierdzony, ostrzeżenie `Invalidation failed; old value may survive until TTL`.
3. Po `docker start lab2-redis` (PING → `PONG`) `get` zwrócił **`HIT {'name': 'Nowa Nazwa'}`**, choć w bazie jest już `Zapis bez cache`. Redis 7 zapisał przy zatrzymaniu migawkę RDB i po starcie ją wczytał. Wpis nie zginął, więc stara wartość wróciła. Zatrzymanie serwera nie gwarantuje ani zachowania, ani utraty wpisów.

**Stara wartość po nieudanym unieważnieniu**, przy działającym Redis i odłączonym kliencie (scenariusz z instrukcji). Zamiast TTL 300 s użyto **20 s**, żeby w tym samym przebiegu doczekać wygaśnięcia wpisu:

```
rename 'Przed awaria'         -> cache_invalidated= True
get                           -> MISS  'Przed awaria'      (wypełnia cache)
REDIS_URL=redis://127.0.0.1:9999/0
get                           -> BYPASS 'Przed awaria'
rename 'Po awarii'            -> cache_invalidated= False  (zapis w bazie zatwierdzony)
REDIS_URL przywrócony
get                           -> HIT   'Przed awaria'      <- stara wartość z cache
TTL klucza                    -> 13
po 21 s: TTL klucza           -> -2 (brak klucza)
get                           -> MISS  'Po awarii'         <- aktualna wartość z bazy
```

## Analiza skutków niedostępności cache

**1. Dlaczego dane przetrwały uruchomienie nowego procesu?**
Rekord został zatwierdzony (`commit`) w pliku `demo.db`. Każde polecenie `demo.py` to osobny proces, który otwiera ten sam plik. Pamięć poprzedniego procesu nie jest potrzebna. Wpis cache też przetrwał, bo Redis jest osobnym procesem, stąd HIT w drugim wywołaniu `get`.

**2. Co pokazuje HIT, a czego nie dowodzi o wydajności?**
HIT pokazuje, że odpowiedź pochodzi z kopii w Redis i aplikacja nie wykonała odczytu z bazy. W testach widać to po liczniku wywołań repozytorium. HIT nie dowodzi, że odpowiedź była szybsza: odczyt jednego rekordu z lokalnego pliku SQLite może trwać krócej niż zapytanie sieciowe do Redis z deserializacją JSON. HIT nie dowodzi też, że kopia jest aktualna (punkt 5). O wydajności rozstrzyga dopiero pomiar.

**3. Dlaczego błąd zapisu nie powinien zatwierdzić części danych?**
Zmiana ma sens tylko w całości. Częściowy zapis zostawia stan, którego żadna reguła nie przewiduje. W paczkomacie byłaby to np. skrytka zajęta bez przypisanej rezerwacji. W market-service — nowa cena bez punktu w historii albo przesunięte `last_seen_at` bez nowej ceny. Klient dostaje błąd i ponawia żądanie, a częściowo zapisany stan sprawiłby, że ponowienie zostałoby błędnie odrzucone albo zdublowane. Dlatego zmiana jest jedną transakcją: `sessions.begin()` zatwierdza ją przy poprawnym wyjściu z bloku, a wyjątek ją wycofuje (`test_duplicate_rolls_back`).

**4. Dlaczego obsługujemy awarię GET, SET i DELETE w Redis?**
Każda z tych operacji to osobne wywołanie sieciowe i każda może zawieść niezależnie, np. Redis przestanie odpowiadać między GET a SET. Cache jest opcjonalny, więc żadna jego awaria nie może dać błędu 500 przy sprawnej bazie:

- nieudany **GET** → odczyt z bazy (BYPASS);
- nieudany **SET** → odpowiedź z bazy bez zapisania kopii;
- nieudany **DELETE** → zmiana jest już zatwierdzona w bazie i nie wolno jej cofać ani zgłaszać jako błąd.

Krótkie timeouty (0,3 s) i brak ponowień sprawiają, że niedostępny Redis nie wydłuża też każdego żądania.

**5. Co grozi po nieudanym unieważnieniu?**
Stara kopia zostaje w Redis i jest zwracana jako HIT, mimo że baza ma już nową wartość. Trwa to do wygaśnięcia TTL albo do następnego udanego unieważnienia. Pokazały to oba eksperymenty powyżej (`Przed awaria` mimo `Po awarii` w bazie; `Nowa Nazwa` po restarcie Redis). TTL jest więc górną granicą nieaktualności tylko wtedy, gdy wpis ma ustawiony termin wygaśnięcia. Z tego powodu przez cache nie podejmuje się decyzji, które muszą opierać się na aktualnym stanie, np. przydziału ostatniej skrytki.
