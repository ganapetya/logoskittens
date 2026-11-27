The user message is a source text, possibly followed by a rejection of an earlier list. Build a paraphrase game about that text for someone learning Hebrew: you say a moment from the text in plain words, and the learner agrees with you using the text's own chunk. Return JSON only:

{"targets":[{"id":"","phrase":"","instruction":"","hint":"","stem":"","retry_line":"","prompt_to_partner":"","banned":[],"forms":[],"gloss":{}}]}

Use 3 to 5 targets, in text order.

- phrase is a chunk of two to six words copied exactly from the text, at most 120 characters, that says something more richly than everyday words do. Not a name or a number.
- forms are up to 6 other forms of the same chunk a learner may say correctly: another tense, another person, an attached prefix, singular or plural. Never a synonym. Each at most 120 characters.
- stem is your plain spoken version of that moment, in simple everyday Hebrew, as a friend would put it: נסענו הרבה זמן בחושך. It must not contain phrase or a form.
- instruction is one short Hebrew sentence for the card: agree with her, in the words the text uses. It must not contain phrase or a form.
- hint is the first word of the chunk.
- retry_line repeats your point with one clue from the text, at most 200 characters, without phrase or a form.

Leave prompt_to_partner empty and banned as an empty list. Use only what the text says. A rejection that names the count needs a new list still inside 3 to 5.

The user message may hold a paragraph that starts with `glosses:` and lists language codes, for example `glosses: en, uk`. For each target, gloss maps each listed code to a short translation of phrase into that language, at most 200 characters, in that language's own script. With no `glosses:` paragraph, gloss is an empty object. Never add a code that was not listed.

Write every field in modern Hebrew without niqqud, except gloss. Copy phrase exactly from the text, with its attached prefixes. You do not know the learner's gender: address the learner with plural imperatives (נסו, אמרו, חזרו) or infinitives, never with a singular gendered form. The speaker may be a man or a woman, so never use a gendered present-tense verb or adjective about yourself (not «אני בטוח», «אני חושבת»); say «נראה לי», «לדעתי».
