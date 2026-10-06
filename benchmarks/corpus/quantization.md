# Quantization

## Mechanism

Quantization reduces model weight memory by representing weights with fewer bits. Weight-only quantization primarily reduces the memory occupied by model parameters. Activation quantization also changes the representation of intermediate activations. Calibration estimates suitable scales from representative input data.

## Trade-offs

Aggressive quantization can reduce accuracy, especially when important outlier values are poorly represented. Calibration data should resemble the deployment distribution. Lower precision does not guarantee lower latency because the hardware and inference kernels must support the chosen format efficiently. Quantization primarily targets model storage and memory bandwidth, while speculative decoding targets sequential token generation.

## Evaluation

Measure task accuracy, peak memory, tokens per second, and latency on the target hardware. Compare identical prompts, batch sizes, and output lengths. Report model format and calibration settings alongside measurements.
