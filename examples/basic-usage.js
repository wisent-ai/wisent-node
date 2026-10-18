/**
 * Basic usage example for the Wisent client library.
 *
 * Run it with WISENT_API_KEY, WISENT_API_URL (the base URL of the Wisent API
 * you call), WISENT_MODEL and STEERING_SCALE set; a missing one is refused
 * naming it, and a failed request ends the run with the API's own error.
 */

const wisent = require('../dist');

function required(name) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

const client = wisent.default(required('WISENT_API_KEY'), required('WISENT_API_URL'));
const model = required('WISENT_MODEL');
const strength = Number(required('STEERING_SCALE'));
if (Number.isNaN(strength)) throw new Error('STEERING_SCALE is not a number');

async function main() {
  console.log(`Using Wisent client library v${wisent.version}`);

  const controlVectors = await client.controlVectors.getControlVectors({ model });
  for (const vector of controlVectors) {
    console.log(`- ${vector.name} (${vector.id})`);
  }

  const [first] = controlVectors;
  if (!first) {
    console.log(`The API holds no control vector for ${model}.`);
    return;
  }

  const response = await client.inference.runWithControlVector(
    'Write a short poem about artificial intelligence.',
    first,
    strength,
  );
  console.log(response.text);
  console.log(`Prompt tokens: ${response.usage.promptTokens}`);
  console.log(`Completion tokens: ${response.usage.completionTokens}`);
  console.log(`Total tokens: ${response.usage.totalTokens}`);
}

main();
