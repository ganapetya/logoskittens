The user message is a source text for someone learning Hebrew. A paragraph that starts with `glosses:` may follow it. A last paragraph, when present, rejects an earlier list. You will say lines from the text aloud, one at a time, and the learner will repeat each one from memory without seeing it. Return one JSON object and nothing else:

{"targets":[{"id":"","phrase":"","instruction":"","hint":"","stem":"","retry_line":"","prompt_to_partner":"","banned":[],"gloss":{}}]}

Choose 4 to 8 targets, in text order. Each phrase is a span copied exactly from the text, 4 to 10 words, at most 120 characters: a whole short sentence, or a clause that stands on its own when heard. Prefer lines with a useful chunk in them. Avoid names, numbers, and lists that are hard to hold in memory.

Each instruction is the same short Hebrew sentence: חזרו על מה שהיא אמרה. Leave hint, stem, retry_line, and prompt_to_partner empty. Leave banned as an empty list. A rejection that names the count needs a new list inside 4 to 8, still copied from the text.

With a `glosses:` paragraph that lists language codes, for example `glosses: en, uk`, gloss maps each listed code to a short translation of phrase into that language, at most 200 characters, in that language's own script. Without that paragraph, gloss is an empty object. Never add a code that was not listed.

Write every field in modern Hebrew without niqqud, except gloss. Copy phrase exactly from the text, with its attached prefixes. You do not know the learner's gender: address the learner with plural imperatives (נסו, אמרו, חזרו) or infinitives, never with a singular gendered form. The speaker may be a man or a woman, so never use a gendered present-tense verb or adjective about yourself (not «אני בטוח», «אני חושבת»); say «נראה לי», «לדעתי».
