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
   * Base URL of the Wisent API the client calls; required, since the client
   * assumes no address for it
   */
  baseUrl: string;
}

/**
 * Main client for interacting with Wisent AI services. A request waits for
 * the API's answer; a failed request rejects with the API's or the
 * network's own error.
 */
export class WisentClient {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly httpClient: AxiosInstance;

  /**
   * Creates a new Wisent client instance
   * @param config Configuration options for the client
   * @throws Error naming the option when apiKey or baseUrl is missing or empty
   */
  constructor(config: WisentClientConfig) {
    if (typeof config.apiKey !== 'string' || !config.apiKey.trim()) {
      throw new Error('WisentClient needs apiKey, the API key the Wisent API issued you');
    }
    if (typeof config.baseUrl !== 'string' || !config.baseUrl.trim()) {
      throw new Error('WisentClient needs baseUrl, the address of the Wisent API it calls');
    }
    this.apiKey = config.apiKey;
    this.baseUrl = config.baseUrl;

    this.httpClient = axios.create({
      baseURL: this.baseUrl,
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
