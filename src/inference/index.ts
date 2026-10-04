/**
 * Inference module for Wisent AI
 * 
 * This module provides functionality for running inference with control vectors.
 */

import { WisentClient } from '../client';
import { ControlVector } from '../control_vector';

/**
 * Inference request options
 */
export interface InferenceRequest {
  /**
   * Model to use for inference
   */
  model: string;
  
  /**
   * Input prompt for the model
   */
  prompt: string;
  
  /**
   * Control vectors to apply during inference
   */
  controlVectors?: {
    /**
     * Control vector ID
     */
    id: string;
    
    /**
     * Scaling factor for the control vector. Required: steering strength is
     * the caller's choice, and no strength suits every vector.
     */
    scale: number;
  }[];
  
  /**
   * Maximum number of tokens to generate; omitted, the server's model decides
   */
  maxTokens?: number;
  
  /**
   * Temperature for sampling; omitted, the model's own sampling is used
   */
  temperature?: number;
  
  /**
   * Top-p sampling parameter; omitted, the model's own sampling is used
   */
  topP?: number;
}

/**
 * Inference response structure
 */
export interface InferenceResponse {
  /**
   * Generated text from the model
   */
  text: string;
  
  /**
   * Usage statistics
   */
  usage: {
    /**
     * Number of prompt tokens
     */
    promptTokens: number;
    
    /**
     * Number of completion tokens
     */
    completionTokens: number;
    
    /**
     * Total number of tokens
     */
    totalTokens: number;
  };
}

/**
 * Class for running inference with control vectors
 */
export class InferenceAPI {
  private client: WisentClient;
  
  /**
   * Create a new InferenceAPI instance
   * @param client Wisent client instance
   */
  constructor(client: WisentClient) {
    this.client = client;
  }
  
  /**
   * Run inference with the specified options
   * @param request Inference request options
   * @returns Promise resolving to the inference response
   */
  async runInference(request: InferenceRequest): Promise<InferenceResponse> {
    const httpClient = this.client.getHttpClient();
    const response = await httpClient.post('/inference', request);
    return response.data;
  }
  
  /**
   * Run inference with a specific control vector
   * @param controlVector Control vector to apply
   * @param scale Scaling factor for the control vector (required: the caller states the steering strength)
   * @param model Model to use (optional, defaults to the control vector's model)
   * @returns Promise resolving to the inference response
   */
  async runWithControlVector(
    prompt: string,
    controlVector: ControlVector,
    scale: number,
    model?: string
  ): Promise<InferenceResponse> {
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