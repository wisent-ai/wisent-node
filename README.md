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

```typescript
import { WisentClient } from 'wisent';

// Initialize the client
const client = new WisentClient({
  apiKey: "your_api_key",
  baseUrl: "https://api.wisent.ai"
});

// Get a control vector from the backend
client.controlVector.get({
  name: "helpful", 
  model: "mistralai/Mistral-7B-Instruct-v0.1"
})
.then(controlVector => {
  console.log("Retrieved control vector:", controlVector);
})
.catch(error => {
  console.error("Error:", error);
});

// Apply a control vector during inference
client.inference.generateWithControl({
  modelName: "mistralai/Mistral-7B-Instruct-v0.1",
  prompt: "Tell me about quantum computing",
  controlVectors: {
    helpful: 0.8, 
    concise: 0.5
  }
})
.then(response => {
  console.log("Response:", response.text);
})
.catch(error => {
  console.error("Error:", error);
});
```

## Advanced Usage

### Working with Control Vectors

```typescript
import { WisentClient } from 'wisent';

const client = new WisentClient({
  apiKey: "your_api_key"
});

// Get a control vector
const helpfulVector = await client.controlVector.get({
  name: "helpful", 
  model: "mistralai/Mistral-7B-Instruct-v0.1"
});

// Combine multiple vectors
const combinedVector = await client.controlVector.combine({
  vectors: {
    helpful: 0.8,
    concise: 0.5
  },
  model: "mistralai/Mistral-7B-Instruct-v0.1"
});

// Apply during inference
const response = await client.inference.generate({
  prompt: "Tell me about quantum computing",
  controlVector: combinedVector,
  method: "caa" // Context-Aware Addition
});
```

## Documentation

For full documentation, visit [docs.wisent.ai](https://docs.wisent.ai).

## License

MIT
