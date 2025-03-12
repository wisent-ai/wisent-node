import axios, { AxiosInstance } from 'axios';
import { version } from './version';

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
export class WisentClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly httpClient: AxiosInstance;
  
  /**
   * Creates a new Wisent client instance
   * @param config Configuration options for the client
   */
  constructor(config: WisentClientConfig) {
    this.apiKey = config.apiKey;
    this.baseUrl = config.baseUrl || 'https://api.wisent.ai';
    
    this.httpClient = axios.create({
      baseURL: this.baseUrl,
      timeout: config.timeout || 30000,
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'User-Agent': `wisent-js/${version}`,
        'Content-Type': 'application/json',
      }
    });
  }
  
  /**
   * Get the current API key
   */
  getApiKey(): string {
    return this.apiKey;
  }
  
  /**
   * Get the base URL for API requests
   */
  getBaseUrl(): string {
    return this.baseUrl;
  }
  
  /**
   * Get the HTTP client instance
   * @internal
   */
  getHttpClient(): AxiosInstance {
    return this.httpClient;
  }
} 