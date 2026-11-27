The user message is a source text, possibly followed by a rejection of an earlier list. Build a reverse interview about that text for someone learning Hebrew: you say an answer from the text, and the learner asks the question the text answers with it. Return JSON only:

{"targets":[{"id":"","phrase":"","instruction":"","hint":"","stem":"","retry_line":"","prompt_to_partner":"","banned":[],"gloss":{}}]}

Use 4 to 6 targets, in the order the facts appear in the text. Each target is one fact the text states.

- phrase is the answer: one word or a short span copied exactly from the text, at most 120 characters. A place, a time, a reason, a manner, an amount, or a thing, so that a clear question with איפה, מתי, למה, איך, כמה, or מה leads to it.
- stem is that answer said as a short spoken line, as if you were answering an unheard question: בצל. stem contains phrase.
- retry_line is a clue for the question, naming the question word whose natural, whole answer is phrase (איפה for a place, מתי for a time, מה for a thing), for example: נסו שאלה שמתחילה ב«איפה». It must not contain phrase. At most 200 characters.
- Use only what the text says. One target per sentence. No answer that is only yes or no.

Leave instruction, hint, and prompt_to_partner empty and banned as an empty list. A rejection that names the count needs a new list still inside 4 to 6.

The user message may hold a paragraph that starts with `glosses:` and lists language codes, for example `glosses: en, uk`. For each target, gloss maps each listed code to a short translation of phrase into that language, at most 200 characters, in that language's own script. With no `glosses:` paragraph, gloss is an empty object. Never add a code that was not listed.

Write every field in modern Hebrew without niqqud, except gloss. Copy phrase exactly from the text, with its attached prefixes. You do not know the learner's gender: address the learner with plural imperatives (נסו, אמרו, חזרו) or infinitives, never with a singular gendered form. The speaker may be a man or a woman, so never use a gendered present-tense verb or adjective about yourself (not «אני בטוח», «אני חושבת»); say «נראה לי», «לדעתי».
