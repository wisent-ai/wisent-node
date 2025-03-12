"use strict";
/**
 * Utilities module for Wisent AI
 *
 * This module provides utility functions for working with the Wisent API.
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.cosineSimilarity = cosineSimilarity;
exports.scaleVector = scaleVector;
exports.addVectors = addVectors;
exports.subtractVectors = subtractVectors;
exports.euclideanDistance = euclideanDistance;
/**
 * Calculate the cosine similarity between two vectors
 * @param a First vector
 * @param b Second vector
 * @returns Cosine similarity value between -1 and 1
 */
function cosineSimilarity(a, b) {
    if (a.length !== b.length) {
        throw new Error('Vectors must have the same length');
    }
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;
    for (let i = 0; i < a.length; i++) {
        dotProduct += a[i] * b[i];
        normA += a[i] * a[i];
        normB += b[i] * b[i];
    }
    if (normA === 0 || normB === 0) {
        return 0;
    }
    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}
/**
 * Scale a vector by a scalar value
 * @param vector Vector to scale
 * @param scale Scaling factor
 * @returns Scaled vector
 */
function scaleVector(vector, scale) {
    return vector.map(value => value * scale);
}
/**
 * Add two vectors together
 * @param a First vector
 * @param b Second vector
 * @returns Sum of the vectors
 */
function addVectors(a, b) {
    if (a.length !== b.length) {
        throw new Error('Vectors must have the same length');
    }
    return a.map((value, index) => value + b[index]);
}
/**
 * Subtract one vector from another
 * @param a First vector
 * @param b Second vector to subtract from the first
 * @returns Difference of the vectors
 */
function subtractVectors(a, b) {
    if (a.length !== b.length) {
        throw new Error('Vectors must have the same length');
    }
    return a.map((value, index) => value - b[index]);
}
/**
 * Calculate the Euclidean distance between two vectors
 * @param a First vector
 * @param b Second vector
 * @returns Euclidean distance
 */
function euclideanDistance(a, b) {
    if (a.length !== b.length) {
        throw new Error('Vectors must have the same length');
    }
    let sum = 0;
    for (let i = 0; i < a.length; i++) {
        const diff = a[i] - b[i];
        sum += diff * diff;
    }
    return Math.sqrt(sum);
}
