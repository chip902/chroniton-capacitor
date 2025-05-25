/**
 * Calendar Microservice Client for Next.js Applications
 *
 * This client provides a simple interface for integrating with the Calendar Microservice
 * from a Next.js application. It handles authentication, event fetching, and synchronization.
 */

import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';

// Type definitions
export enum CalendarProvider {
  GOOGLE = 'google',
  MICROSOFT = 'microsoft',
  APPLE = 'apple',
  EXCHANGE = 'exchange'
}

export interface CalendarCredentials {
  token_type: string;
  access_token: string;
  refresh_token?: string;
  expires_at?: number;
  tenant_id?: string; // For Microsoft only
  
  // For Exchange/Mailcow ActiveSync
  exchange_url?: string;
  username?: string;
  password?: string;
}

export interface EventParticipant {
  email?: string;
  name?: string;
  responseStatus?: string;
}

export interface CalendarEvent {
  id: string;
  provider: CalendarProvider;
  providerId: string;
  title: string;
  description?: string;
  location?: string;
  startTime: string; // ISO datetime string
  endTime: string; // ISO datetime string
  allDay: boolean;
  organizer?: EventParticipant;
  participants: EventParticipant[];
  recurring: boolean;
  recurrencePattern?: string;
  calendarId: string;
  calendarName?: string;
  link?: string;
  private: boolean;
  status?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface CalendarInfo {
  id: string;
  summary?: string; // Google
  name?: string; // Microsoft
  description?: string;
  location?: string;
  timeZone?: string;
  accessRole?: string;
  primary?: boolean; // Google
  isDefaultCalendar?: boolean; // Microsoft
  color?: string;
  hexColor?: string;
}

export interface SyncSource {
  id: string;
  name: string;
  providerType: string;
  connectionInfo: Record<string, any>;
  credentials?: Record<string, any>;
  syncDirection: 'read_only' | 'write_only' | 'bidirectional';
  syncFrequency: 'real_time' | 'hourly' | 'daily' | 'manual';
  syncMethod: 'api' | 'agent' | 'file' | 'email';
  calendars: string[];
  lastSync?: string;
  syncTokens: Record<string, string>;
  enabled: boolean;
}

export interface SyncDestination {
  id: string;
  name: string;
  providerType: string;
  connectionInfo: Record<string, any>;
  credentials?: Record<string, any>;
  calendarId: string;
  conflictResolution: 'source_wins' | 'destination_wins' | 'latest_wins' | 'manual';
  categories: Record<string, string>;
  // New fields for color management
  sourceCalendars: Record<string, string>;
  colorManagement: 'category' | 'property' | 'separate_calendar';
}

export interface SyncConfiguration {
  sources: SyncSource[];
  destination: SyncDestination;
  agents: any[]; // Not typically managed from client side
  globalSettings: Record<string, any>;
}

export interface SyncResult {
  status: string;
  sourcesSync?: number;
  eventsSync?: number;
  errors: string[];
  startTime: string;
  endTime?: string;
}

// Main Calendar Client
export class CalendarClient {
  private api: AxiosInstance;
  private credentials: Record<string, CalendarCredentials> = {};
  private calendarSelections: Record<string, string[]> = {};
  private syncTokens: Record<string, Record<string, string>> = {
    [CalendarProvider.GOOGLE]: {},
    [CalendarProvider.MICROSOFT]: {},
    [CalendarProvider.APPLE]: {},
    [CalendarProvider.EXCHANGE]: {}
  };

  /**
   * Create a new Calendar Client instance
   * 
   * @param baseURL The base URL of the Calendar Microservice
   */
  constructor(baseURL: string) {
    this.api = axios.create({
      baseURL,
      timeout: 30000 // 30 seconds
    });
  }

  /**
   * Set provider credentials
   * 
   * @param provider The calendar provider (GOOGLE or MICROSOFT)
   * @param credentials The OAuth credentials
   */
  public setCredentials(provider: CalendarProvider, credentials: CalendarCredentials): void {
    this.credentials[provider] = credentials;
  }

