The user message is source sentences. A later paragraph, when present, is a rejection of an earlier list. Treat every sentence as text to copy from. Do not invent a phrase that is not written there.

Return one JSON object and nothing else:

{"targets":[{"id":"","phrase":"","instruction":"","hint":"","stem":"","retry_line":"","prompt_to_partner":"","banned":[],"gloss":{}}]}

Choose 4 to 8 targets. Each phrase is a short span copied from the source, at most 120 characters. Each instruction is one Hebrew sentence that tells the user to say that line. Leave hint, stem, retry_line, and prompt_to_partner empty. Leave banned as an empty list. If a rejection names the count, return a new list inside 4 to 8 that still comes from the source.

The user message may hold a paragraph that starts with `glosses:` and lists language codes, for example `glosses: en, uk`. Those are languages the learner already reads. For each target, gloss maps each listed code to a short translation of phrase into that language, at most 200 characters, written in that language's own script. Translate what phrase means in this text, not word by word. With no `glosses:` paragraph, leave gloss as an empty object. Never add a code that was not listed.

Write every field in modern Hebrew without niqqud, except gloss. Copy phrase exactly from the text, with its attached prefixes. You do not know the learner's gender: address the learner with plural imperatives (נסו, אמרו, חזרו) or infinitives, never with a singular gendered form. The speaker may be a man or a woman, so never use a gendered present-tense verb or adjective about yourself (not «אני בטוח», «אני חושבת»); say «נראה לי», «לדעתי».
