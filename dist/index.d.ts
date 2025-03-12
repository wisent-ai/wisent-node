export { version } from './version';
export { WisentClient, WisentClientConfig } from './client';
export { Activation, ActivationsAPI, GetActivationsOptions } from './activations';
export { ControlVector, ControlVectorAPI, GetControlVectorsOptions } from './control_vector';
export { InferenceAPI, InferenceRequest, InferenceResponse } from './inference';
export { cosineSimilarity, scaleVector, addVectors, subtractVectors, euclideanDistance } from './utils';
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
export default function createWisentClient(apiKey: string, baseUrl?: string): {
    client: WisentClient;
    activations: ActivationsAPI;
    controlVectors: ControlVectorAPI;
    inference: InferenceAPI;
};
