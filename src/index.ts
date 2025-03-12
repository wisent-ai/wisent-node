// Wisent AI Client Library
// Main entry point for the package

// Export version information
export { version } from './version';

// Export client
export { WisentClient, WisentClientConfig } from './client';

// Export activations module
export { 
  Activation,
  ActivationsAPI,
  GetActivationsOptions 
} from './activations';

// Export control vector module
export { 
  ControlVector,
  ControlVectorAPI,
  GetControlVectorsOptions 
} from './control_vector';

// Export inference module
export { 
  InferenceAPI,
  InferenceRequest,
  InferenceResponse 
} from './inference';

// Export utility functions
export {
  cosineSimilarity,
  scaleVector,
  addVectors,
  subtractVectors,
  euclideanDistance
} from './utils';

// Create a default export for convenience
import { WisentClient } from './client';
import { ActivationsAPI } from './activations';
import { ControlVectorAPI } from './control_vector';
import { InferenceAPI } from './inference';

/**
 * Create a complete Wisent client with all APIs
 * @param apiKey API key for authentication
 * @param baseUrl Optional base URL for the API
 * @returns Object containing all Wisent APIs
 */
export default function createWisentClient(apiKey: string, baseUrl?: string) {
  const client = new WisentClient({ apiKey, baseUrl });
  
  return {
    client,
    activations: new ActivationsAPI(client),
    controlVectors: new ControlVectorAPI(client),
    inference: new InferenceAPI(client)
  };
} 