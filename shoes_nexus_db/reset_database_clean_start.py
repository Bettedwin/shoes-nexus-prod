from db_config import DB_PATH
import sqlite3
import shutil
from datetime import datetime

print("=" * 60)
print("🗑️  SHOES NEXUS - DATABASE RESET TOOL")
print("=" * 60)
print()

# ============================================
# BACKUP FIRST (SAFETY)
# ============================================
print("📦 Step 1: Creating backup...")

backup_file = f"shoes_nexus_backup_before_reset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
shutil.copy2(DB_PATH, backup_file)

print(f"✅ Backup saved as: {backup_file}")
print()

# ============================================
# CONFIRM RESET
# ============================================
print("⚠️  WARNING: This will delete ALL of the following:")
print("   - Sales records")
print("   - Returns/exchanges")
print("   - Expenses")
print("   - Stock history")
print("   - Activity logs")
print("   - Payment records")
print()
print("✅ This will KEEP:")
print("   - Products catalog")
print("   - User accounts")
print("   - Product sizes configuration")
print()

confirm = input("Type 'RESET' to proceed (or anything else to cancel): ")

if confirm != "RESET":
    print()
    print("❌ Reset cancelled. Database unchanged.")
    exit()

print()
print("🔄 Proceeding with reset...")
print()

# ============================================
# CONNECT TO DATABASE
# ============================================
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# ============================================
# DELETE TRANSACTION DATA
# ============================================
tables_to_clear = [
    "sales",
    "returns_exchanges",
    "daily_expenses",
    "daily_payments",
    "activity_log"
]

for table in tables_to_clear:
    try:
        # Get count before deletion
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        
        # Delete all records
        cur.execute(f"DELETE FROM {table}")
        
        # Reset auto-increment counter
        cur.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
        
        print(f"✅ Cleared {table}: {count} records deleted")
    except Exception as e:
        print(f"⚠️  {table}: {e}")

# ============================================
# RESET STOCK QUANTITIES TO ZERO
# ============================================
print()
print("🔄 Resetting stock quantities to zero...")

try:
    cur.execute("UPDATE product_sizes SET quantity = 0")
    rows = cur.rowcount
    print(f"✅ Reset {rows} size entries to 0 quantity")
except Exception as e:
    print(f"⚠️  Error resetting sizes: {e}")

try:
    cur.execute("UPDATE products SET stock = 0")
    rows = cur.rowcount
    print(f"✅ Reset {rows} products to 0 stock")
except Exception as e:
    print(f"⚠️  Error resetting products: {e}")

# ============================================
# COMMIT CHANGES
# ============================================
conn.commit()

# ============================================
# VERIFY RESET
# ============================================
print()
print("=" * 60)
print("📊 VERIFICATION - Checking what remains:")
print("=" * 60)

# Check products
cur.execute("SELECT COUNT(*) FROM products")
products_count = cur.fetchone()[0]
print(f"✅ Products catalog: {products_count} products")

# Check users
cur.execute("SELECT COUNT(*) FROM staff")
users_count = cur.fetchone()[0]
print(f"✅ User accounts: {users_count} users")

# Check product sizes
cur.execute("SELECT COUNT(*) FROM product_sizes")
sizes_count = cur.fetchone()[0]
print(f"✅ Product sizes config: {sizes_count} size entries (all set to 0 quantity)")

# Check sales (should be 0)
cur.execute("SELECT COUNT(*) FROM sales")
sales_count = cur.fetchone()[0]
print(f"{'✅' if sales_count == 0 else '❌'} Sales records: {sales_count}")

# Check returns (should be 0)
cur.execute("SELECT COUNT(*) FROM returns_exchanges")
returns_count = cur.fetchone()[0]
print(f"{'✅' if returns_count == 0 else '❌'} Returns: {returns_count}")

# Check expenses (should be 0)
cur.execute("SELECT COUNT(*) FROM daily_expenses")
expenses_count = cur.fetchone()[0]
print(f"{'✅' if expenses_count == 0 else '❌'} Expenses: {expenses_count}")

# Check activity log (should be 0)
cur.execute("SELECT COUNT(*) FROM activity_log")
log_count = cur.fetchone()[0]
print(f"{'✅' if log_count == 0 else '❌'} Activity log: {log_count}")

conn.close()

# ============================================
# FINAL MESSAGE
# ============================================
print()
print("=" * 60)
print("✅ DATABASE RESET COMPLETE!")
print("=" * 60)
print()
print("📋 Next Steps:")
print("   1. Restart your Streamlit app")
print("   2. Login with your existing account")
print("   3. Use 'Initial Stock Setup' to add your real inventory")
print("   4. Start fresh with actual business operations")
print()
print(f"💾 Backup saved at: {backup_file}")
print("   (Keep this safe in case you need to restore)")
print()