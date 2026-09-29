## Cathedral, by GPT-6 Astra, xhigh

Used [jev-rerank](https://github.com/anteloc/jev-rerank) for this, in order to test how much it would help in finding suitable parts.

Two prompts, one for instructing Astra into using jev-rerank, the next one for asking to build a cathedral.

**Prompt:** ok, let's try and use a jev reranker for getting suitable parts for a model.

use the following command to get candidates:

../jev-rerank/uv run jev-rerank --db $LDRAW\_LIB\_DIR/scripts/ldraw-info.db --table-field parts\_descriptions.description --top 10 --query 'a wall decoration for a castle' --show --json

notice that: query should be written as if trying to find a single part, but it will return 10 candidates, ranked by score.

(Astra gave it a try... and then...)

**Prompt:** ok, now: build me a cathedral