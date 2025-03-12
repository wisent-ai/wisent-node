"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.WisentClient = void 0;
const axios_1 = __importDefault(require("axios"));
const version_1 = require("./version");
/**
 * Main client for interacting with Wisent AI services
 */
class WisentClient {
    /**
     * Creates a new Wisent client instance
     * @param config Configuration options for the client
     */
    constructor(config) {
        this.apiKey = config.apiKey;
        this.baseUrl = config.baseUrl || 'https://api.wisent.ai';
        this.httpClient = axios_1.default.create({
            baseURL: this.baseUrl,
            timeout: config.timeout || 30000,
            headers: {
                'Authorization': `Bearer ${this.apiKey}`,
                'User-Agent': `wisent-js/${version_1.version}`,
                'Content-Type': 'application/json',
            }
        });
    }
    /**
     * Get the current API key
     */
    getApiKey() {
        return this.apiKey;
    }
    /**
     * Get the base URL for API requests
     */
    getBaseUrl() {
        return this.baseUrl;
    }
    /**
     * Get the HTTP client instance
     * @internal
     */
    getHttpClient() {
        return this.httpClient;
    }
}
exports.WisentClient = WisentClient;
