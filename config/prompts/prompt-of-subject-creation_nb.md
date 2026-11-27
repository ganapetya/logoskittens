Du leser råstoff: setninger en person allerede har lest. Du lager et emnekort til en åpen samtale. Du skriver ikke en leksjon, en prøve eller en fortelling.

Bruk bare det som står i råstoffet. Ikke finn på steder, hendelser eller grunner.

Returner ett JSON-objekt med disse nøklene:
- used_words: liste med innholdsord og korte uttrykk som faktisk står i teksten. Sløyf artikler, hjelpeverb og nakne pronomen. Ingen duplikater. Behold skrivemåten fra teksten.
- significant_words: liste, et utvalg av used_words. Velg de få konkrete ordene samtalen skal komme tilbake til (steder, ting, opplevelser). Sløyf limord.
- important_words: liste med omtrent 6 til 12 innholdsord eller korte uttrykk som står i teksten og er verdt å høre, særlig dem du ikke la i significant_words. Dette er øvingsord sammendraget ikke skal miste. Sløyf limord og alt som allerede står i significant_words. Behold skrivemåten fra teksten.
- theme: én setning som sier hva stoffet handler om. Ingen nye fakta.
- small_talk_subjects: liste med 4 til 7 korte åpninger. Hver åpning er ett spørsmål eller ett frempek en venn kunne sagt. Grunngi hver åpning i temaet og i significant_words.

Skriv kortet på norsk.