  /**
   * Get authentication URL for a calendar provider
   * 
   * @param provider The calendar provider to authenticate with
   * @param tenantId Optional tenant ID for Microsoft authentication
   * @returns Authentication URL to redirect the user to
   */
  public async getAuthUrl(provider: CalendarProvider, tenantId?: string): Promise<string> {
    try {
      // For Exchange/Mailcow, there's no OAuth flow - return empty string
      if (provider === CalendarProvider.EXCHANGE) {
        return '';
      }
      
      const endpoint = `/api/auth/${provider.toLowerCase()}${tenantId ? `?tenant_id=${tenantId}` : ''}`;
      const response = await this.api.get(endpoint);
      return response.data.auth_url;
    } catch (error: any) {
      console.error(`Error getting auth URL for ${provider}:`, error.response?.data || error.message);
      throw error;
    }
  }
  
  /**
   * Authenticate with Exchange/Mailcow server using basic auth
   * 
   * @param exchangeUrl The Exchange server URL
   * @param username The username for authentication
   * @param password The password for authentication
   * @returns The authentication credentials
   */
  public async authenticateExchange(
    exchangeUrl: string, 
    username: string, 
    password: string
  ): Promise<CalendarCredentials> {
    try {
      const endpoint = '/api/auth/exchange';
      const response = await this.api.post(endpoint, {
        exchange_url: exchangeUrl,
        username,
        password
      });
      
      const credentials: CalendarCredentials = response.data;
      
      // Store credentials for future use
      this.setCredentials(CalendarProvider.EXCHANGE, credentials);
      
      return credentials;
    } catch (error: any) {
      console.error('Error authenticating with Exchange:', error.response?.data || error.message);
      throw error;
    }
  }

  /**
   * Exchange authentication code for OAuth tokens
   * 
   * @param provider The calendar provider
   * @param code The authorization code
   * @param state Optional state/tenant ID from the OAuth flow
   * @returns The OAuth credentials
   */
  public async exchangeAuthCode(
    provider: CalendarProvider, 
    code: string, 
    state?: string
  ): Promise<CalendarCredentials> {
    try {
      const endpoint = `/api/auth/${provider.toLowerCase()}/callback`;
      const params = new URLSearchParams();
      params.append('code', code);
      if (state) {
        params.append('state', state);
      }
      
      const response = await this.api.get(`${endpoint}?${params.toString()}`);
      const credentials: CalendarCredentials = response.data;
      
      // Store credentials for future use
      this.setCredentials(provider, credentials);
      
      return credentials;
    } catch (error: any) {
      console.error(`Error exchanging auth code for ${provider}:`, error.response?.data || error.message);
      throw error;
    }
  }

  /**
   * List available calendars for authenticated providers
   * 
   * @returns Object mapping provider names to lists of calendars
   */
  public async listCalendars(): Promise<Record<string, CalendarInfo[]>> {
    try {
      // Encode credentials as JSON for the API
      const credentialsStr = JSON.stringify(this.credentials);
      
      const response = await this.api.get('/api/calendars', {
        params: { credentials: credentialsStr }
      });
      
      return response.data;
    } catch (error: any) {
      console.error('Error listing calendars:', error.response?.data || error.message);
      throw error;
    }
  }

  /**
   * Set calendar selections for fetching events
   * 
   * @param selections Object mapping provider names to lists of calendar IDs
   */
  public setCalendarSelections(selections: Record<string, string[]>): void {
    this.calendarSelections = selections;
  }

