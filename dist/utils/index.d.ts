/**
 * Utilities module for Wisent AI
 *
 * This module provides utility functions for working with the Wisent API.
 */
/**
 * Calculate the cosine similarity between two vectors
 * @param a First vector
 * @param b Second vector
 * @returns Cosine similarity value between -1 and 1
 */
export declare function cosineSimilarity(a: number[], b: number[]): number;
/**
 * Scale a vector by a scalar value
 * @param vector Vector to scale
 * @param scale Scaling factor
 * @returns Scaled vector
 */
export declare function scaleVector(vector: number[], scale: number): number[];
/**
 * Add two vectors together
 * @param a First vector
 * @param b Second vector
 * @returns Sum of the vectors
 */
export declare function addVectors(a: number[], b: number[]): number[];
/**
 * Subtract one vector from another
 * @param a First vector
 * @param b Second vector to subtract from the first
 * @returns Difference of the vectors
 */
export declare function subtractVectors(a: number[], b: number[]): number[];
/**
 * Calculate the Euclidean distance between two vectors
 * @param a First vector
 * @param b Second vector
 * @returns Euclidean distance
 */
export declare function euclideanDistance(a: number[], b: number[]): number;
