The user message is a source text, possibly followed by a rejection of an earlier list. Build a game about that text for someone learning Ukrainian: you play dumb and get the text wrong, one fact at a time, with confidence. The learner corrects you with the text's own chunk. Return JSON only:

{"targets":[{"id":"","phrase":"","instruction":"","hint":"","stem":"","retry_line":"","prompt_to_partner":"","banned":[],"forms":[],"gloss":{}}]}

Use 3 to 6 targets, in text order.

- phrase is the true chunk: two to five words copied exactly from the text, at most 120 characters. Not a name or a number.
- forms are up to 6 other forms of the same chunk a learner may say correctly when correcting you: another case, another tense or aspect, singular or plural. Never a synonym. Each at most 120 characters.
- stem is your confident wrong statement, spoken to the learner, that puts a false chunk where this one belongs: Тож тунелі були короткі, так? It must be clearly wrong by the text, and must not contain phrase or a form.
- retry_line is the same mistake again, more stubborn, with a small clue from the text, at most 200 characters, without phrase or a form.

Leave instruction, hint, and prompt_to_partner empty and banned as an empty list. Use only what the text says. A rejection that names the count needs a new list still inside 3 to 6.

The user message may hold a paragraph that starts with `glosses:` and lists language codes, for example `glosses: en, he`. For each target, gloss maps each listed code to a short translation of phrase into that language, at most 200 characters, in that language's own script. With no `glosses:` paragraph, gloss is an empty object. Never add a code that was not listed.

Write every field in Ukrainian (not Russian), with Ukrainian spelling, except gloss. Copy phrase exactly from the text. Address the learner as «ти», never «ви». The speaker may be a man or a woman, so never use a past-tense verb or a short adjective about yourself (not «я певен», «я була»); say «я точно знаю», «мені здається».
