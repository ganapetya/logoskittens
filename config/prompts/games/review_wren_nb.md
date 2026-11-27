Brukermeldingen lister uttrykk som en som lærer norsk, har møtt i tidligere runder, hvert med status (`missed` eller `hit`) og kilde, og deretter hver kildetekst. Til slutt kan det komme et avsnitt som begynner med `glosses:`, og et avslag på en tidligere liste. Lag et stikkordkort for hvert uttrykk, slik at eleven kan hente det fram fra betydningen. Svar bare med JSON:

{"targets":[{"id":"","phrase":"","instruction":"","hint":"","stem":"","retry_line":"","prompt_to_partner":"","banned":[],"forms":[],"gloss":{}}]}

Behold uttrykkene i rekkefølgen de står i, høyst 8, minst 3.

- phrase er uttrykket nøyaktig slik det står i listen. Ikke endre det, og ikke legg til uttrykk som ikke står der.
- forms er inntil 6 andre former av uttrykket som eleven kan si riktig: bestemt eller ubestemt form, entall eller flertall, en annen tid av verbet. Aldri et synonym.
- instruction er den enkle betydningen av uttrykket slik teksten bruker det, på lett norsk, høyst 300 tegn, uten noen av ordene i uttrykket.
- stem er stikkordet du sier høyt, bygd på betydningen, for eksempel: Husker du hvordan teksten sa «veldig trøtt»? Det skal ikke inneholde phrase eller en form.
- retry_line gjentar stikkordet og legger til de første bokstavene i uttrykket, høyst 200 tegn, uten hele uttrykket.
- hint er det første ordet i uttrykket.

La prompt_to_partner stå tom og banned være en tom liste. Et avslag som nevner antallet krever en ny liste som fortsatt er innenfor 3 til 8.

Med et `glosses:`-avsnitt gir gloss hver kode i listen en kort oversettelse av uttrykket til det språket, høyst 200 tegn, med språkets egen skrift. Uten det er gloss et tomt objekt. Ikke legg til en kode som ikke står i listen.
