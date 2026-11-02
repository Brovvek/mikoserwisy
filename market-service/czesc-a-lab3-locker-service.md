# LAB3 — część A: Eureka na przykładzie paczkomatu

Odpowiedzi na pytania z sekcji 5 instrukcji LAB3 („Analiza przykładu przed implementacją”) oraz wyniki uruchomienia przykładu z paczki `lab3-support`. Własne usługi są opisane w [README.md](README.md), w sekcji 9.

## Analiza przykładu

**1. Jakie informacje wysyła usługa podczas rejestracji?**
Nazwę logiczną (`app`, np. `LOCKER-SERVICE`), identyfikator instancji (`127.0.0.1:locker-service:8101`), nazwę hosta (`localhost`), adres IP (`127.0.0.1`), port, status (`UP`), dane dzierżawy (`renewalIntervalInSecs` 30, `durationInSecs` 90) oraz adresy pomocnicze, np. `healthCheckUrl`. Pola widać w `EurekaClient.__parepare_instance_info` biblioteki `py-eureka-client` 0.13.3. Danych paczkomatów w zgłoszeniu nie ma.

**2. Po co klient wysyła heartbeat?**
Odnawia dzierżawę, czyli potwierdza rejestrowi, że instancja nadal istnieje. Bez odnowienia rejestr może po pewnym czasie usunąć wpis. W tej bibliotece ten sam wątek co 30 s pobiera też zmiany rejestru do lokalnej kopii. Heartbeat dowodzi tylko, że działa klient rejestru, a nie że endpoint biznesowy odpowiada poprawnie.

**3. Który adres jest konfiguracją, a który jest pobierany z rejestru?**
Konfiguracją jest adres Eureki (`EUREKA_SERVER_URL`) i dane własnej instancji (`SERVICE_PORT`, `INSTANCE_IP`, `INSTANCE_HOST`). Adres `LOCKER-SERVICE` jest pobierany z lokalnej kopii rejestru. W kodzie `PARCEL-SERVICE` występuje tylko nazwa logiczna i ścieżka.

**4. Czy żądanie biznesowe przechodzi przez Eurekę?**
Nie. `do_service()` wybiera adres z lokalnej kopii rejestru, a żądanie HTTP idzie bezpośrednio do instancji. Eureka zna adresy, a nie dane i nie pośredniczy w ruchu.

**5. Która usługa jest właścicielem informacji o paczkomacie?**
`LOCKER-SERVICE`. `PARCEL-SERVICE` odczytuje je przez API i niczego nie zapisuje.

**6. Co zwraca `PARCEL-SERVICE`, gdy `LOCKER-SERVICE` nie odpowie?**
`503` z `{"detail": "Locker Service is unavailable"}`. Dotyczy to braku instancji, braku połączenia i timeoutu. Jej własny `/health` nadal daje `200`.

**7. Czy dwie instancje `LOCKER-SERVICE` spełniają wymóg dwóch różnych usług?**
Nie. To dwa procesy jednej usługi, z tą samą odpowiedzialnością i tymi samymi danymi. Dwie usługi to dwie odpowiedzialności, dwie nazwy i osobni właściciele danych.

**8. Dlaczego brak paczkomatu powinien dawać inny wynik niż brak połączenia z usługą?**
Bo oznaczają co innego i wymagają innej reakcji. `404` to odpowiedź usługi: tego paczkomatu nie ma, a ponawianie niczego nie zmieni. `503` znaczy, że odpowiedzi nie udało się uzyskać: paczkomat może istnieć, więc można spróbować później. Gdyby brak połączenia też dawał `404`, chwilowa awaria wyglądałaby jak brak danych, a nadawca mógłby np. odrzucić poprawną paczkę.

## Uruchomienie przykładu

Środowisko: Windows 10, Python 3.14.0, `py-eureka-client` 0.13.3, Docker Desktop 29.2.1 (`docker compose up --build -d eureka`). Wykonano 2026-11-02 w katalogu `temps/lab3-support`. Testy paczki: `6 passed`.

| Żądanie | Wynik |
|---|---|
| Rejestr po starcie obu usług | `LOCKER-SERVICE` i `PARCEL-SERVICE`: `localhost/127.0.0.1:8101` i `:8102`, `UP` |
| `GET :8101/lockers/KRK-1024` | `200`, rekord `KRK-1024` z polami z LAB1 |
| `GET :8102/delivery-check/KRK-1024` | `200`, `{"destination":"KRK-1024","locker":{"id":"KRK-1024",...}}` |
| `GET :8102/delivery-check/UNKNOWN` | `404`, `{"detail":"Destination locker not found"}` |
| Po zatrzymaniu `LOCKER-SERVICE` | `503`, `{"detail":"Locker Service is unavailable"}`; `/health` usługi `PARCEL-SERVICE` daje `200` |
| Po ponownym uruchomieniu `LOCKER-SERVICE` | `200` z danymi przy pierwszym żądaniu po starcie |

Bezpośrednio po zatrzymaniu `LOCKER-SERVICE` odczyt `/eureka/apps` nadal pokazywał ją jako `UP`, a żądanie i tak dało `503`. To przykład z instrukcji: stan w rejestrze nie jest dowodem, że proces odpowiada.
