#!/usr/bin/env bash
# Download the children's books from Project Gutenberg's pglaf.org mirror into corpus/books/.
# The main gutenberg.org site returned 503 to scripted downloads on 2026-11-25; the mirror is
# run by the Project Gutenberg Literary Archive Foundation and serves the same texts.
set -eu
cd "$(dirname "$0")/../corpus/books"
for pair in 11:alice-in-wonderland 12:through-the-looking-glass 16:peter-pan 55:wizard-of-oz \
            236:jungle-book 289:wind-in-the-willows 113:secret-garden 120:treasure-island \
            500:pinocchio 271:black-beauty; do
  id=${pair%%:*}; slug=${pair#*:}
  [ -s "$slug.txt" ] && continue
  d=$(echo "${id%?}" | sed 's/./&\//g'); base="https://gutenberg.pglaf.org/$d$id"
  curl -sfL -m 30 -A "rag-learning-project" "$base/$id-0.txt" -o "$slug.txt" \
    || curl -sfL -m 30 -A "rag-learning-project" "$base/$id.txt" -o "$slug.txt"
  echo "$slug: $(wc -w < "$slug.txt") words"; sleep 1
done
