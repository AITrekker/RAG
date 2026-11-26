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

## Step 4: token-sized chunks (vector r128 recall@800w 0.885)

I built a recursive chunker that works within each chapter. It packs paragraphs, or sentences when a paragraph is too long, into chunks of a target size measured with the embedding model's own tokenizer, and it carries a small overlap (one eighth of the size) into the next chunk. I swept sizes of 128, 256, 384, and 512 tokens for both BM25 and vector search.

| Chunking | Chunks | Mean tokens | Under 20 tokens | Over 512 tokens |
|---|---|---|---|---|
| Paragraph | 2,568 | 112 | 410 | 35 |
| r128 | 2,920 | 100 | 16 | 0 |
| r256 | 1,458 | 202 | 2 | 0 |
| r384 | 989 | 298 | 0 | 0 |
| r512 | 729 | 405 | 0 | 20 |

The first sweep used recall@5 and gave a muddled answer, since bigger chunks looked about as good as smaller ones. Five 400-token chunks hold four times the text of five 100-token chunks, so recall@5 gives big chunks credit for retrieving more text. I added recall@800w to the harness, which walks down the results until 800 words (about 1,000 tokens) are used and checks whether any of that text comes from a gold chapter. The rescore script now copies the current harness into every tag, so all steps carry this metric.

| Mode | Recall@5 | Recall@800w | MRR@10 |
|---|---|---|---|
| BM25, paragraph | 0.615 | 0.846 | 0.459 |
| BM25, r128 | 0.615 | 0.808 | 0.432 |
| BM25, r512 | 0.692 | 0.500 | 0.542 |
| Vector, paragraph | 0.769 | 0.808 | 0.572 |
| Vector, r128 | 0.808 | 0.885 | 0.598 |
| Vector, r512 | 0.769 | 0.654 | 0.622 |

At an equal amount of text, smaller chunks win for both methods, and recall falls steadily as chunk size grows. Vector search with 128-token chunks is the best configuration so far at 23 of 26. BM25 on raw paragraphs holds up well on this metric, because it favors short paragraphs that cost few words.

One question moves these scores by 0.038, so a difference of one or two questions between neighboring configurations is noise. The trend across sizes is larger than that.

Two questions miss in every configuration. q14 asks for Queequeg's "idol," and the book calls Yojo his "god." q25 asks what Fedallah "predicted," and chapter 117 shows the prophecy as dialogue about hearses and hemp without any word like "predict."

The r512 setting slightly overshoots the model's limit on 20 chunks, by up to 12 tokens, because the limit includes two special tokens and re-tokenizing decoded text can add a few. It does not change the conclusion, since r512 lost anyway.

I reset `runs/results.csv` because its columns changed. `runs/rescore.csv` is the comparable record for every step.

This leads to step 5, hybrid search over r128 chunks. BM25 and vectors still miss different questions.

## Step 5: hybrid search with RRF (recall@800w 0.923, MRR 0.646)

I ran BM25 and vector search over the same r128 chunks and merged the two rankings with reciprocal rank fusion. Each chunk scores the sum of 1 / (60 + rank) across both lists, so only rank positions matter and the two methods' incompatible scores never get compared.

| Mode (r128) | Recall@5 | Recall@800w | MRR@10 |
|---|---|---|---|
| BM25 | 0.615 | 0.808 | 0.432 |
| Vector | 0.808 | 0.885 | 0.598 |
| Hybrid | 0.808 | 0.923 | 0.646 |

I expected hybrid search to recover the questions where only one method succeeds, and it did. At 800 words, hybrid hits every question that either method hits on its own, and it loses none. It picks up "How did Ahab die?" from BM25 and the leg, Queequeg's home, and whiteness questions from vectors. MRR improved more than recall did, which means the right chunk also moves higher in the list.

The two remaining misses are the ones both methods miss, q14 (idol versus god) and q25 (Fedallah's prediction). Fusion cannot recover a chunk that neither list ranks well.

"Who was Ahab?" hits within 800 words but not in the top five, where chapters 134, 130, and 135 show Ahab in the final chase without describing him. This is the whole-book question that step 9's chapter summaries target.

Every chunking or model change still re-embeds the whole book on each run, and the rescore re-embeds every tag. That is fast for one book, but the LLM-written headers in step 8 will be slow to produce and must be stored. This leads to step 6, Postgres and pgvector.

## Step 6: Postgres and pgvector (scores unchanged, recall@800w 0.923)

I moved storage into Postgres 17 with pgvector 0.8.7. The schema has a documents table, a chunks table keyed by chunking strategy with a generated full-text column and GIN index, and an embeddings table with a fixed 384-dimension vector column and an HNSW index. `rag ingest` chunks and embeds the book first, then writes the document, its 2,920 chunks, and their embeddings in one transaction.

The goal was to hold step 5's scores while making the embeddings persistent, and it did. The Postgres versions of vector and hybrid search return the same top five chunks as the in-memory versions for all 30 questions, and the scores match exactly.

| Mode (r128) | Recall@5 | Recall@800w | MRR@10 |
|---|---|---|---|
| pg-vector (HNSW) | 0.808 | 0.885 | 0.598 |
| pg-vector-exact | 0.808 | 0.885 | 0.598 |
| pg-hybrid | 0.808 | 0.923 | 0.646 |

The first ingest took 11 seconds, and a second run skipped in 0.16 seconds because the file hash, chunking, and model were already stored. To test the transaction, I forced the embeddings to the wrong dimension so the first vector insert would fail. The ingest raised an error and the row counts stayed exactly as before, with no orphan chunks and no partial document. That is the failure mode the two-database setup in LearnRAG kept hitting.

HNSW is an approximate index, but at 2,920 vectors it returned the same results as an exact scan on every question. One detail matters here. pgvector's HNSW returns at most `hnsw.ef_search` rows (40 by default), so a query asking for the top 200 silently gets 40. The search code raises ef_search to the requested depth.

Retrieval quality is where step 5 left it, and I still have to read chunks myself to get an answer. This leads to step 7, generation with local Qwen.
