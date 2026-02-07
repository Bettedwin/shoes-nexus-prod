import os

# Get the absolute path to database
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "shoes_nexus_db", "shoes_nexus.db")

# Verify database exists
if not os.path.exists(DB_PATH):
    raise FileNotFoundError(f"Database not found at: {DB_PATH}")

print(f"✅ Using database: {DB_PATH}")

# Business settings
BUSINESS_NAME = "Shoes Nexus Kenya"
BUSINESS_PHONE = "+254748921804"
BUSINESS_EMAIL = "info@shoesnexus.com"
WHATSAPP_NUMBER = "+254748921804"

# M-Pesa settings
MPESA_PAYBILL = "522533"
MPESA_ACCOUNT = "7776553"
ACCOUNT_NAME = "Shoes Nexus"

# Delivery zones
DELIVERY_ZONES = [
    {
        "name": "Nairobi CBD",
        "cost": 100,
        "days": "Same day"
    },
    {
        "name": "Nairobi and Environs (Our Riders)",
        "cost": 200,
        "days": "Same day"
    },
    {
        "name": "Nairobi and Environs (Bolt Rider)",
        "cost": 150-900,
        "days": "Same day"
    },
    {
        "name": "Countrywide (Matatu Saccos)",
        "cost": 150-350,
        "days": "1-3 days"
    }
]

# Image base URL (will be updated for production)
IMAGE_BASE_URL = "/images"
