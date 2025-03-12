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
export declare class ActivationsAPI {
    private client;
    /**
     * Create a new ActivationsAPI instance
     * @param client Wisent client instance
     */
    constructor(client: WisentClient);
    /**
     * Get activations based on specified criteria
     * @param options Options for filtering activations
     * @returns Promise resolving to an array of activations
     */
    getActivations(options?: GetActivationsOptions): Promise<Activation[]>;
    /**
     * Get a specific activation by ID
     * @param id Activation ID
     * @returns Promise resolving to the activation
     */
    getActivation(id: string): Promise<Activation>;
}
