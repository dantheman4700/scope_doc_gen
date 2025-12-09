"""
Google OAuth flow for per-user Google account connections.

This allows users to connect their own Google accounts for exports,
rather than using the service account.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from server.core.config import (
    GOOGLE_OAUTH_CLIENT_ID,
    GOOGLE_OAUTH_CLIENT_SECRET,
    GOOGLE_OAUTH_REDIRECT_URI,
)

logger = logging.getLogger(__name__)

# OAuth scopes needed for Google Docs export
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
]


def get_oauth_flow(redirect_uri: Optional[str] = None) -> Flow:
    """
    Create a Google OAuth flow for user authentication.
    
    Args:
        redirect_uri: Optional custom redirect URI
        
    Returns:
        Google OAuth Flow instance
    """
    client_config = {
        "web": {
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri or GOOGLE_OAUTH_REDIRECT_URI],
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=GOOGLE_SCOPES,
        redirect_uri=redirect_uri or GOOGLE_OAUTH_REDIRECT_URI,
    )
    
    return flow


def get_authorization_url(state: Optional[str] = None) -> tuple[str, str]:
    """
    Get the Google OAuth authorization URL.
    
    Args:
        state: Optional state parameter for CSRF protection
        
    Returns:
        Tuple of (authorization_url, state)
    """
    flow = get_oauth_flow()
    
    authorization_url, state = flow.authorization_url(
        access_type="offline",  # Get refresh token
        include_granted_scopes="true",
        prompt="consent",  # Always show consent screen to get refresh token
        state=state,
    )
    
    return authorization_url, state


def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    """
    Exchange authorization code for tokens.
    
    Args:
        code: Authorization code from Google OAuth callback
        
    Returns:
        Dictionary with tokens and expiry info
    """
    import requests
    
    flow = get_oauth_flow()
    flow.fetch_token(code=code)
    
    credentials = flow.credentials
    
    # Try to get user email from Google userinfo API
    email = None
    try:
        userinfo_response = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {credentials.token}"}
        )
        if userinfo_response.ok:
            userinfo = userinfo_response.json()
            email = userinfo.get("email")
    except Exception as e:
        logger.warning(f"Failed to fetch user email: {e}")
    
    return {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes) if credentials.scopes else GOOGLE_SCOPES,
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        "email": email,
    }


def credentials_from_tokens(token_data: Dict[str, Any]) -> Optional[Credentials]:
    """
    Create Credentials object from stored token data.
    
    Args:
        token_data: Token data dictionary (from exchange_code_for_tokens)
        
    Returns:
        Credentials object or None if invalid
    """
    if not token_data:
        return None
        
    try:
        expiry = None
        if token_data.get("expiry"):
            expiry = datetime.fromisoformat(token_data["expiry"])
        
        credentials = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id", GOOGLE_OAUTH_CLIENT_ID),
            client_secret=token_data.get("client_secret", GOOGLE_OAUTH_CLIENT_SECRET),
            scopes=token_data.get("scopes", GOOGLE_SCOPES),
            expiry=expiry,
        )
        
        return credentials
        
    except Exception as e:
        logger.error(f"Failed to create credentials from tokens: {e}")
        return None


def get_user_drive_service(token_data: Dict[str, Any]):
    """
    Get a Drive service using user's OAuth credentials.
    
    Args:
        token_data: User's stored token data
        
    Returns:
        Google Drive service or None
    """
    credentials = credentials_from_tokens(token_data)
    if not credentials:
        return None
        
    try:
        return build("drive", "v3", credentials=credentials)
    except Exception as e:
        logger.error(f"Failed to build Drive service: {e}")
        return None


def get_user_docs_service(token_data: Dict[str, Any]):
    """
    Get a Docs service using user's OAuth credentials.
    
    Args:
        token_data: User's stored token data
        
    Returns:
        Google Docs service or None
    """
    credentials = credentials_from_tokens(token_data)
    if not credentials:
        return None
        
    try:
        return build("docs", "v1", credentials=credentials)
    except Exception as e:
        logger.error(f"Failed to build Docs service: {e}")
        return None


def is_token_valid(token_data: Dict[str, Any]) -> bool:
    """
    Check if the stored tokens are still valid (or can be refreshed).
    
    Args:
        token_data: User's stored token data
        
    Returns:
        True if tokens are valid or refreshable
    """
    if not token_data:
        return False
    
    # If we have a refresh token, we can always get new access tokens
    if token_data.get("refresh_token"):
        return True
    
    # Check if access token is expired
    expiry = token_data.get("expiry")
    if expiry:
        try:
            expiry_dt = datetime.fromisoformat(expiry)
            return datetime.utcnow() < expiry_dt
        except:
            pass
    
    return bool(token_data.get("access_token"))


def revoke_tokens(token_data: Dict[str, Any]) -> bool:
    """
    Revoke user's Google OAuth tokens.
    
    Args:
        token_data: User's stored token data
        
    Returns:
        True if revocation successful
    """
    import requests
    
    token = token_data.get("access_token") or token_data.get("refresh_token")
    if not token:
        return True  # Nothing to revoke
    
    try:
        response = requests.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to revoke tokens: {e}")
        return False

