"use strict";
// Wisent AI Client Library
// Main entry point for the package
Object.defineProperty(exports, "__esModule", { value: true });
exports.euclideanDistance = exports.subtractVectors = exports.addVectors = exports.scaleVector = exports.cosineSimilarity = exports.InferenceAPI = exports.ControlVectorAPI = exports.ActivationsAPI = exports.WisentClient = exports.version = void 0;
exports.default = createWisentClient;
// Export version information
var version_1 = require("./version");
Object.defineProperty(exports, "version", { enumerable: true, get: function () { return version_1.version; } });
// Export client
var client_1 = require("./client");
Object.defineProperty(exports, "WisentClient", { enumerable: true, get: function () { return client_1.WisentClient; } });
// Export activations module
var activations_1 = require("./activations");
Object.defineProperty(exports, "ActivationsAPI", { enumerable: true, get: function () { return activations_1.ActivationsAPI; } });
// Export control vector module
var control_vector_1 = require("./control_vector");
Object.defineProperty(exports, "ControlVectorAPI", { enumerable: true, get: function () { return control_vector_1.ControlVectorAPI; } });
// Export inference module
var inference_1 = require("./inference");
Object.defineProperty(exports, "InferenceAPI", { enumerable: true, get: function () { return inference_1.InferenceAPI; } });
// Export utility functions
var utils_1 = require("./utils");
Object.defineProperty(exports, "cosineSimilarity", { enumerable: true, get: function () { return utils_1.cosineSimilarity; } });
Object.defineProperty(exports, "scaleVector", { enumerable: true, get: function () { return utils_1.scaleVector; } });
Object.defineProperty(exports, "addVectors", { enumerable: true, get: function () { return utils_1.addVectors; } });
Object.defineProperty(exports, "subtractVectors", { enumerable: true, get: function () { return utils_1.subtractVectors; } });
Object.defineProperty(exports, "euclideanDistance", { enumerable: true, get: function () { return utils_1.euclideanDistance; } });
// Create a default export for convenience
const client_2 = require("./client");
const activations_2 = require("./activations");
const control_vector_2 = require("./control_vector");
const inference_2 = require("./inference");
/**
 * Create a complete Wisent client with all APIs
 * @param apiKey API key for authentication
 * @param baseUrl Optional base URL for the API
 * @returns Object containing all Wisent APIs
 */
function createWisentClient(apiKey, baseUrl) {
    const client = new client_2.WisentClient({ apiKey, baseUrl });
    return {
        client,
        activations: new activations_2.ActivationsAPI(client),
        controlVectors: new control_vector_2.ControlVectorAPI(client),
        inference: new inference_2.InferenceAPI(client)
    };
}
