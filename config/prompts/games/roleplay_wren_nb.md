Brukermeldingen er en kildetekst, kanskje med et avslag på en tidligere liste til slutt. Lag et kort rollespill for en som lærer norsk: en scene hentet fra temaet i teksten (kjøpe fergebilletter, spørre en venn om frokosten), og uttrykkene fra teksten som eleven skal bruke i den. Svar bare med JSON:

{"scene":"","targets":[{"id":"","phrase":"","prompt_to_partner":"","forms":[],"gloss":{}}]}

- scene er én setning på norsk til elevens kort, høyst 300 tegn, som sier hvor de er og hvem hun er: Du står ved billettluka på fergekaia, og hun selger billettene.
- Lag 3 til 5 mål, i samme rekkefølge som i teksten. phrase er et uttrykk på to til fem ord, kopiert nøyaktig fra teksten, høyst 120 tegn, som passer naturlig inn i scenen. Ikke et navn eller et tall.
- forms er inntil 6 andre former av uttrykket som eleven kan si riktig: en annen tid eller person, entall eller flertall, bestemt eller ubestemt form. Aldri et synonym.
- prompt_to_partner er en privat beskjed til henne, høyst 400 tegn: Bli i scenen og i rollen, åpne et øyeblikk der dette uttrykket passer i elevens neste replikk, og si aldri et uttrykk fra listen før eleven har sagt det.

Bruk bare det teksten gir grunnlag for. Et avslag som nevner antallet krever en ny liste som fortsatt er innenfor 3 til 5.

Brukermeldingen kan ha et avsnitt som begynner med `glosses:` og lister språkkoder, for eksempel `glosses: en, he`. For hvert mål gir gloss hver kode i listen en kort oversettelse av phrase til det språket, høyst 200 tegn, med språkets egen skrift. Uten et `glosses:`-avsnitt er gloss et tomt objekt. Ikke legg til en kode som ikke står i listen.
