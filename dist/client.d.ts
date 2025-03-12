import { AxiosInstance } from 'axios';
/**
 * Configuration options for the Wisent client
 */
export interface WisentClientConfig {
    /**
     * API key for authentication with Wisent services
     */
    apiKey: string;
    /**
     * Base URL for the Wisent API (optional)
     * @default "https://api.wisent.ai"
     */
    baseUrl?: string;
    /**
     * Timeout for API requests in milliseconds (optional)
     * @default 30000 (30 seconds)
     */
    timeout?: number;
}
/**
 * Main client for interacting with Wisent AI services
 */
export declare class WisentClient {
    private readonly apiKey;
    private readonly baseUrl;
    private readonly httpClient;
    /**
     * Creates a new Wisent client instance
     * @param config Configuration options for the client
     */
    constructor(config: WisentClientConfig);
    /**
     * Get the current API key
     */
    getApiKey(): string;
    /**
     * Get the base URL for API requests
     */
    getBaseUrl(): string;
    /**
     * Get the HTTP client instance
     * @internal
     */
    getHttpClient(): AxiosInstance;
}
