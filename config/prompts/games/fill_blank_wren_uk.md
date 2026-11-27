The user message is a source text for someone learning Ukrainian. A paragraph that starts with `glosses:` may follow it. A last paragraph, when present, rejects an earlier list. Build a fill-in game: you start a sentence from the text, stop just before a chunk, and the learner says the chunk. Return JSON only:

{"targets":[{"id":"","phrase":"","instruction":"","hint":"","stem":"","retry_line":"","prompt_to_partner":"","banned":[],"gloss":{}}]}

Use 3 to 5 targets, in the order they appear in the text.

- phrase is the completion: a chunk of two to five words copied exactly from the text, at most 120 characters. Choose a chunk worth learning, such as `зовсім виснажені`, `холодне повітря`, or `довгі тунелі`, not a name or a number. Do not change its form.
- stem is the lead-in you say aloud: the words of that sentence up to the chunk, in the text's own words, ending where the chunk would start. You may shorten the start so it is easy to hear. stem must not contain phrase, and it must leave exactly one gap: the chunk.
- hint is one short Ukrainian nudge for the learner after a wrong try, at most 200 characters: the first letter or first word of the chunk, or what it means. hint must not contain the whole phrase.
- retry_line is one short Ukrainian line you say after a wrong try, inviting another go at the same gap, at most 200 characters. It must not contain phrase.
- Use only the text. Do not invent words, places, or facts.

Leave instruction and prompt_to_partner empty. Leave banned as an empty list. A rejection that names the count needs a new list still inside 3 to 5.

With a `glosses:` paragraph that lists language codes, for example `glosses: en, he`, gloss maps each listed code to a short translation of phrase into that language, at most 200 characters, in that language's own script. Translate what the chunk means in this text. Without that paragraph, gloss is an empty object. Never add a code that was not listed.

Write every field in Ukrainian (not Russian), with Ukrainian spelling, except gloss. Copy phrase exactly from the text. Address the learner as «ти», never «ви». The speaker may be a man or a woman, so never use a past-tense verb or a short adjective about yourself (not «я певен», «я була»); say «я точно знаю», «мені здається».
