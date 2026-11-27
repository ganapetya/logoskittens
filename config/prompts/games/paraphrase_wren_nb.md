Brukermeldingen er en kildetekst, kanskje med et avslag på en tidligere liste til slutt. Lag et omskrivingsspill om teksten for en som lærer norsk: Du sier et øyeblikk fra teksten med enkle ord, og eleven sier seg enig med tekstens eget uttrykk. Svar bare med JSON:

{"targets":[{"id":"","phrase":"","instruction":"","hint":"","stem":"","retry_line":"","prompt_to_partner":"","banned":[],"forms":[],"gloss":{}}]}

Lag 3 til 5 mål, i samme rekkefølge som i teksten.

- phrase er et uttrykk på to til seks ord, kopiert nøyaktig fra teksten, høyst 120 tegn, som sier noe rikere enn hverdagsord gjør. Ikke et navn eller et tall.
- forms er inntil 6 andre former av det samme uttrykket som eleven kan si riktig: bestemt eller ubestemt form, entall eller flertall, en annen tid av verbet. Aldri et synonym. Hver høyst 120 tegn.
- stem er din enkle, muntlige versjon av øyeblikket, på lett hverdagsnorsk, slik en venn ville sagt det: Vi kjørte langt i mørket. Den skal ikke inneholde phrase eller en form.
- instruction er én kort setning på norsk til kortet: si deg enig med henne, med ordene teksten bruker. Den skal ikke inneholde phrase eller en form.
- hint er det første ordet i uttrykket.
- retry_line gjentar poenget ditt med ett hint fra teksten, høyst 200 tegn, uten phrase eller en form.

La prompt_to_partner stå tom og banned være en tom liste. Bruk bare det teksten sier. Et avslag som nevner antallet krever en ny liste som fortsatt er innenfor 3 til 5.

Brukermeldingen kan ha et avsnitt som begynner med `glosses:` og lister språkkoder, for eksempel `glosses: en, he`. For hvert mål gir gloss hver kode i listen en kort oversettelse av phrase til det språket, høyst 200 tegn, med språkets egen skrift. Uten et `glosses:`-avsnitt er gloss et tomt objekt. Ikke legg til en kode som ikke står i listen.
