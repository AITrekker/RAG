# Step log

One entry per step covering what was built, what I expected to break, and what actually broke.

## Step 1: substring search (recall@5 0.111, MRR 0.111)

I built AND keyword matching over 2,568 paragraphs, returned in book order with no ranking.

I expected "Ahab" to match hundreds of paragraphs unranked and "beef" to match nothing. Both happened, since "Who was Ahab?" matched 371 paragraphs and the beef question matched none.

The one hit (q01) is luck. Chapter 16 comes first in book order and happens to be a gold chapter, and the top five results are dialogue lines like "Who is Captain Ahab, sir?" that describe nothing.

Requiring every word caused more misses than vocabulary mismatch did. Six of nine answerable questions returned zero paragraphs because a single question word (made, reward, object, first, survive) never appeared next to the others.

This leads to step 2, which uses BM25 to rank paragraphs that match only some of the words.

## Step 2: BM25 (recall@5 0.615, MRR 0.459 on 30 questions)

I replaced AND matching with BM25 ranking over the same paragraphs and the same tokenizer. Step 1 scored 0.154 on this 30-question set.

I expected vocabulary mismatch to remain and "Ahab" to be too common to discriminate. Both happened. "Who was Ahab?" lost the lucky book-order hit from step 1, and its top five now come from chapters 135, 128, 19, 132, and 130. The beef question now hits chapter 36, but only because those paragraphs say "Ahab" and "Moby" many times, and the word "beef" contributes nothing.

The surprise is that conceptual questions did better than lookups. All 9 conceptual questions hit, against 3 of 10 lookups and 4 of 7 hard questions. The lookups fail on exact wording. The book says "chief mate" where the question says "first mate," "owners" where it says "owned," and "god" where it says "idol," and the tokenizer has no stemming to bridge "owned" and "owners." The long paragraph that literally says "Stubb was the second mate" also loses to shorter paragraphs that repeat "mate."

BM25 returns something for every question, including all four unanswerable ones, so retrieval alone has no way to say "not in the book." That becomes the generator's job at step 7.

The hit metric is generous for multi-chapter questions. q26 counts as a hit because chapter 100 appears in the top five, although the answer needs four chapters.

This leads to step 3, embeddings, since most remaining misses are about meaning and wording. Stemming would fix "owned" and "owners" and is worth a quick test alongside.

## Step 3: embeddings (vector recall@5 0.769, MRR 0.572)

I embedded each paragraph with bge-small-en-v1.5 on the RTX 5070 and ranked by cosine similarity. Everything is still in memory, and the book embeds in seconds.

| Mode | Recall@5 | MRR@10 | Lookup | Conceptual | Hard |
|---|---|---|---|---|---|
| BM25 (step 2) | 0.615 | 0.459 | 3/10 | 9/9 | 4/7 |
| Vector | 0.769 | 0.572 | 9/10 | 6/9 | 5/7 |

Both Ahab questions hit for the first time. "Who was Ahab?" ranks chapters 16 and 28 in the top five, and the beef question finds chapters 36 and 41 even though no paragraph contains "beef."

I predicted that exact names would get worse, and they did. Vectors missed "Why wouldn't Ahab help the Rachel?", where BM25 matched the ship's name directly. Vectors also missed "How did Ahab die?" and the coffin-survival question, which BM25 found through words like "die" and "coffin." The two methods fail on different questions, and that is the case for combining them at step 5.

The surprise was that lookups went from worst to best. "First mate" now finds "chief mate," and "owned" finds "owners," because the embedding treats them as the same meaning.

The chunks have the problems I predicted. 35 paragraphs are longer than the model's 512-token limit (the longest is 1,041 tokens) and get cut off, and 369 paragraphs are under 20 tokens, mostly short dialogue lines with no context.

The stemming side test made BM25 worse, dropping recall from 0.615 to 0.538. It lost q05 and q26 and gained nothing, and it still missed "owned" versus "owners." I dropped stemming.

This leads to step 4, chunking that fits the model's window and gives short lines their context.
