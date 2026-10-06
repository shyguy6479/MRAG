# Speculative Decoding

## Mechanism

Speculative decoding uses a smaller draft model to propose several tokens. The target model verifies these proposals in a parallel pass. A correctly implemented speculative sampling algorithm preserves the target model distribution through acceptance and rejection rules.

## Trade-offs

Speculative decoding adds draft-model memory and computation. Low acceptance rates can erase the latency benefit. A draft model that predicts the target model's tokens well tends to increase acceptance. Unlike weight quantization, speculative decoding primarily reduces sequential target-model decoding work rather than parameter storage.

## Evaluation

Measure draft acceptance rate, time per output token, draft overhead, and end-to-end latency. Match output distribution and sampling settings when comparing implementations. Report the draft model, target model, and number of proposed tokens.
