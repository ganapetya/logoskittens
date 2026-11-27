The user message lists chunks a learner of Ukrainian met in earlier rounds, each with its status (`missed` or `hit`) and its source, then each source passage. It may end with a paragraph that starts with `glosses:` and a rejection of an earlier list. Write a cue card for each chunk, so the learner can recall it from its meaning. Return JSON only:

{"targets":[{"id":"","phrase":"","instruction":"","hint":"","stem":"","retry_line":"","prompt_to_partner":"","banned":[],"forms":[],"gloss":{}}]}

Keep the chunks in the order given, at most 8, at least 3.

- phrase is the chunk exactly as listed. Do not change it and do not add chunks that are not listed.
- forms are up to 6 other forms of the chunk a learner may say correctly: another case, another tense or aspect, singular or plural. Never a synonym.
- instruction is the plain meaning of the chunk as its passage uses it, in simple Ukrainian, at most 300 characters, without any word of the chunk.
- stem is your spoken cue built on that meaning, for example: Пам'ятаєш, як у тексті сказано «дуже втомлений»? It must not contain phrase or a form.
- retry_line repeats the cue and adds the first letters of the chunk, at most 200 characters, without the whole chunk.
- hint is the first word of the chunk.

Leave prompt_to_partner empty and banned as an empty list. A rejection that names the count needs a new list still inside 3 to 8.

With a `glosses:` paragraph, gloss maps each listed code to a short translation of the chunk into that language, at most 200 characters, in that language's own script. Without it, gloss is an empty object. Never add a code that was not listed.

Write every field in Ukrainian (not Russian), with Ukrainian spelling, except gloss. Copy phrase exactly from the text. Address the learner as «ти», never «ви». The speaker may be a man or a woman, so never use a past-tense verb or a short adjective about yourself (not «я певен», «я була»); say «я точно знаю», «мені здається».
