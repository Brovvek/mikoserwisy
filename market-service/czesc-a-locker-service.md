# LAB1 — część A: Locker Service (przykład wspólny)

Odpowiedzi na pytania z sekcji 1.1 („Pytania kontrolne przed kodowaniem”) i sekcji 4 („Pytania po przykładzie”) instrukcji LAB1. Dotyczą wspólnego przykładu systemu paczkomatów. Własna usługa jest opisana w [README.md](README.md).

Podstawą odpowiedzi są instrukcja LAB1 i opis rozwiązania referencyjnego (PDF). Kodu rozwiązania referencyjnego nie było w otrzymanych materiałach, dlatego scenariusza na porcie 8000 nie uruchomiono. Te same mechanizmy sprawdzono na własnej usłudze:

- 404 zamiast pustego 200;
- 409 bez zmiany stanu przy niedozwolonej operacji;
- 422 przy nieznanej wartości ze słownika (w market-service: paliwo spoza listy);
- utrata zmian po restarcie.

## Pytania kontrolne przed kodowaniem

**1. Za jaki konkretny problem biznesowy odpowiada Locker Service?**
Odpowiada za wiedzę, które skrytki w których paczkomatach są wolne, zarezerwowane, zajęte albo wyłączone z użytku. Pilnuje też, by zmiana tego stanu przebiegała dozwoloną ścieżką (free → reserved → occupied → free, free ↔ out_of_service). Dzięki temu dwie paczki nie trafią do jednej skrytki, a zepsuta skrytka nie zostanie komuś przydzielona.

**2. Za co nie powinna odpowiadać?**

- konta użytkowników;
- płatności;
- paczki i ich statusy;
- historia przesyłek;
- wysyłanie powiadomień;
- transport i dostawy.

Te dane mają innych właścicieli: Parcel, Tracking, Notification i Delivery Service.

**3. Czy jej odpowiedzialność jest wystarczająco spójna, aby wydzielić ją z systemu?**
Tak. Dotyczy jednego obszaru — dostępności fizycznej infrastruktury, czyli paczkomatów i ich skrytek. Ma jedną główną regułę (przejścia statusów skrytki) i jednego właściciela danych. Zmienia się z innych powodów niż obsługa paczek czy powiadomień, np. przy nowych paczkomatach, nowych rozmiarach skrytek albo awariach urządzeń.

**4. Jakie dane będą należeć do tej usługi?**

- paczkomaty: `id`, `name`, `address`, `city`, `status` (`online`/`offline`);
- skrytki: `id`, `locker_id`, `size` (S/M/L), `status` (`free`, `reserved`, `occupied`, `out_of_service`).

**5. Jakie informacje inne części systemu będą pobierać przez jej API?**
Listę paczkomatów i szczegóły jednego paczkomatu, listę jego skrytek z rozmiarami i statusami, a także wynik zmiany statusu skrytki. Przykładowo Parcel Service sprawdza, czy jest wolna skrytka danego rozmiaru, a potem zleca jej rezerwację lub zajęcie i czeka na potwierdzenie.

**6. Co użytkownik będzie mógł zrobić za pośrednictwem tej usługi?**
Operator albo kurier, a docelowo również inne usługi, mogą:

- przeglądać paczkomaty i ich skrytki;
- dodać paczkomat i skrytkę;
- zmieniać status skrytki: zarezerwować, zająć, zwolnić, wyłączyć z użytku i przywrócić do użytku.

**7. Co stanie się z tą funkcją, jeśli proces usługi przestanie działać?**
Nie da się sprawdzić dostępności skrytek ani zmienić ich stanu. Parcel Service nie potwierdzi więc umieszczenia paczki, a nowe nadania w paczkomatach zostaną wstrzymane. Funkcje niezależne od skrytek, np. historia przesyłek w Tracking Service, mogą działać dalej. Wersja z LAB1 trzyma dane w pamięci, więc po ponownym uruchomieniu wszystkie zmiany statusów znikną i wrócą dane początkowe.

**8. Czy dla tego problemu mikroserwis ma uzasadnienie, czy wystarczyłby moduł monolitu?**
Dla małego systemu wystarczyłby moduł modularnego monolitu. Skrytki i paczki można wtedy obsłużyć w jednej transakcji, bez kosztów sieci.

Osobna usługa ma sens, gdy:

- paczkomaty rozwija osobny zespół;
- odczyty dostępności mają inne obciążenie niż reszta systemu;
- potrzebna jest integracja z urządzeniami w paczkomatach;
- trzeba wdrażać i skalować tę część niezależnie.

Na LAB1 wydzielenie jest uzasadnione dydaktycznie, bo granica odpowiedzialności jest wyraźna.

## Pytania po przykładzie

**1. Dlaczego skrytki należą do Locker Service?**
Skrytki są fizyczną częścią paczkomatu, a ich stan jest głównym przedmiotem odpowiedzialności usługi. Reguła przejść statusów dotyczy właśnie skrytek. Jeden właściciel zapisu gwarantuje, że wszystkie zmiany stanu przechodzą przez tę samą regułę i nie powstają sprzeczne kopie.

**2. Dlaczego historia przesyłek nie powinna być przechowywana w tej usłudze?**
Historia dotyczy paczki, nie skrytki, i ma innego właściciela: Tracking Service. Ma też inny cykl życia: przybywa zdarzeń, nic się nie nadpisuje, a dane przechowuje się długo. Do tego dochodzą inne potrzeby odczytu, np. śledzenie paczki przez klienta. Połączenie obu obszarów poszerzyłoby odpowiedzialność Locker Service i zwiększyło sprzężenie, bo każda zmiana w śledzeniu wymagałaby wdrożenia usługi skrytek.

**3. Co powinno się stać, gdy paczkomat nie istnieje?**
Usługa zwraca 404 z opisem w `detail`, a nie 200 z pustą odpowiedzią. Tak samo dla listy skrytek nieistniejącego paczkomatu. Istniejący paczkomat bez skrytek to co innego: 200 i pusta lista `[]`.

**4. Czy Locker Service musi znać dane użytkownika?**
Nie. Operuje na skrytkach i ich stanach; do powiązania operacji wystarczyłby identyfikator paczki lub operacji. Dane osobowe należą do usługi użytkowników. Ich brak w Locker Service zmniejsza zakres usługi i ilość przetwarzanych danych osobowych.

**5. Czy ta usługa jest już całym systemem paczkomatów?**
Nie. To jedna usługa, odpowiedzialna za dostępność skrytek. System potrzebuje jeszcze m.in.:

- Parcel Service (paczki i ich statusy);
- Tracking Service (historia zdarzeń);
- Notification Service (powiadomienia);
- Delivery Service (transport);
- usługi użytkowników;
- API Gateway;
- komunikacji między usługami przez HTTP i broker zdarzeń.
