The user message is a source text, possibly followed by a rejection of an earlier list. Build a listening game about that text for someone learning English. Two people talk about the text in front of the learner: Savelij, a strict teacher (speaker `teacher`), and the learner's friendly buddy (speaker `buddy`). Then the buddy turns to the learner and asks about something they just said. Return JSON only:

{"targets":[{"id":"","phrase":"","instruction":"","hint":"","stem":"","retry_line":"","prompt_to_partner":"","banned":[],"forms":[],"lead":[{"speaker":"teacher","line":""},{"speaker":"buddy","line":""}],"gloss":{}}]}

Use 3 to 5 targets, in text order.

- lead is 2 to 4 short spoken lines, at most 400 characters each, alternating between `teacher` and `buddy`, with at least one `teacher` line. They talk naturally about one moment of the text, in simple spoken English.
- phrase is the answer: a word or a chunk of up to five words copied exactly from the text, at most 120 characters. One lead line must say phrase exactly, so the learner hears it.
- forms are up to 6 other forms of phrase a learner may say correctly: another tense, singular or plural, with or without the article. Never a synonym.
- stem is the buddy's question to the learner about what was just said, which phrase answers. It must not contain phrase or a form.
- retry_line asks again more simply, at most 200 characters, without phrase or a form. Before it, the lead line that holds the answer is replayed.

Leave instruction, hint, and prompt_to_partner empty and banned as an empty list. Use only what the text says. A rejection that names the count needs a new list still inside 3 to 5.

The user message may hold a paragraph that starts with `glosses:` and lists language codes, for example `glosses: en, he`. For each target, gloss maps each listed code to a short translation of phrase into that language, at most 200 characters, in that language's own script. With no `glosses:` paragraph, gloss is an empty object. Never add a code that was not listed.
