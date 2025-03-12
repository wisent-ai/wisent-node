/**
 * TypeScript usage example for the Wisent client library
 */

// Import the Wisent client library and types
import createWisentClient, { 
  ControlVector,
  InferenceResponse,
  cosineSimilarity
} from '../dist';

// Create a client instance with your API key
const wisent = createWisentClient('YOUR_API_KEY');

// Example: Get control vectors
async function getControlVectors(): Promise<ControlVector[]> {
  try {
    // Get control vectors for a specific model
    const controlVectors = await wisent.controlVectors.getControlVectors({
      model: 'llama-3-70b',
      limit: 5
    });
    
    console.log('Available control vectors:');
    controlVectors.forEach(cv => {
      console.log(`- ${cv.name}: ${cv.description || 'No description'}`);
    });
    
    return controlVectors;
  } catch (error) {
    console.error('Error fetching control vectors:', (error as Error).message);
    return [];
  }
}

// Example: Run inference with a control vector
async function runInference(controlVectorId: string): Promise<InferenceResponse | null> {
  try {
    const result = await wisent.inference.runInference({
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
    
    return result;
  } catch (error) {
    console.error('Error running inference:', (error as Error).message);
    return null;
  }
}

// Example: Compare two control vectors
function compareControlVectors(cv1: ControlVector, cv2: ControlVector): void {
  const similarity = cosineSimilarity(cv1.data, cv2.data);
  console.log(`\nSimilarity between "${cv1.name}" and "${cv2.name}": ${similarity.toFixed(4)}`);
}

// Run the examples
async function main(): Promise<void> {
  console.log(`Using Wisent client library`);
  
  // Get control vectors
  const controlVectors = await getControlVectors();
  
  // If we have control vectors, run inference with the first one
  if (controlVectors.length > 0) {
    await runInference(controlVectors[0].id);
    
    // If we have at least two control vectors, compare them
    if (controlVectors.length >= 2) {
      compareControlVectors(controlVectors[0], controlVectors[1]);
    }
  } else {
    console.log('No control vectors available for inference.');
  }
}

// Execute the main function
main().catch(error => {
  console.error('Unhandled error:', error);
}); 