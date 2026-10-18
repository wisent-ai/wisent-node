/**
 * TypeScript usage example for the Wisent client library.
 *
 * Run it with WISENT_API_KEY, WISENT_API_URL (the base URL of the Wisent API
 * you call), WISENT_MODEL and STEERING_SCALE set; a missing one is refused
 * naming it, and a failed request ends the run with the API's own error.
 */

import createWisentClient, { ControlVector, cosineSimilarity } from '../dist';

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

const wisent = createWisentClient(required('WISENT_API_KEY'), required('WISENT_API_URL'));
const model = required('WISENT_MODEL');
const strength = Number(required('STEERING_SCALE'));
if (Number.isNaN(strength)) throw new Error('STEERING_SCALE is not a number');

function compare(first: ControlVector, second: ControlVector): void {
  const similarity = cosineSimilarity(first.data, second.data);
  console.log(`Similarity between "${first.name}" and "${second.name}": ${similarity}`);
}

async function main(): Promise<void> {
  const controlVectors = await wisent.controlVectors.getControlVectors({ model });
  for (const vector of controlVectors) {
    console.log(`- ${vector.name} (${vector.id})`);
  }

  const [first, second] = controlVectors;
  if (!first) {
    console.log(`The API holds no control vector for ${model}.`);
    return;
  }

  const response = await wisent.inference.runWithControlVector(
    'Write a short poem about artificial intelligence.',
    first,
    strength,
  );
  console.log(response.text);
  console.log(`Prompt tokens: ${response.usage.promptTokens}`);
  console.log(`Completion tokens: ${response.usage.completionTokens}`);
  console.log(`Total tokens: ${response.usage.totalTokens}`);

  if (second) compare(first, second);
}

void main();
