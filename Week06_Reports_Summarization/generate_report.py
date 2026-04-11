import os
from google import genai

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path: str) -> None:
    """Basit .env yükleyici (GOOGLE_API_KEY=... satırları). Ortamda zaten varsa ezmez."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


_load_dotenv(os.path.join(_SCRIPT_DIR, ".env"))

# ── CONFIG ──────────────────────────────────────────────────────────────────
FIELD_NOTES_DIR = "field_notes"
DRAFT_OUTPUT    = "draft_report.txt"
# Önce ortam, sonra bu klasördeki .env — https://aistudio.google.com/apikey
API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
# 2.5-flash, 2.0-flash'tan farklı kota havuzunda. Hâlâ 429: GEMINI_MODEL = "gemini-2.5-flash-lite"
GEMINI_MODEL = "gemini-2.5-flash"

# Dosya hiyerarşisi
FIELD_NOTE_FILES = [
    "07_concrete_delivery_ticket.txt", "05_safety_log_entry.txt",
    "08_traffic_control_report.txt", "09_crane_operator_log.txt",
    "04_elif_project_engineer.txt", "01_superintendent_morning.txt",
    "03_mehmet_kaya_steel.txt", "02_hasan_beton_plus.txt",
    "06_photo_log.txt", "10_municipality_voicemail.txt", "11_night_watchman.txt"
]

def main():
    if not API_KEY:
        env_path = os.path.join(_SCRIPT_DIR, ".env")
        print(
            "HATA: API anahtarı yok.\n"
            f"• Bu klasörde .env oluşturun: {env_path}\n"
            "  Satır: GOOGLE_API_KEY=your-key-here\n"
            "• veya PowerShell: $env:GOOGLE_API_KEY=\"your-key-here\""
        )
        return

    client = genai.Client(api_key=API_KEY)
    
    print(f"Reading files from '{FIELD_NOTES_DIR}/'...")
    combined = []
    for filename in FIELD_NOTE_FILES:
        filepath = os.path.join(FIELD_NOTES_DIR, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                combined.append(f"=== SOURCE: {filename} ===\n{f.read()}\n")
    
    if not combined:
        print("HATA: Dosyalar bulunamadı!")
        return

    field_notes_text = "\n".join(combined)
    print(f"Loaded {len(combined)} files.")

    print(f"Sending to {GEMINI_MODEL}...")
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"Produce a professional Daily Construction Report for March 14, 2026. Use official data (File 07) for quantities. Field notes: {field_notes_text}"
        )
        
        with open(DRAFT_OUTPUT, "w", encoding="utf-8") as f:
            f.write(response.text)
        
        print(f"\n✓ SUCCESS! Report generated: {DRAFT_OUTPUT}")

    except Exception as e:
        err = str(e)
        print(f"\nAPI ERROR: {err}")
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            print(
                "\n--- Kotayı aştınız (429) ---\n"
                "• Birkaç saniye/dakika sonra tekrar deneyin.\n"
                "• Günlük ücretsiz kotayı doldurduysanız ertesi gün veya faturalı plan deneyin.\n"
                "• Limitler: https://ai.google.dev/gemini-api/docs/rate-limits\n"
                "• GEMINI_MODEL sabitini değiştirip deneyin (ör. gemini-2.5-flash-lite)."
            )

if __name__ == "__main__":
    main()