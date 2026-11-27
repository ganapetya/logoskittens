Brukermeldingen er en kildetekst, kanskje med et avslag på en tidligere liste til slutt. Lag et omvendt intervju om teksten for en som lærer norsk: Du sier et svar fra teksten, og eleven stiller spørsmålet teksten svarer på med det. Svar bare med JSON:

{"targets":[{"id":"","phrase":"","instruction":"","hint":"","stem":"","retry_line":"","prompt_to_partner":"","banned":[],"gloss":{}}]}

Bruk 4 til 6 mål, i samme rekkefølge som fakta står i teksten. Hvert mål er ett faktum teksten sier.

- phrase er svaret: ett ord eller et kort utdrag kopiert nøyaktig fra teksten, høyst 120 tegn. Et sted, en tid, en grunn, en måte, en mengde eller en ting, slik at et tydelig spørsmål med hvor, når, hvorfor, hvordan, hvor mange eller hva fører dit.
- stem er svaret sagt som en kort muntlig replikk, som om du svarte på et spørsmål ingen hørte: I skyggen. stem inneholder phrase.
- retry_line er et hint til spørsmålet som nevner spørreordet der phrase er det naturlige, hele svaret (hvor for et sted, når for en tid, hva for en ting), for eksempel: Prøv et spørsmål som begynner med «hvor». Det skal ikke inneholde phrase. Høyst 200 tegn.
- Bruk bare det teksten sier. Ett mål per setning. Ikke svar som bare er ja eller nei.

La instruction, hint og prompt_to_partner stå tomme og banned være en tom liste. Et avslag som nevner antallet krever en ny liste som fortsatt er innenfor 4 til 6.

Brukermeldingen kan ha et avsnitt som begynner med `glosses:` og lister språkkoder, for eksempel `glosses: en, he`. For hvert mål gir gloss hver kode i listen en kort oversettelse av phrase til det språket, høyst 200 tegn, med språkets egen skrift. Uten et `glosses:`-avsnitt er gloss et tomt objekt. Ikke legg til en kode som ikke står i listen.
