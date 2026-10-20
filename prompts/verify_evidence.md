# Evidence verification prompt — development draft 0.1

Evaluate one proposed evidence record solely against the supplied source passage and surrounding context. Do not use background knowledge. The calling program has already checked whether the quotation occurs in the archived text.

Return one JSON object conforming to `schemas/verification-result.schema.json`.

Accept the record only if all of the following are true:

1. The quoted passage and immediate context support the assigned theme.
2. The claim target is correct.
3. The claim type is correct.
4. The narrative segment is explicit rather than inferred from outside knowledge.
5. The salience level is no stronger than the source language warrants.
6. The stance is attributed to the film rather than merely expressing the critic's taste.
7. Any ending response is explicit and correctly classified.
8. The selfishness and consumerism guardrails in the extraction prompt are satisfied.
9. The passage and context concern the supplied target film rather than a different work mentioned by the source.

Reject rather than repair an unsupported record. Do not find a different quotation, add a new theme, or rewrite the evidence. List concise machine-readable reason codes and a brief explanation grounded in the supplied context.
