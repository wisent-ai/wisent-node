"use strict";
/**
 * Control Vector module for Wisent AI
 *
 * This module provides functionality for working with control vectors.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.ControlVectorAPI = void 0;
/**
 * Class for working with control vectors
 */
class ControlVectorAPI {
    /**
     * Create a new ControlVectorAPI instance
     * @param client Wisent client instance
     */
    constructor(client) {
        this.client = client;
    }
    /**
     * Get control vectors based on specified criteria
     * @param options Options for filtering control vectors
     * @returns Promise resolving to an array of control vectors
     */
    async getControlVectors(options = {}) {
        const httpClient = this.client.getHttpClient();
        const response = await httpClient.get('/control-vectors', { params: options });
        return response.data.controlVectors;
    }
    /**
     * Get a specific control vector by ID
     * @param id Control Vector ID
     * @returns Promise resolving to the control vector
     */
    async getControlVector(id) {
        const httpClient = this.client.getHttpClient();
        const response = await httpClient.get(`/control-vectors/${id}`);
        return response.data.controlVector;
    }
    /**
     * Create a new control vector
     * @param controlVector Control vector data to create
     * @returns Promise resolving to the created control vector
     */
    async createControlVector(controlVector) {
        const httpClient = this.client.getHttpClient();
        const response = await httpClient.post('/control-vectors', controlVector);
        return response.data.controlVector;
    }
}
exports.ControlVectorAPI = ControlVectorAPI;
