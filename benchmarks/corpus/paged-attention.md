# Paged Attention

## Mechanism

Paged attention organizes the key-value cache into fixed-size blocks that need not occupy contiguous physical memory. A block table maps logical positions to physical cache blocks. This reduces wasted KV-cache allocation and enables more concurrent sequences to fit in available memory.

## Trade-offs

Paged attention adds block-table management and specialized attention kernels. It improves cache allocation efficiency but does not reduce the number of parameters in the model. Long contexts still consume substantial KV-cache memory. Paged attention and weight quantization address different memory components and can be combined.

## Evaluation

Measure KV-cache utilization, fragmentation, concurrent sequences, and serving throughput under realistic request length distributions. Throughput improvements depend on available memory and the workload, so do not assume a fixed speedup.
