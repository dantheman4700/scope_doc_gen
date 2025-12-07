"""Google Drive service for fetching templates from a shared folder."""

import io
import logging
from pathlib import Path
from typing import List, Dict, Optional
import json

logger = logging.getLogger(__name__)

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaIoBaseDownload
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    logger.warning("Google Drive libraries not available")


class GoogleDriveTemplateService:
    """Service for fetching templates from Google Drive folder."""

    def __init__(self, service_account_file: Optional[str] = None, folder_id: Optional[str] = None):
        """
        Initialize the Google Drive template service.

        Args:
            service_account_file: Path to service account JSON key file
            folder_id: Google Drive folder ID containing templates
        """
        if not GOOGLE_DRIVE_AVAILABLE:
            raise RuntimeError("Google Drive libraries not available. Install google-api-python-client and google-auth.")

        self.service_account_file = service_account_file
        self.folder_id = folder_id
        self._drive_service = None

    def _get_drive_service(self):
        """Get or create a Drive API service instance."""
        if self._drive_service is not None:
            return self._drive_service

        if not self.service_account_file:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE must be set to access templates")

        service_account_path = Path(self.service_account_file)
        if not service_account_path.exists():
            raise FileNotFoundError(f"Service account file not found: {service_account_path}")

        try:
            credentials = service_account.Credentials.from_service_account_file(
                str(service_account_path),
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )
            self._drive_service = build('drive', 'v3', credentials=credentials)
            return self._drive_service
        except Exception as e:
            logger.exception("Failed to initialize Google Drive service")
            raise RuntimeError(f"Failed to initialize Google Drive service: {e}")

    def list_templates(self) -> List[Dict[str, str]]:
        """
        List all template files in the configured Google Drive folder.

        Returns:
            List of dicts with 'id', 'name', 'mimeType', and 'webViewLink' keys
        """
        if not self.folder_id:
            raise ValueError("GOOGLE_TEMPLATE_FOLDER_ID must be set")

        drive_service = self._get_drive_service()

        try:
            # Query for files in the folder
            # Support both Google Docs and DOCX files
            query = (
                f"'{self.folder_id}' in parents and "
                f"(mimeType='application/vnd.google-apps.document' or "
                f"mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document') and "
                f"trashed=false"
            )

            results = drive_service.files().list(
                q=query,
                fields="files(id, name, mimeType, webViewLink)",
                orderBy="name"
            ).execute()

            files = results.get('files', [])
            templates = []

            for file in files:
                templates.append({
                    'id': file['id'],
                    'name': file['name'],
                    'mimeType': file['mimeType'],
                    'webViewLink': file.get('webViewLink', ''),
                })

            logger.info(f"Found {len(templates)} templates in folder {self.folder_id}")
            return templates

        except HttpError as e:
            logger.exception(f"Failed to list templates from Google Drive: {e}")
            raise RuntimeError(f"Failed to list templates: {e}")

    def download_template(self, file_id: str) -> str:
        """
        Download a template file from Google Drive and return its content as text.

        For Google Docs, exports as plain text.
        For DOCX files, downloads the file and extracts text.

        Args:
            file_id: Google Drive file ID

        Returns:
            Template content as plain text
        """
        drive_service = self._get_drive_service()

        try:
            # Get file metadata to determine type
            file_metadata = drive_service.files().get(fileId=file_id).execute()
            mime_type = file_metadata.get('mimeType', '')

            if mime_type == 'application/vnd.google-apps.document':
                # Google Doc - export as plain text
                request = drive_service.files().export_media(
                    fileId=file_id,
                    mimeType='text/plain'
                )
                content = io.BytesIO()
                downloader = MediaIoBaseDownload(content, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                content_text = content.getvalue().decode('utf-8')
                return content_text

            elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                # DOCX file - download and extract text
                request = drive_service.files().get_media(fileId=file_id)
                content = io.BytesIO()
                downloader = MediaIoBaseDownload(content, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                
                # Extract text from DOCX
                from docx import Document
                docx_bytes = content.getvalue()
                doc = Document(io.BytesIO(docx_bytes))
                
                # Convert paragraphs to text
                text_parts = []
                for paragraph in doc.paragraphs:
                    text_parts.append(paragraph.text)
                
                return '\n'.join(text_parts)

            else:
                raise ValueError(f"Unsupported file type: {mime_type}")

        except HttpError as e:
            logger.exception(f"Failed to download template {file_id}: {e}")
            raise RuntimeError(f"Failed to download template: {e}")
        except Exception as e:
            logger.exception(f"Error processing template {file_id}: {e}")
            raise RuntimeError(f"Error processing template: {e}")