  /**
   * Fetch events from selected calendars
   * 
   * @param startDate Optional start date for the event range
   * @param endDate Optional end date for the event range
   * @returns Object with events and sync tokens
   */
  public async getEvents(
    startDate?: Date,
    endDate?: Date
  ): Promise<{ events: CalendarEvent[], syncTokens: Record<string, Record<string, string>> }> {
    try {
      // Encode parameters as JSON for the API
      const credentialsStr = JSON.stringify(this.credentials);
      const calendarsStr = JSON.stringify(this.calendarSelections);
      const syncTokensStr = JSON.stringify(this.syncTokens);
      
      // Prepare query parameters
      const params: Record<string, string> = {
        credentials: credentialsStr,
        calendars: calendarsStr,
        sync_tokens: syncTokensStr
      };
      
      // Add optional date parameters if provided
      if (startDate) {
        params.start = startDate.toISOString();
      }
      
      if (endDate) {
        params.end = endDate.toISOString();
      }
      
      // Make API call
      const response = await this.api.get('/api/events', { params });
      
      // Update sync tokens for next request
      this.syncTokens = response.data.syncTokens;
      
      // Convert snake_case to camelCase for event properties
      const events: CalendarEvent[] = response.data.events.map((event: any) => ({
        id: event.id,
        provider: event.provider,
        providerId: event.provider_id,
        title: event.title,
        description: event.description,
        location: event.location,
        startTime: event.start_time,
        endTime: event.end_time,
        allDay: event.all_day,
        organizer: event.organizer,
        participants: event.participants,
        recurring: event.recurring,
        recurrencePattern: event.recurrence_pattern,
        calendarId: event.calendar_id,
        calendarName: event.calendar_name,
        link: event.link,
        private: event.private,
        status: event.status,
        createdAt: event.created_at,
        updatedAt: event.updated_at
      }));
      
      return {
        events,
        syncTokens: this.syncTokens
      };
    } catch (error: any) {
      console.error('Error fetching events:', error.response?.data || error.message);
      throw error;
    }
  }

  // Sync Configuration Management
  
  /**
   * Get the current synchronization configuration
   */
  public async getSyncConfiguration(): Promise<SyncConfiguration> {
    try {
      const response = await this.api.get('/api/sync/config');
      return response.data;
    } catch (error: any) {
      console.error('Error getting sync configuration:', error.response?.data || error.message);
      throw error;
    }
  }
  
  /**
   * Configure the destination calendar for synchronization
   */
  public async configureDestination(destination: SyncDestination): Promise<SyncDestination> {
    try {
      const response = await this.api.post('/api/sync/config/destination', destination);
      return response.data;
    } catch (error: any) {
      console.error('Error configuring destination:', error.response?.data || error.message);
      throw error;
    }
  }
  
  /**
   * Add a new synchronization source
   */
  public async addSyncSource(source: SyncSource): Promise<SyncSource> {
    try {
      const response = await this.api.post('/api/sync/sources', source);
      return response.data;
    } catch (error: any) {
      console.error('Error adding sync source:', error.response?.data || error.message);
      throw error;
    }
  }
  
  /**
   * Update an existing synchronization source
   */
  public async updateSyncSource(sourceId: string, updates: Partial<SyncSource>): Promise<SyncSource> {
    try {
      const response = await this.api.put(`/api/sync/sources/${sourceId}`, updates);
      return response.data;
    } catch (error: any) {
      console.error('Error updating sync source:', error.response?.data || error.message);
      throw error;
    }
  }
  
  /**
   * Remove a synchronization source
   */
  public async removeSyncSource(sourceId: string): Promise<{ status: string, message: string }> {
    try {
      const response = await this.api.delete(`/api/sync/sources/${sourceId}`);
      return response.data;
    } catch (error: any) {
      console.error('Error removing sync source:', error.response?.data || error.message);
      throw error;
    }
  }
  
  /**
   * Run synchronization for all sources
   */
  public async runSync(): Promise<SyncResult> {
    try {
      const response = await this.api.post('/api/sync/run');
      return response.data;
    } catch (error: any) {
      console.error('Error running sync:', error.response?.data || error.message);
      throw error;
    }
  }
  
  /**
   * Run synchronization for a single source
   */
  public async runSourceSync(sourceId: string): Promise<SyncResult> {
    try {
      const response = await this.api.post(`/api/sync/run/${sourceId}`);
      return response.data;
    } catch (error: any) {
      console.error(`Error running sync for source ${sourceId}:`, error.response?.data || error.message);
      throw error;
    }
  }
}