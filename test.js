// Simple test script for the Wisent client library
const wisent = require('./dist');

// Display the version
console.log(`Wisent client library version: ${wisent.version}`);

// Create a client instance
const client = wisent.default('test-api-key', 'https://api.example.com');

// Log the client structure
console.log('Client structure:');
console.log(Object.keys(client));

// Test utility functions
const vectorA = [1, 2, 3];
const vectorB = [4, 5, 6];

console.log('\nVector operations:');
console.log(`Cosine similarity: ${wisent.cosineSimilarity(vectorA, vectorB)}`);
console.log(`Scaled vector: ${wisent.scaleVector(vectorA, 2)}`);
console.log(`Vector addition: ${wisent.addVectors(vectorA, vectorB)}`);
console.log(`Vector subtraction: ${wisent.subtractVectors(vectorA, vectorB)}`);
console.log(`Euclidean distance: ${wisent.euclideanDistance(vectorA, vectorB)}`);

console.log('\nTest completed successfully!'); 