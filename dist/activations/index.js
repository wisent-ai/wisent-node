"use strict";
/**
 * Activations module for Wisent AI
 *
 * This module provides functionality for working with model activations.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ActivationsAPI = void 0;
/**
 * Class for working with model activations
 */
class ActivationsAPI {
    /**
     * Create a new ActivationsAPI instance
     * @param client Wisent client instance
     */
    constructor(client) {
        this.client = client;
    }
    /**
     * Get activations based on specified criteria
     * @param options Options for filtering activations
     * @returns Promise resolving to an array of activations
     */
    async getActivations(options = {}) {
        const httpClient = this.client.getHttpClient();
        const response = await httpClient.get('/activations', { params: options });
        return response.data.activations;
    }
    /**
     * Get a specific activation by ID
     * @param id Activation ID
     * @returns Promise resolving to the activation
     */
    async getActivation(id) {
        const httpClient = this.client.getHttpClient();
        const response = await httpClient.get(`/activations/${id}`);
        return response.data.activation;
    }
}
exports.ActivationsAPI = ActivationsAPI;
