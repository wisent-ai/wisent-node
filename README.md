<!-- wisent-banner:start -->
<p align="center">
  <img src="assets/readme-banner.webp" alt="wisent-node by Wisent" width="100%">
</p>
<!-- wisent-banner:end -->

<!-- wisent-readme-signals:start -->
[![Source](https://img.shields.io/badge/GitHub-Source-181717?logo=github)](https://github.com/wisent-ai/wisent-node) [![Issues](https://img.shields.io/badge/GitHub-Issues-181717?logo=github)](https://github.com/wisent-ai/wisent-node/issues) [![Wisent](https://img.shields.io/badge/Wisent-Website-0B0B0B)](https://wisent.com) [![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/qRjpkthq54) [![LinkedIn](https://img.shields.io/badge/LinkedIn-Follow-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/company/wisent-ai/) [![X](https://img.shields.io/badge/X-Follow-000000?logo=x&logoColor=white)](https://x.com/wisentai) [![Enterprise](https://img.shields.io/badge/Enterprise-Book%20a%20call-0B0B0B?logo=calendly)](https://calendly.com/lbartoszcze)
<!-- wisent-readme-signals:end -->

# Wisent

Monitor and Control Your AI Agent Brain.

You look at what your model says. But what was it actually thinking? Wisent shows
you how to use information from AI activations, intermediate steps within its
layers, to your advantage. Wisent is a full toolkit for representation
engineering, activation steering and mechanistic interpretability. Cut
hallucination rates, decensor your model or stop it from being detected by
AI-generated text detectors. Your Models — Yours to Control. Better than
fine-tuning. Better than analysing the outputs directly.

Deploy the latest research in your stack. This is the JavaScript and TypeScript client
you call it from.

## Installation

```bash
npm install wisent
# or
yarn add wisent
```

## Features

- **Activations**: Extract and send model activations to the Wisent backend
- **Control Vectors**: Retrieve and apply control vectors for model inference
- **Inference**: Utilities for applying control vectors during inference
- **Utilities**: Helper functions for common tasks

## Quick Start

The package's default export builds a client and the three APIs that share it.

```typescript
import createWisentClient from 'wisent';

// The base URL is optional; omitted, the client calls https://api.wisent.ai.
const wisent = createWisentClient("your_api_key");

// Control vectors the backend holds for a model.
const [helpful] = await wisent.controlVectors.getControlVectors({
  model: "mistralai/Mistral-7B-Instruct-v0.1",
});

// Steer one generation with it. The scale is required: steering strength is
// the caller's choice, and no strength suits every vector.
const strength = Number(process.env.STEERING_SCALE);
const response = await wisent.inference.runWithControlVector(
  "Tell me about quantum computing",
  helpful,
  strength,
);
console.log(response.text, response.usage.totalTokens);
```

## Advanced Usage

### Several control vectors in one request

`runInference` takes the whole request: the model, the prompt and each control
vector by id with its own scale. `maxTokens`, `temperature` and `topP` are sent
only when given; omitted, the server's model decides them.

```typescript
const concise = await wisent.controlVectors.getControlVector("concise-vector-id");

const response = await wisent.inference.runInference({
  model: helpful.model,
  prompt: "Tell me about quantum computing",
  controlVectors: [
    { id: helpful.id, scale: strength },
    { id: concise.id, scale: strength },
  ],
});
```

### Vector utilities

`cosineSimilarity`, `euclideanDistance`, `scaleVector`, `addVectors` and
`subtractVectors` are exported for working with activation and control vectors
as plain number arrays.

## Release maintenance

The release metadata tool is the Rust crate in `release/`; it is not a library
test and is not included in the npm distribution.

```bash
cargo run --manifest-path release/Cargo.toml -- surface
cargo run --manifest-path release/Cargo.toml -- baseline --stdout
```

`surface` reads the package's public names statically (exports, public members
of exported types, `bin` commands) from the entry point package.json declares.
`baseline` recovers `released-surface.json` from the best tier reachable now: the
tarball npm serves, else a tag at origin, else the working revision.
`published NAME` asks npm about one name and prints published, absent or
unproven (unproven exits 1), and `marker-claims MARKER` says whether a marker's
tier claims a registry. The version-check workflow uses these same commands.
`--stdout` does not replace `released-surface.json`; an
unreadable distribution or unproven publication tier exits 1 with the reason.

## Documentation

For full documentation, visit [docs.wisent.ai](https://docs.wisent.ai).

## License

MIT
