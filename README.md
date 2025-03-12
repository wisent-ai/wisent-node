# Wisent

A JavaScript/TypeScript client library for interacting with the Wisent backend services.

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