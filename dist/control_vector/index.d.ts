/**
 * Control Vector module for Wisent AI
 *
 * This module provides functionality for working with control vectors.
 */
import { WisentClient } from '../client';
/**
 * Control Vector data structure
 */
export interface ControlVector {
    /**
     * Unique identifier for the control vector
     */
    id: string;
    /**
     * Name of the control vector
     */
    name: string;
    /**
     * Description of what the control vector does
     */
    description?: string;
    /**
     * Model this control vector is compatible with
     */
    model: string;
    /**
     * Layer where the control vector is applied
     */
    layer: string;
    /**
     * Timestamp when the control vector was created
     */
    createdAt: string;
    /**
     * Control vector data (vector representation)
     */
    data: number[];
    /**
     * Tags associated with this control vector
     */
    tags?: string[];
}
/**
 * Options for retrieving control vectors
 */
export interface GetControlVectorsOptions {
    /**
     * Filter by model name
     */
    model?: string;
    /**
     * Filter by layer name
     */
    layer?: string;
    /**
     * Filter by tag
     */
    tag?: string;
    /**
     * Maximum number of control vectors to return
     */
    limit?: number;
}
/**
 * Class for working with control vectors
 */
export declare class ControlVectorAPI {
    private client;
    /**
     * Create a new ControlVectorAPI instance
     * @param client Wisent client instance
     */
    constructor(client: WisentClient);
    /**
     * Get control vectors based on specified criteria
     * @param options Options for filtering control vectors
     * @returns Promise resolving to an array of control vectors
     */
    getControlVectors(options?: GetControlVectorsOptions): Promise<ControlVector[]>;
    /**
     * Get a specific control vector by ID
     * @param id Control Vector ID
     * @returns Promise resolving to the control vector
     */
    getControlVector(id: string): Promise<ControlVector>;
    /**
     * Create a new control vector
     * @param controlVector Control vector data to create
     * @returns Promise resolving to the created control vector
     */
    createControlVector(controlVector: Omit<ControlVector, 'id' | 'createdAt'>): Promise<ControlVector>;
}
