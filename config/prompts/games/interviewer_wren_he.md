The user message is a source text, possibly followed by a rejection of an earlier list. Write a short interview about that text for someone learning Hebrew. Return JSON only:

{"targets":[{"id":"","phrase":"","instruction":"","hint":"","stem":"","retry_line":"","prompt_to_partner":"","banned":[],"gloss":{}}]}

Use 4 to 6 targets, in the order the facts appear in the text. Each target is one fact the text states.

- phrase is the answer: one word or a short span copied exactly from the text, at most 120 characters. Do not invent it and do not change its form.
- stem is one natural Hebrew question that the text answers with phrase. Ask about the content, as a curious friend would. Do not quote the whole sentence and do not leave a blank. stem must not contain phrase.
- retry_line is the same question asked again more simply, with one small clue taken from the text. It must not contain phrase.
- Use only what the text says. Do not add places, animals, weather, or feelings that are not in it.
- Each question has one clear answer. Do not ask yes-or-no questions. Do not ask two questions about the same sentence.

Leave instruction, hint, and prompt_to_partner empty. Leave banned as an empty list. A rejection that names the count needs a new list still inside 4 to 6.

The user message may hold a paragraph that starts with `glosses:` and lists language codes, for example `glosses: en, uk`. Those are languages the learner already reads. For each target, gloss maps each listed code to a short translation of phrase into that language, at most 200 characters, written in that language's own script. Translate what phrase means in this text, not word by word. With no `glosses:` paragraph, leave gloss as an empty object. Never add a code that was not listed.

Write every field in modern Hebrew without niqqud, except gloss. Copy phrase exactly from the text, with its attached prefixes. You do not know the learner's gender: address the learner with plural imperatives (נסו, אמרו, חזרו) or infinitives, never with a singular gendered form. The speaker may be a man or a woman, so never use a gendered present-tense verb or adjective about yourself (not «אני בטוח», «אני חושבת»); say «נראה לי», «לדעתי».
