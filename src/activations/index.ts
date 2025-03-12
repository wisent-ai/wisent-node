/**
 * Activations module for Wisent AI
 * 
 * This module provides functionality for working with model activations.
 */

import { WisentClient } from '../client';

/**
 * Activation data structure
 */
export interface Activation {
  /**
   * Unique identifier for the activation
   */
  id: string;
  
  /**
   * Model that generated the activation
   */
  model: string;
  
  /**
   * Layer where the activation was captured
   */
  layer: string;
  
  /**
   * Timestamp when the activation was created
   */
  createdAt: string;
  
  /**
   * Activation data (vector representation)
   */
  data: number[];
}

/**
 * Options for retrieving activations
 */
export interface GetActivationsOptions {
  /**
   * Filter by model name
   */
  model?: string;
  
  /**
   * Filter by layer name
   */
  layer?: string;
  
  /**
   * Maximum number of activations to return
   */
  limit?: number;
}

/**
 * Class for working with model activations
 */
export class ActivationsAPI {
  private client: WisentClient;
  
  /**
   * Create a new ActivationsAPI instance
   * @param client Wisent client instance
   */
  constructor(client: WisentClient) {
    this.client = client;
  }
  
  /**
   * Get activations based on specified criteria
   * @param options Options for filtering activations
   * @returns Promise resolving to an array of activations
   */
  async getActivations(options: GetActivationsOptions = {}): Promise<Activation[]> {
    const httpClient = this.client.getHttpClient();
    const response = await httpClient.get('/activations', { params: options });
    return response.data.activations;
  }
  
  /**
   * Get a specific activation by ID
   * @param id Activation ID
   * @returns Promise resolving to the activation
   */
  async getActivation(id: string): Promise<Activation> {
    const httpClient = this.client.getHttpClient();
    const response = await httpClient.get(`/activations/${id}`);
    return response.data.activation;
  }
} 