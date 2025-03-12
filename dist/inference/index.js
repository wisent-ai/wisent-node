"use strict";
/**
 * Inference module for Wisent AI
 *
 * This module provides functionality for running inference with control vectors.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.InferenceAPI = void 0;
/**
 * Class for running inference with control vectors
 */
class InferenceAPI {
    /**
     * Create a new InferenceAPI instance
     * @param client Wisent client instance
     */
    constructor(client) {
        this.client = client;
    }
    /**
     * Run inference with the specified options
     * @param request Inference request options
     * @returns Promise resolving to the inference response
     */
    async runInference(request) {
        const httpClient = this.client.getHttpClient();
        const response = await httpClient.post('/inference', request);
        return response.data;
    }
    /**
     * Run inference with a specific control vector
     * @param prompt Input prompt for the model
     * @param controlVector Control vector to apply
     * @param model Model to use (optional, defaults to the control vector's model)
     * @param scale Scaling factor for the control vector (optional, defaults to 1.0)
     * @returns Promise resolving to the inference response
     */
    async runWithControlVector(prompt, controlVector, model, scale = 1.0) {
        return this.runInference({
            model: model || controlVector.model,
            prompt,
            controlVectors: [
                {
                    id: controlVector.id,
                    scale
                }
            ]
        });
    }
}
exports.InferenceAPI = InferenceAPI;
