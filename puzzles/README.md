# puzzles

Numbered custom rounds. Each file is one round, shared as
`https://danielstarosta-817.github.io/maptap/#n=<number>`.

The builder at the bottom of the standings page writes the JSON for you: build the round,
hit **Make the link**, then **Numbered instead**. Save the JSON here as `<number>.json`,
push, and share the short link. Numbering is yours to pick — just don't reuse one.

    { "t": "Countries that don't exist anymore",
      "q": [ ["Ouagadougou, Upper Volta", 12.3714, -1.5197], ... ] }

`q` is five entries of `[label, latitude, longitude]`. The label is all the guesser sees;
the coordinates are the answer. Use this route when you would rather the answers lived in
the repo than inside the URL.
