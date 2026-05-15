import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Usar credentials.json
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
gc = gspread.authorize(creds)

# Tu URL
spreadsheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/1KIiqr2jdtBaL8GdQZrK-_xjj2Hpu9riDweNcwQVIO5A/edit")

# Ver TODAS las pestañas que existen
print("Hojas en el Google Sheet:")
for sheet in spreadsheet.worksheets():
    print(f"  - {sheet.title}")

# Intentar abrir "Empleados"
try:
    worksheet = spreadsheet.worksheet("Empleados")
    data = worksheet.get_all_records()
    print(f"\n✅ Hoja 'Empleados' encontrada con {len(data)} registros")
    if data:
        print(f"Primeros 3 registros:")
        for i, row in enumerate(data[:3]):
            print(f"  {i+1}: {row}")
except Exception as e:
    print(f"❌ Error: {e}")