## Etap LAB3 — rejestracja i odnajdywanie usług

### Usługi i granice odpowiedzialności

| Usługa | Odpowiedzialność | Właściciel danych | Nazwa w Eurece | Port |
|---|---|---|---|---:|
| … | … | … | … | … |
| … | … | … | … | … |

### Konfiguracja i uruchomienie

- wersja Pythona i zależności:
- adres Eureka Server:
- konfiguracja każdej instancji:
- komendy uruchomienia i testów:
- wybrany lokalny sposób uruchomienia rejestru (Maven albo Docker):
- połączenie cyklu życia klienta Eureki z zasobami LAB2:

Nie należy zapisywać haseł ani lokalnych sekretów w repozytorium. Adresy, porty i nazwy powinny być zgodne z uruchomionymi procesami.

### Kontrakt komunikacji między usługami

- usługa wywołująca:
- nazwa logiczna odnajdywanej usługi:
- metoda i ścieżka HTTP:
- dane wejściowe i odpowiedź:
- sposób obsługi błędów zależności:
- timeout wywołania:
- diagram rejestracji i żądania biznesowego:

### Wyniki weryfikacji

| Scenariusz | Stan początkowy i żądanie | Oczekiwany wynik | Wynik rzeczywisty | Przywrócenie stanu |
|---|---|---|---|---|
| Rejestracja | Uruchomienie rejestru i obu usług | Obie instancje `UP` | … | … |
| Odnajdywanie | Wywołanie przepływu dla znanego zasobu | `200` z danymi zależnej usługi | … | … |
| Brak zasobu | Wywołanie nieistniejącego ID | `404` | … | … |
| Awaria zależności | Zatrzymanie usługi wywoływanej, ponowienie żądania | `503`; health wywołującej nadal `200` | … | … |
| Przywrócenie zależności | Restart zatrzymanej usługi, odświeżenie rejestru klienta | Ponownie `200` z danymi | … | … |
| Testy automatyczne | `pytest` bez Eureka Server | Testy z atrapą, w tym mapowanie `502` | … | … |

Należy wskazać co najmniej cztery własne testy LAB3 oraz wynik wcześniejszych testów LAB1 i LAB2. Dla odmiennego mapowania błędów należy podać uzasadnienie wynikające z kontraktu.

### Ograniczenia i dokumentacja

- zachowanie po niedostępności usługi lub rejestru:
- obserwacja wpisu po zatrzymaniu usługi i wpływ lokalnej kopii rejestru:
- dwa wykorzystane źródła dokumentacji i sprawdzone wersje:
- problem rozwiązany na podstawie każdego źródła i sposób sprawdzenia:
- sposób weryfikacji sugestii AI:

### Wkład autorów

- osoba 1:
- osoba 2:
