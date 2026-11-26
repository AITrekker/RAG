# Step log

One entry per step covering what was built, what I expected to break, and what actually broke.

## Step 1: substring search (recall@5 0.111, MRR 0.111)

I built AND keyword matching over 2,568 paragraphs, returned in book order with no ranking.

I expected "Ahab" to match hundreds of paragraphs unranked and "beef" to match nothing. Both happened, since "Who was Ahab?" matched 371 paragraphs and the beef question matched none.

The one hit (q01) is luck. Chapter 16 comes first in book order and happens to be a gold chapter, and the top five results are dialogue lines like "Who is Captain Ahab, sir?" that describe nothing.

The surprise was that requiring every word mattered more than vocabulary mismatch. Six of nine answerable questions returned zero paragraphs because a single question word (made, reward, object, first, survive) never appeared next to the others.

This leads to step 2, which ranks partial matches with BM25 instead of requiring every word.
