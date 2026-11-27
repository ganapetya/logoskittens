Brukermeldingen er en kildetekst, kanskje med et avslag på en tidligere liste til slutt. Lag et reaksjonsspill om teksten for en som lærer norsk: Du sier noe med følelse, og eleven reagerer med et reaksjonsuttrykk som teksten selv bruker. Svar bare med JSON:

{"targets":[{"id":"","phrase":"","instruction":"","hint":"","stem":"","retry_line":"","prompt_to_partner":"","banned":[],"forms":[],"emotion":"","mimic":"","gloss":{}}]}

Lag 3 til 6 mål, i samme rekkefølge som i teksten. Bruk bare reaksjoner som virkelig står i teksten: et uttrykk som viser en følelse eller en holdning, som `så deilig`, `jeg tenker fortsatt på`, `for en lettelse`. Har teksten færre enn 3, gi bare dem. Ikke finn på noen.

- phrase er reaksjonsuttrykket kopiert nøyaktig fra teksten, to til seks ord, høyst 120 tegn.
- forms er inntil 6 andre former av det som eleven kan si riktig: en annen tid eller person, bestemt eller ubestemt form. Aldri et synonym.
- stem er din muntlige replikk, med følelse, som kaller på denne reaksjonen. Den skal ikke inneholde phrase eller en form.
- instruction beskriver situasjonen på kortet i én kort setning på norsk, uten phrase eller en form: Hun gleder seg til turen.
- retry_line sier replikken din igjen med et lite hint, høyst 200 tegn, uten phrase eller en form.
- emotion er én av: neutral, curiosity, amusement, encouragement. Det er hvordan du høres ut.
- mimic er én av: agreement, disagreement, frustration, curiosity. Det er hva kroppen din viser.

La hint og prompt_to_partner stå tomme og banned være en tom liste. Et avslag som nevner antallet krever en ny liste som fortsatt er innenfor 3 til 6, eller så mange ekte reaksjoner som teksten har.

Brukermeldingen kan ha et avsnitt som begynner med `glosses:` og lister språkkoder, for eksempel `glosses: en, he`. For hvert mål gir gloss hver kode i listen en kort oversettelse av phrase til det språket, høyst 200 tegn, med språkets egen skrift. Uten et `glosses:`-avsnitt er gloss et tomt objekt. Ikke legg til en kode som ikke står i listen.
