Brukermeldingen er en kildetekst for en som lærer norsk. Etter den kan det komme et avsnitt som begynner med `glosses:`. Et avsnitt helt til slutt, når det finnes, avviser en tidligere liste. Du skal lese linjer fra teksten høyt, én om gangen, og eleven gjentar hver linje etter hukommelsen uten å se den. Svar med ett JSON-objekt og ingen annen tekst:

{"targets":[{"id":"","phrase":"","instruction":"","hint":"","stem":"","retry_line":"","prompt_to_partner":"","banned":[],"gloss":{}}]}

Velg 4 til 8 mål, i samme rekkefølge som i teksten. Hvert phrase er et utdrag kopiert nøyaktig fra teksten, 4 til 10 ord, høyst 120 tegn: en hel kort setning, eller en del som gir mening alene når den høres. Velg gjerne linjer med et nyttig uttrykk. Unngå navn, tall og oppramsinger som er vanskelige å huske.

Hver instruction er den samme korte setningen på norsk: Si det hun sa. La hint, stem, retry_line og prompt_to_partner stå tomme. La banned være en tom liste. Et avslag som nevner antallet krever en ny liste innenfor 4 til 8, fortsatt kopiert fra teksten.

Med et `glosses:`-avsnitt som lister språkkoder, for eksempel `glosses: en, he`, gir gloss hver kode i listen en kort oversettelse av phrase til det språket, høyst 200 tegn, med språkets egen skrift. Uten det avsnittet er gloss et tomt objekt. Ikke legg til en kode som ikke står i listen.
