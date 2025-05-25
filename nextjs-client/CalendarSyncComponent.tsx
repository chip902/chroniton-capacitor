/**
 * Calendar Sync Component for Next.js Applications
 * 
 * This component provides a UI for configuring and managing calendar synchronization.
 */

import React, { useState, useEffect } from 'react';
import { 
  CalendarClient, 
  CalendarProvider, 
  CalendarEvent,

  CalendarInfo,
  SyncSource,
  SyncDestination,
  SyncConfiguration
} from './CalendarClient';

// Initial setup with environment variables
const API_URL = process.env.NEXT_PUBLIC_CALENDAR_API_URL || 'http://localhost:8000';
const calendarClient = new CalendarClient(API_URL);

interface CalendarSyncProps {
  onEventsLoaded?: (events: CalendarEvent[]) => void;
  onSyncComplete?: (result: any) => void;
}

const CalendarSyncComponent: React.FC<CalendarSyncProps> = ({ 
  onEventsLoaded,
  onSyncComplete
}) => {
  // Authentication state
  const [googleAuth, setGoogleAuth] = useState<boolean>(false);
  const [microsoftAuth, setMicrosoftAuth] = useState<boolean>(false);
  
  // Calendar data
  const [calendars, setCalendars] = useState<Record<string, CalendarInfo[]>>({});
  const [selectedCalendars, setSelectedCalendars] = useState<Record<string, string[]>>({});
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  
  // Sync configuration
  const [syncConfig, setSyncConfig] = useState<SyncConfiguration | null>(null);
  const [syncSources, setSyncSources] = useState<SyncSource[]>([]);
  const [destination, setDestination] = useState<SyncDestination | null>(null);
  
  // UI state
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  
  // Load existing configuration on mount
  useEffect(() => {
    loadSyncConfiguration();
  }, []);
  
  // Load the current synchronization configuration
  const loadSyncConfiguration = async () => {
    try {
      setLoading(true);
      const config = await calendarClient.getSyncConfiguration();
      setSyncConfig(config);
      setSyncSources(config.sources || []);
      setDestination(config.destination || null);
      setLoading(false);
    } catch (err: any) {
      setError('Failed to load configuration: ' + err.message);
      setLoading(false);
    }
  };
  
  // Handle Google authentication
  const authenticateGoogle = async () => {
    try {
      const authUrl = await calendarClient.getAuthUrl(CalendarProvider.GOOGLE);
      // Store current URL to return after auth
      sessionStorage.setItem('calendarReturnUrl', window.location.href);
      // Redirect to Google auth
      window.location.href = authUrl;
    } catch (err: any) {
      setError('Google authentication failed: ' + err.message);
    }
  };
  
  // Handle Microsoft authentication
  const authenticateMicrosoft = async (tenantId?: string) => {
    try {
      const authUrl = await calendarClient.getAuthUrl(CalendarProvider.MICROSOFT, tenantId);
      // Store current URL to return after auth
      sessionStorage.setItem('calendarReturnUrl', window.location.href);
      // Redirect to Microsoft auth
      window.location.href = authUrl;
    } catch (err: any) {
      setError('Microsoft authentication failed: ' + err.message);
    }
  };
  
  // Handle OAuth callback
  const handleAuthCallback = async (provider: CalendarProvider, code: string, state?: string) => {
    try {
      setLoading(true);
      const credentials = await calendarClient.exchangeAuthCode(provider, code, state);
      
      if (provider === CalendarProvider.GOOGLE) {
        setGoogleAuth(true);
      } else if (provider === CalendarProvider.MICROSOFT) {
        setMicrosoftAuth(true);
      }
      
      setMessage(`${provider} authentication successful`);
      setLoading(false);
      
      // Load calendars after successful authentication
      await loadCalendars();
      
      // Return to the original page if stored
      const returnUrl = sessionStorage.getItem('calendarReturnUrl');
      if (returnUrl) {
        sessionStorage.removeItem('calendarReturnUrl');
        window.location.href = returnUrl;
      }
    } catch (err: any) {
      setError(`Authentication failed: ${err.message}`);
      setLoading(false);
    }
  };
  
  // Load available calendars
  const loadCalendars = async () => {
    try {
      setLoading(true);
      const calendarData = await calendarClient.listCalendars();
      setCalendars(calendarData);
      setLoading(false);
    } catch (err: any) {
      setError('Failed to load calendars: ' + err.message);
      setLoading(false);
    }
  };
  
  // Handle calendar selection changes
  const handleCalendarSelectionChange = (provider: string, calendarId: string, selected: boolean) => {
    setSelectedCalendars(prev => {
      const current = {...prev};
      if (!current[provider]) {
        current[provider] = [];
      }
      
      if (selected && !current[provider].includes(calendarId)) {
        current[provider] = [...current[provider], calendarId];
      } else if (!selected && current[provider].includes(calendarId)) {
        current[provider] = current[provider].filter(id => id !== calendarId);
      }
      
      return current;
    });
  };
  
  // Save calendar selections for future use
  const saveCalendarSelections = () => {
    calendarClient.setCalendarSelections(selectedCalendars);
    setMessage('Calendar selections saved');
  };
  
  // Load events from selected calendars
  const loadEvents = async (startDate?: Date, endDate?: Date) => {
    try {
      setLoading(true);
      const result = await calendarClient.getEvents(startDate, endDate);
      setEvents(result.events);
      setLoading(false);
      
      // Notify parent component if needed
      if (onEventsLoaded) {
        onEventsLoaded(result.events);
      }
    } catch (err: any) {
      setError('Failed to load events: ' + err.message);
      setLoading(false);
    }
  };
  
  // Configure destination calendar
  const configureDestination = async (dest: SyncDestination) => {
    try {
      setLoading(true);
      const result = await calendarClient.configureDestination(dest);
      setDestination(result);
      setMessage('Destination calendar configured successfully');
      setLoading(false);
    } catch (err: any) {
      setError('Failed to configure destination: ' + err.message);
      setLoading(false);
    }
  };
  
  // Add a new sync source
  const addSyncSource = async (source: SyncSource) => {
    try {
      setLoading(true);
      const result = await calendarClient.addSyncSource(source);
      setSyncSources(prev => [...prev, result]);
      setMessage('Sync source added successfully');
      setLoading(false);
    } catch (err: any) {
      setError('Failed to add sync source: ' + err.message);
      setLoading(false);
    }
  };
  
  // Update an existing sync source
  const updateSyncSource = async (sourceId: string, updates: Partial<SyncSource>) => {
    try {
      setLoading(true);
      const result = await calendarClient.updateSyncSource(sourceId, updates);
      setSyncSources(prev => prev.map(source => 
        source.id === sourceId ? result : source
      ));
      setMessage('Sync source updated successfully');
      setLoading(false);
    } catch (err: any) {
      setError('Failed to update sync source: ' + err.message);
      setLoading(false);
    }
  };
  
  // Remove a sync source
  const removeSyncSource = async (sourceId: string) => {
    try {
      setLoading(true);
      await calendarClient.removeSyncSource(sourceId);
      setSyncSources(prev => prev.filter(source => source.id !== sourceId));
      setMessage('Sync source removed successfully');
      setLoading(false);
    } catch (err: any) {
      setError('Failed to remove sync source: ' + err.message);
      setLoading(false);
    }
  };
  
  // Run synchronization for all sources
  const runSync = async () => {
    try {
      setLoading(true);
      const result = await calendarClient.runSync();
      setMessage(`Sync completed: ${result.eventsSync} events synchronized`);
      setLoading(false);
      
      // Notify parent component if needed
      if (onSyncComplete) {
        onSyncComplete(result);
      }
    } catch (err: any) {
      setError('Sync failed: ' + err.message);
      setLoading(false);
    }
  };
  
  // Run synchronization for a specific source
  const runSourceSync = async (sourceId: string) => {
    try {
      setLoading(true);
      const result = await calendarClient.runSourceSync(sourceId);
      setMessage(`Source sync completed: ${result.eventsSync} events synchronized`);
      setLoading(false);
      
      // Notify parent component if needed
      if (onSyncComplete) {
        onSyncComplete(result);
      }
    } catch (err: any) {
      setError(`Source sync failed: ${err.message}`);
      setLoading(false);
    }
  };
  
  // Create a new calendar source from credentials and selection
  const createSourceFromSelection = () => {
    // This method would create a SyncSource object from the current
    // authentication credentials and calendar selections
    // For demonstration purposes, we'll just show the basic structure
    
    const newSources: SyncSource[] = [];
    
    // Create a source for each provider that has selected calendars
    Object.entries(selectedCalendars).forEach(([provider, calendarIds]) => {
      if (calendarIds.length > 0) {
        const credentials = provider === CalendarProvider.GOOGLE 
          ? calendarClient['credentials'][CalendarProvider.GOOGLE] 
          : calendarClient['credentials'][CalendarProvider.MICROSOFT];
        
        const newSource: SyncSource = {
          id: `source_${Date.now()}`,
          name: `${provider} Source`,
          providerType: provider,
          connectionInfo: {},
          credentials,
          syncDirection: 'read_only',
          syncFrequency: 'hourly',
          syncMethod: 'api',
          calendars: calendarIds,
          syncTokens: {},
          enabled: true
        };
        
        newSources.push(newSource);
      }
    });
    
    return newSources;
  };
  
  // Add sources based on current selections
  const addSourcesFromSelection = async () => {
    const sources = createSourceFromSelection();
    
    setLoading(true);
    for (const source of sources) {
      try {
        await addSyncSource(source);
      } catch (err: any) {
        setError(`Failed to add source ${source.name}: ${err.message}`);
      }
    }
    setLoading(false);
    
    await loadSyncConfiguration();
  };
  
  // Create a destination from the selected calendar
  const createDestinationFromSelection = async (providerId: string, calendarId: string) => {
    if (!providerId || !calendarId) {
      setError('Please select a provider and calendar');
      return;
    }
    
    try {
      const credentials = providerId === CalendarProvider.GOOGLE 
        ? calendarClient['credentials'][CalendarProvider.GOOGLE] 
        : calendarClient['credentials'][CalendarProvider.MICROSOFT];
      
      // Find the calendar info
      const calendarInfo = calendars[providerId]?.find(cal => cal.id === calendarId);
      
      const newDestination: SyncDestination = {
        id: `destination_${Date.now()}`,
        name: calendarInfo?.summary || calendarInfo?.name || 'Unified Calendar',
        providerType: providerId,
        connectionInfo: {},
        credentials,
        calendarId,
        conflictResolution: 'latest_wins',
        categories: {},
        // New fields for color management
        sourceCalendars: {},
        colorManagement: 'separate_calendar' // Default to separate calendars for better color support
      };
      
      await configureDestination(newDestination);
    } catch (err: any) {
      setError(`Failed to configure destination: ${err.message}`);
    }
  };
  
  // Render calendar selection UI
  const renderCalendarSelection = () => {
    return (
      <div className="calendar-selection">
        <h3>Select Calendars to Sync</h3>
        
        {Object.entries(calendars).map(([provider, providerCalendars]) => (
          <div key={provider} className="provider-section">
            <h4>{provider === 'google' ? 'Google Calendars' : 'Microsoft Calendars'}</h4>
            
            {providerCalendars.map(calendar => (
              <div key={calendar.id} className="calendar-item">
                <label>
                  <input 
                    type="checkbox"
                    checked={selectedCalendars[provider]?.includes(calendar.id) || false}
                    onChange={(e) => handleCalendarSelectionChange(
                      provider, 
                      calendar.id, 
                      e.target.checked
                    )}
                  />
                  {' '}
                  {calendar.summary || calendar.name || calendar.id}
                  {calendar.primary || calendar.isDefaultCalendar ? ' (Primary)' : ''}
                </label>
              </div>
            ))}
          </div>
        ))}
        
        <div className="actions">
          <button onClick={saveCalendarSelections} disabled={loading}>
            Save Selections
          </button>
          <button onClick={() => loadEvents()} disabled={loading}>
            Load Events
          </button>
          <button onClick={addSourcesFromSelection} disabled={loading}>
            Add as Sync Sources
          </button>
        </div>
      </div>
    );
  };
  
  // Render sync configuration UI
  const renderSyncConfiguration = () => {
    return (
      <div className="sync-configuration">
        <h3>Synchronization Configuration</h3>
        
        <div className="destination-section">
          <h4>Destination Calendar</h4>
          {destination ? (
            <div className="destination-info">
              <p><strong>Name:</strong> {destination.name}</p>
              <p><strong>Provider:</strong> {destination.providerType}</p>
              <p><strong>Calendar ID:</strong> {destination.calendarId}</p>
              <p><strong>Conflict Resolution:</strong> {destination.conflictResolution}</p>
              <button 
                onClick={() => setDestination(null)} 
                disabled={loading}
                className="danger"
              >
                Remove Destination
              </button>
            </div>
          ) : (
            <div className="destination-selector">
              <p>Select a calendar to use as the destination for all synced events:</p>
              
              <select id="destination-provider">
                <option value="">-- Select Provider --</option>
                {Object.keys(calendars).map(provider => (
                  <option key={provider} value={provider}>
                    {provider === 'google' ? 'Google' : 'Microsoft'}
                  </option>
                ))}
              </select>
              
              <select id="destination-calendar">
                <option value="">-- Select Calendar --</option>
                {/* Dynamically populate based on selected provider */}
                {(document.getElementById('destination-provider') as HTMLSelectElement)?.value && 
                  calendars[(document.getElementById('destination-provider') as HTMLSelectElement).value]?.map(calendar => (
                    <option key={calendar.id} value={calendar.id}>
                      {calendar.summary || calendar.name || calendar.id}
                    </option>
                  ))
                }
              </select>
              
              <button 
                onClick={() => createDestinationFromSelection(
                  (document.getElementById('destination-provider') as HTMLSelectElement).value,
                  (document.getElementById('destination-calendar') as HTMLSelectElement).value
                )} 
                disabled={loading}
              >
                Set as Destination
              </button>
            </div>
          )}
        </div>
        
        <div className="sources-section">
          <h4>Sync Sources</h4>
          {syncSources.length === 0 ? (
            <p>No sync sources configured. Add calendars as sources to begin syncing.</p>
          ) : (
            <div className="sources-list">
              {syncSources.map(source => (
                <div key={source.id} className="source-item">
                  <h5>{source.name}</h5>
                  <p><strong>Provider:</strong> {source.providerType}</p>
                  <p><strong>Calendars:</strong> {source.calendars.length}</p>
                  <p><strong>Sync Direction:</strong> {source.syncDirection}</p>
                  <p><strong>Last Sync:</strong> {source.lastSync || 'Never'}</p>
                  <div className="source-actions">
                    <button 
                      onClick={() => runSourceSync(source.id)} 
                      disabled={loading || !destination}
                    >
                      Sync Now
                    </button>
                    <button 
                      onClick={() => {
                        const enabled = !source.enabled;
                        updateSyncSource(source.id, { enabled });
                      }} 
                      disabled={loading}
                    >
                      {source.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button 
                      onClick={() => removeSyncSource(source.id)} 
                      disabled={loading}
                      className="danger"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        
        <div className="sync-actions">
          <button 
            onClick={runSync} 
            disabled={loading || !destination || syncSources.length === 0}
            className="primary"
          >
            Synchronize All Calendars
          </button>
        </div>
      </div>
    );
  };
  
  // Render events list
  const renderEvents = () => {
    if (events.length === 0) {
      return <p>No events to display. Select calendars and load events.</p>;
    }
    
    return (
      <div className="events-list">
        <h3>Calendar Events</h3>
        {events.map(event => (
          <div key={event.id} className="event-item">
            <h4>{event.title}</h4>
            <p><strong>When:</strong> {new Date(event.startTime).toLocaleString()} - {new Date(event.endTime).toLocaleString()}</p>
            <p><strong>Calendar:</strong> {event.calendarName}</p>
            <p><strong>Provider:</strong> {event.provider}</p>
            {event.location && <p><strong>Location:</strong> {event.location}</p>}
            {event.description && <p><strong>Description:</strong> {event.description}</p>}
          </div>
        ))}
      </div>
    );
  };
  
  return (
    <div className="calendar-sync-component">
      <h2>Calendar Synchronization</h2>
      
      {/* Error/message display */}
      {error && <div className="error-message">{error}</div>}
      {message && <div className="success-message">{message}</div>}
      
      {/* Authentication section */}
      <div className="authentication-section">
        <h3>Calendar Authentication</h3>
        <div className="auth-buttons">
          <button 
            onClick={authenticateGoogle} 
            disabled={loading || googleAuth}
            className={googleAuth ? 'connected' : ''}
          >
            {googleAuth ? 'Connected to Google' : 'Connect Google Calendar'}
          </button>
          
          <button 
            onClick={() => authenticateMicrosoft()} 
            disabled={loading || microsoftAuth}
            className={microsoftAuth ? 'connected' : ''}
          >
            {microsoftAuth ? 'Connected to Microsoft' : 'Connect Microsoft Calendar'}
          </button>
        </div>
        
        {(googleAuth || microsoftAuth) && (
          <button onClick={loadCalendars} disabled={loading}>
            Load Available Calendars
          </button>
        )}
      </div>
      
      {/* Calendar selection */}
      {Object.keys(calendars).length > 0 && renderCalendarSelection()}
      
      {/* Sync configuration */}
      {renderSyncConfiguration()}
      
      {/* Events display */}
      {events.length > 0 && renderEvents()}
      
      {/* Loading indicator */}
      {loading && <div className="loading-indicator">Loading...</div>}
    </div>
  );
};

export default CalendarSyncComponent;