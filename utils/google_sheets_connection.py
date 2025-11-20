import gspread
from google.oauth2.service_account import Credentials

scopes = [ "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive" ]

creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)

client = gspread.authorize(creds)

sheet_id = "1Xx-LfKeg2tG1cwm5wdMHW7AQGID3a0-7zs4ufQ7iwKU"

sheet = client.open_by_key(sheet_id)


values_list = sheet.sheet1.row_values(1)
print(values_list)