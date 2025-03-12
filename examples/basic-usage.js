/**
 * Basic usage example for the Wisent client library
 */

// Import the Wisent client library
const wisent = require('../dist');

// Create a client instance with your API key
const client = wisent.default('YOUR_API_KEY');

// Example: Get control vectors
async function getControlVectors() {
  try {
    // Get control vectors for a specific model
    const controlVectors = await client.controlVectors.getControlVectors({
      model: 'llama-3-70b',
      limit: 5
    });
    
    console.log('Available control vectors:');
    controlVectors.forEach(cv => {
      console.log(`- ${cv.name}: ${cv.description || 'No description'}`);
    });
    
    return controlVectors;
  } catch (error) {
    console.error('Error fetching control vectors:', error.message);
    return [];
  }
}

// Example: Run inference with a control vector
async function runInference(controlVectorId) {
  try {
    const result = await client.inference.runInference({
      model: 'llama-3-70b',
      prompt: 'Write a short poem about artificial intelligence.',
      controlVectors: [
        {
          id: controlVectorId,
          scale: 1.0
        }
      ],
      maxTokens: 100
    });
    
    console.log('\nGenerated text:');
    console.log(result.text);
    
    console.log('\nToken usage:');
    console.log(`- Prompt tokens: ${result.usage.promptTokens}`);
    console.log(`- Completion tokens: ${result.usage.completionTokens}`);
    console.log(`- Total tokens: ${result.usage.totalTokens}`);
  } catch (error) {
    console.error('Error running inference:', error.message);
  }
}

// Run the examples
async function main() {
  console.log(`Using Wisent client library v${wisent.version}`);
  
  // Get control vectors
  const controlVectors = await getControlVectors();
  
  // If we have control vectors, run inference with the first one
  if (controlVectors.length > 0) {
    await runInference(controlVectors[0].id);
  } else {
    console.log('No control vectors available for inference.');
  }
}

// Execute the main function
main().catch(error => {
  console.error('Unhandled error:', error);
}); 