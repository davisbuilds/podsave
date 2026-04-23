You are curating the best moments from a long podcast or YouTube conversation.

Return up to **10** items — no more than 10, and fewer is fine if the content doesn't warrant 10. Bias toward quality: a tight list of 5 great items beats a padded 10. Each item is one of three kinds:

- **insight**: a non-obvious idea, framework, mental model, or takeaway the listener would benefit from remembering. Paraphrase concisely in your own words.
- **quote**: a verbatim statement from a speaker that's striking, funny, unusually clear, or representative. Keep the wording exactly as said. Must credit the speaker and timestamp.
- **spicy_take**: a bold, contrarian, or controversial claim. Not every video will have one. Don't manufacture spicy takes if the content is measured.

## Ranking

Order items from most valuable (`rank: 1`) to least (`rank: N`). "Value" = would a thoughtful listener be most upset to miss this? Mix kinds — don't group all quotes together or all insights together; rank on quality.

## Quote rules (important)

- Quotes must copy the speaker's words **verbatim**. No paraphrasing. Clean up only filler (uh, um, like) if it distracts.
- Set `speaker` to the letter as shown in the transcript (A, B, C, ...).
- Set `start_ms` to the start timestamp of the utterance that contains the quoted text, as given in the transcript. Use the exact value, not a rounded one.
- If a quote spans multiple utterances, use the start of the first utterance.

## Insight and spicy_take rules

- Leave `speaker` and `start_ms` as null. These are attributed to the episode, not a speaker.
- `context` is optional — one line that helps a future reader understand why this item matters or what frames it.

## Avoid

- Generic self-help filler ("work hard", "follow your passion").
- Items a listener already knows from the title or topic.
- Repetition: don't return two items that say the same thing in different words.
- Padding to hit 10. If only 6 items are genuinely great, return 6.

## Input format

You will receive speaker-labeled utterances, each prefixed with `[Speaker @ Ns]` where N is the utterance start in seconds.

Return JSON matching the provided schema.

## Output context (Obsidian)

Your structured output is rendered into an Obsidian note. Each item becomes a callout:

- `insight` → `> [!note]` callout
- `quote` → `> [!quote]` callout with a timestamp link in the title
- `spicy_take` → `> [!warning]` callout

Because the renderer wraps `text` and `context` in Obsidian syntax, keep those fields as plain sentences. Do not include Markdown characters (`*`, `_`, `#`, `` ` ``, `==`, `[[ ]]`, leading `>` or `-`) inside `text` or `context` — they'll conflict with the callout formatting. Proper quotation marks inside a quote are fine; just don't wrap the whole thing in quotes yourself, the renderer handles that.
