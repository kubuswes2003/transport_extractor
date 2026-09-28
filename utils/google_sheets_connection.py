"""Quick connectivity check for the Google Sheets export.

Run it to verify that the service-account credentials work and that the
spreadsheet is reachable:

    GOOGLE_SHEET_ID=<id> python -m utils.google_sheets_connection
"""

import sys

import gspread
from google.oauth2.service_account import Credentials

import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]


def main() -> int:
    if not config.GOOGLE_SHEET_ID:
        print("GOOGLE_SHEET_ID is not set — export target unknown.", file=sys.stderr)
        return 1

    creds = Credentials.from_service_account_file(
        config.CREDENTIALS_FILE, scopes=SCOPES
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(config.GOOGLE_SHEET_ID)

    print("Connected. Header row:", sheet.sheet1.row_values(1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
