# Continuous Batching

## Mechanism

Continuous batching schedules active requests at each decoding iteration. Completed requests leave the batch and new requests can join without waiting for the longest sequence to finish. This can improve accelerator utilization for workloads with variable output lengths.

## Trade-offs

Continuous batching can improve aggregate throughput while increasing an individual request's queueing delay. Scheduling must balance throughput, fairness, and tail latency. Memory pressure and KV-cache capacity constrain the number of active sequences. Paged attention can improve cache allocation for continuous batching.

## Evaluation

Measure time to first token, inter-token latency, P95 request latency, queue wait, and completed requests per second. A throughput result without its latency distribution can conceal poor interactive performance.
