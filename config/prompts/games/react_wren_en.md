The user message is a source text, possibly followed by a rejection of an earlier list. Build a reaction game about that text for someone learning English: you say something with feeling, and the learner reacts with a reaction chunk the text itself uses. Return JSON only:

{"targets":[{"id":"","phrase":"","instruction":"","hint":"","stem":"","retry_line":"","prompt_to_partner":"","banned":[],"forms":[],"emotion":"","mimic":"","gloss":{}}]}

Use 3 to 6 targets, in text order. Use only reactions the text really contains: a chunk that shows a feeling or a stance, such as `that sounds lovely`, `I still think about`, `what a relief`. If the text holds fewer than 3, return only those; do not invent any.

- phrase is the reaction chunk copied exactly from the text, two to six words, at most 120 characters.
- forms are up to 6 other forms of it a learner may say correctly: another tense or person, with or without the article. Never a synonym.
- stem is your spoken line, with feeling, that calls for this reaction. It must not contain phrase or a form.
- instruction names the situation for the card in one short English sentence, without phrase or a form: She is excited about the trip.
- retry_line says your line again with a small clue, at most 200 characters, without phrase or a form.
- emotion is one of: neutral, curiosity, amusement, encouragement. It is how you sound.
- mimic is one of: agreement, disagreement, frustration, curiosity. It is what your body shows.

Leave hint and prompt_to_partner empty and banned as an empty list. A rejection that names the count needs a new list still inside 3 to 6, or as many real reactions as the text has.

The user message may hold a paragraph that starts with `glosses:` and lists language codes, for example `glosses: en, he`. For each target, gloss maps each listed code to a short translation of phrase into that language, at most 200 characters, in that language's own script. With no `glosses:` paragraph, gloss is an empty object. Never add a code that was not listed.
