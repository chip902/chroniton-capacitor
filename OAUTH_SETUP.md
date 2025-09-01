# OAuth Setup Guide for Chroniton Capacitor

This guide will walk you through setting up OAuth credentials for Google Calendar and Microsoft Graph APIs.

## Google Calendar API Setup

### Step 1: Create Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Name it something like "Chroniton Capacitor Calendar Sync"

### Step 2: Enable Google Calendar API

1. In the Google Cloud Console, go to "APIs & Services" > "Library"
2. Search for "Google Calendar API"
3. Click on it and press "Enable"

### Step 3: Configure OAuth Consent Screen

1. Go to "APIs & Services" > "OAuth consent screen"
2. Choose "External" user type (or "Internal" if you're using Google Workspace)
3. Fill in the required information:
   - **App name**: "Chroniton Capacitor"
   - **User support email**: Your email address
   - **Developer contact information**: Your email address
4. Add scopes:
   - `https://www.googleapis.com/auth/calendar`
   - `https://www.googleapis.com/auth/calendar.events`
5. Add test users (your email and any other emails you want to test with)

### Step 4: Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth 2.0 Client IDs"
3. Choose "Web application"
4. Name it "Chroniton Capacitor OAuth Client"
5. Add authorized redirect URIs:
   - `http://localhost:8008/api/auth/google/callback` (for local development)
   - `https://your-production-domain.com/api/auth/google/callback` (for production)
6. Click "Create"
7. Copy the **Client ID** and **Client Secret**

### Step 5: Update Environment Variables

Add these to your `.env` file:

```bash
# Google Calendar OAuth
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8008/api/auth/google/callback
```

## Microsoft Graph API Setup

### Step 1: Register Application in Azure AD

1. Go to the [Azure Portal](https://portal.azure.com/)
2. Navigate to "Azure Active Directory" > "App registrations"
3. Click "New registration"
4. Fill in the details:
   - **Name**: "Chroniton Capacitor Calendar Sync"
   - **Supported account types**: "Accounts in any organizational directory and personal Microsoft accounts"
   - **Redirect URI**: Select "Web" and enter `http://localhost:8008/api/auth/microsoft/callback`
5. Click "Register"

### Step 2: Configure API Permissions

1. In your app registration, go to "API permissions"
2. Click "Add a permission" > "Microsoft Graph" > "Delegated permissions"
3. Add these permissions:
   - `Calendars.Read`
   - `Calendars.Read.Shared`
   - `Calendars.ReadWrite`
   - `Calendars.ReadWrite.Shared`
   - `offline_access`
   - `User.Read`
4. Click "Add permissions"
5. Click "Grant admin consent" (if you have admin rights)

### Step 3: Create Client Secret

1. Go to "Certificates & secrets" > "Client secrets"
2. Click "New client secret"
3. Add description: "Chroniton Capacitor OAuth Secret"
4. Choose expiration (recommend 24 months)
5. Click "Add"
6. **Important**: Copy the secret value immediately (it won't be shown again)

### Step 4: Configure Authentication

1. Go to "Authentication"
2. Add redirect URIs:
   - `http://localhost:8008/api/auth/microsoft/callback` (for local development)
   - `https://your-production-domain.com/api/auth/microsoft/callback` (for production)
3. Under "Implicit grant and hybrid flows", check:
   - "Access tokens"
   - "ID tokens"
4. Click "Save"

### Step 5: Update Environment Variables

Add these to your `.env` file:

```bash
# Microsoft Graph OAuth
MS_CLIENT_ID=your_microsoft_client_id_here
MS_CLIENT_SECRET=your_microsoft_client_secret_here
MS_REDIRECT_URI=http://localhost:8008/api/auth/microsoft/callback
MS_TENANT_ID=common
```

## Complete .env File Example

Here's a complete example of what your `.env` file should look like:

```bash
# Application settings
DEBUG=true
ENVIRONMENT=development
API_PORT=8008
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8000", "http://localhost:8008"]

# Google Calendar OAuth
GOOGLE_CLIENT_ID=your_google_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8008/api/auth/google/callback

# Microsoft Graph OAuth
MS_CLIENT_ID=your_microsoft_client_id_here
MS_CLIENT_SECRET=your_microsoft_client_secret_here
MS_REDIRECT_URI=http://localhost:8008/api/auth/microsoft/callback
MS_TENANT_ID=common

# Redis settings
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Security
SECRET_KEY=your_super_secret_key_here_minimum_32_characters_abcdefghijklmnopqrstuvwxyz
```

## Testing OAuth Flows

Once you've set up the credentials, you can test the OAuth flows:

### Test Google Calendar OAuth

1. Start your application: `python -m src.main`
2. Visit: `http://localhost:8008/api/auth/google/authorize`
3. You should be redirected to Google's consent screen
4. After authorization, you should receive access tokens

### Test Microsoft Graph OAuth

1. Visit: `http://localhost:8008/api/auth/microsoft/authorize`
2. You should be redirected to Microsoft's consent screen
3. After authorization, you should receive access tokens

## Troubleshooting

### Common Issues

1. **"Redirect URI mismatch"**: Make sure the redirect URI in your app registration exactly matches what you're using in your code
2. **"Invalid client"**: Double-check your client ID and secret
3. **"Scope not authorized"**: Make sure you've added and granted the necessary permissions
4. **"SSL required"**: For production, you must use HTTPS redirect URIs

### Debug Mode

You can enable debug mode by setting `DEBUG=true` in your `.env` file. This will provide more detailed error messages.

## Production Deployment

When deploying to production:

1. Update redirect URIs to use your production domain
2. Use HTTPS for all redirect URIs
3. Store credentials securely (consider using AWS Secrets Manager, Azure Key Vault, etc.)
4. Set `ENVIRONMENT=production` in your production environment

## Next Steps

After setting up OAuth credentials:

1. Test the OAuth flows to ensure they work
2. Test calendar listing and event retrieval
3. Set up your frontend integration
4. Configure calendar synchronization