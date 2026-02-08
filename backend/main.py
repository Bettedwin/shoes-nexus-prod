from fastapi import FastAPI, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
from datetime import datetime
import os
import base64
import urllib.parse
import hashlib
import hmac
import secrets
import time
import uuid
import smtplib
import re
from email.message import EmailMessage
from config import (
    DB_PATH,
    DELIVERY_ZONES,
    MPESA_PAYBILL,
    MPESA_ACCOUNT,
    BUSINESS_NAME,
    BUSINESS_EMAIL,
    WHATSAPP_NUMBER,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASS,
    SMTP_FROM,
    SMTP_TLS,
)

# ============================================
# DATABASE CONNECTION
# ============================================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================
# FASTAPI APP
# ============================================
app = FastAPI(
    title="Shoes Nexus API",
    description="E-commerce API for Shoes Nexus Kenya",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve images
images_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "images")
app.mount("/images", StaticFiles(directory=images_path), name="images")

# ============================================
# IMAGE UPLOAD (ADMIN)
# ============================================
@app.post("/api/admin/upload-image")
def admin_upload_image(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
        ext = ".jpg"

    upload_dir = os.path.join(images_path, "admin-uploads")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(upload_dir, filename)

    try:
        with open(save_path, "wb") as buffer:
            buffer.write(file.file.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    return {"image_url": f"/images/admin-uploads/{filename}"}

# ============================================
# MODELS
# ============================================
class CartItem(BaseModel):
    product_id: int
    size: str
    quantity: int

class OrderCreate(BaseModel):
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    delivery_address: str
    delivery_zone: str
    items: List[CartItem]
    customer_notes: Optional[str] = None
    source: Optional[str] = None

class RegisterRequest(BaseModel):
    name: str
    email: str
    phone: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class ForgotPasswordRequest(BaseModel):
    identifier: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class StaffLoginRequest(BaseModel):
    username: str
    password: str

class StaffCreateRequest(BaseModel):
    username: str
    password: str
    role: str

class ProductSizeInput(BaseModel):
    size: str
    stock: int

class ProductCreateRequest(BaseModel):
    category: str
    brand: str
    model: str
    color: str
    selling_price: int
    buying_price: Optional[int] = None
    image_url: Optional[str] = None
    public_brand: Optional[str] = None
    public_title: Optional[str] = None
    public_description: Optional[str] = None
    sizes: Optional[List[ProductSizeInput]] = None

class ProductUpdateRequest(BaseModel):
    category: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    color: Optional[str] = None
    selling_price: Optional[int] = None
    buying_price: Optional[int] = None
    image_url: Optional[str] = None
    public_brand: Optional[str] = None
    public_title: Optional[str] = None
    public_description: Optional[str] = None
    sizes: Optional[List[ProductSizeInput]] = None

class BlogPostCreateRequest(BaseModel):
    title: str
    category: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None
    is_published: Optional[int] = 1

class BlogPostUpdateRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None
    is_published: Optional[int] = None

class HomeSectionCreateRequest(BaseModel):
    title: str
    category_label: Optional[str] = None
    category_match: Optional[str] = None
    model_keywords: Optional[str] = None
    filter_category: Optional[str] = None
    filter_type: Optional[str] = None
    limit_count: Optional[int] = None
    alternate_brands: Optional[int] = 0
    allow_out_of_stock: Optional[int] = 0
    sort_order: Optional[int] = 0
    is_active: Optional[int] = 1

class HomeSectionUpdateRequest(BaseModel):
    title: Optional[str] = None
    category_label: Optional[str] = None
    category_match: Optional[str] = None
    model_keywords: Optional[str] = None
    filter_category: Optional[str] = None
    filter_type: Optional[str] = None
    limit_count: Optional[int] = None
    alternate_brands: Optional[int] = None
    allow_out_of_stock: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[int] = None

class AdminResetUserPasswordRequest(BaseModel):
    identifier: str
    new_password: str

class AdminResetStaffPasswordRequest(BaseModel):
    username: str
    new_password: str

# ============================================
# HELPER FUNCTIONS
# ============================================
def get_product_image_url(product_id: int, brand: str, model: str, color: str):
    """Generate SEO-friendly image URL"""
    # Try to find image in images folder
    base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "images")
    
    # Create SEO-friendly filename pattern
    filename_base = f"{brand}-{color}-{model}".lower().replace(" ", "-")
    
    # Search in all subdirectories
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if filename_base in file.lower() and file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                # Return relative URL
                rel_path = os.path.relpath(os.path.join(root, file), base_path)
                return f"/images/{rel_path.replace(os.sep, '/')}"
    
    # Return placeholder if no image found
    return "/images/placeholder.jpg"

def slugify(value: str) -> str:
    base = "".join(ch.lower() if ch.isalnum() else "-" for ch in (value or "").strip())
    while "--" in base:
        base = base.replace("--", "-")
    return base.strip("-") or "post"

def title_case(value: str) -> str:
    words = [w for w in (value or "").replace("-", " ").split() if w]
    return " ".join(w.capitalize() for w in words)

def detect_style(model: str, image_url: str) -> str:
    text = f"{model or ''} {image_url or ''}".lower()
    checks = [
        (r"multi-strap|multistrap", "Multi-Strap Sandals"),
        (r"3-strap|3 strap", "3-Strap Sandals"),
        (r"diamond strap", "Diamond Strap Sandals"),
        (r"metal strap", "Metal Strap Sandals"),
        (r"platform slides|platform slide", "Platform Slides"),
        (r"doll shoes|doll shoe", "Doll Shoes Flats"),
        (r"rhinestone", "Rhinestone Stiletto Heels"),
        (r"stiletto|stilletto|stilleto", "Stiletto High Heels"),
        (r"butterfly", "Butterfly Detail Heels"),
        (r"heel|heels", "Heels"),
        (r"sneaker|sneakers|trainer", "Sneakers"),
        (r"slide|slides", "Slides"),
        (r"sandals|sandal", "Sandals"),
        (r"boots|boot", "Boots"),
        (r"shoes|shoe", "Shoes"),
    ]
    for pattern, label in checks:
        if re.search(pattern, text):
            return label
    return "Sandals"

def build_public_description(title: str, model: str, color: str, image_url: str) -> str:
    text = f"{model or ''} {color or ''} {image_url or ''}".lower()
    details = []
    if "suede" in text:
        details.append("Soft suede finish for a premium feel")
    if "leather" in text:
        details.append("Smooth leather feel with durable build")
    if "rhinestone" in text or "glitter" in text:
        details.append("Sparkle accents for a dressy look")
    if "butterfly" in text:
        details.append("Statement butterfly detail")
    if "platform" in text:
        details.append("Cushioned platform for extra height")
    if "criss" in text:
        details.append("Criss-cross straps for secure fit")
    if "fluffy" in text:
        details.append("Soft plush comfort for all-day wear")
    if "slide" in text:
        details.append("Easy slip-on design")
    if "doll" in text:
        details.append("Flat profile for everyday comfort")
    desc = [f"{title} designed for comfort, fit, and daily wear."]
    if details:
        desc.append(". ".join(details) + ".")
    desc.append("Affordable quality from Shoes Nexus Kenya with multiple sizes available.")
    desc.append("Fast Nairobi delivery and reliable nationwide shipping.")
    return " ".join(desc)

def generate_public_fields(category: str, model: str, color: str, image_url: str):
    cat = (category or "").lower()
    gender = "Women's" if "women" in cat else "Men's" if "men" in cat else ""
    color_txt = title_case(color or "")
    style = detect_style(model or "", image_url or "")
    parts = [p for p in [gender, color_txt, style] if p]
    title = " ".join(parts).strip() or "Comfort Sandals"
    description = build_public_description(title, model or "", color or "", image_url or "")
    return "Shoes Nexus", title, description

def ensure_audit_log():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            actor TEXT,
            details TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def ensure_product_public_fields():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(products)")
    columns = [row[1] for row in cur.fetchall()]
    if "image_url" not in columns:
        cur.execute("ALTER TABLE products ADD COLUMN image_url TEXT")
    if "public_brand" not in columns:
        cur.execute("ALTER TABLE products ADD COLUMN public_brand TEXT")
    if "public_title" not in columns:
        cur.execute("ALTER TABLE products ADD COLUMN public_title TEXT")
    if "public_description" not in columns:
        cur.execute("ALTER TABLE products ADD COLUMN public_description TEXT")
    conn.commit()
    conn.close()

def log_audit_event(event_type: str, actor: Optional[str], details: str):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO admin_audit_log (event_type, actor, details)
            VALUES (?, ?, ?)
        """, (event_type, actor, details))
        conn.commit()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

def send_reset_email(to_email: str, reset_token: str, expires_at: int):
    if not SMTP_HOST or not SMTP_FROM:
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = f"{BUSINESS_NAME} Password Reset"
        msg["From"] = SMTP_FROM
        msg["To"] = to_email
        expiry = datetime.fromtimestamp(expires_at).strftime("%Y-%m-%d %H:%M")
        msg.set_content(
            f"Your password reset token is:\n\n{reset_token}\n\n"
            f"This token expires at {expiry}.\n\n"
            "If you did not request this, you can ignore this email."
        )
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            if SMTP_TLS:
                server.starttls()
            if SMTP_USER and SMTP_PASS:
                server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception:
        return False

def init_auth_tables():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    # Ensure staff table has is_active column
    cur.execute("PRAGMA table_info(staff)")
    columns = [row[1] for row in cur.fetchall()]
    if "is_active" not in columns:
        cur.execute("ALTER TABLE staff ADD COLUMN is_active INTEGER DEFAULT 1")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS staff_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

def init_order_tables():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            email TEXT,
            delivery_address TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS online_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT,
            customer_id INTEGER,
            subtotal INTEGER,
            delivery_cost INTEGER,
            total_amount INTEGER,
            delivery_address TEXT,
            delivery_method TEXT,
            customer_notes TEXT,
            source TEXT,
            status TEXT DEFAULT 'PENDING',
            payment_status TEXT DEFAULT 'UNPAID',
            payment_method TEXT,
            paid_at TEXT,
            updated_at TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            product_id INTEGER,
            size TEXT,
            quantity INTEGER,
            unit_price INTEGER,
            total_price INTEGER,
            FOREIGN KEY (order_id) REFERENCES online_orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    cur.execute("PRAGMA table_info(online_orders)")
    columns = [row[1] for row in cur.fetchall()]
    if "status" not in columns:
        cur.execute("ALTER TABLE online_orders ADD COLUMN status TEXT DEFAULT 'PENDING'")
    if "payment_status" not in columns:
        cur.execute("ALTER TABLE online_orders ADD COLUMN payment_status TEXT DEFAULT 'UNPAID'")
    if "payment_method" not in columns:
        cur.execute("ALTER TABLE online_orders ADD COLUMN payment_method TEXT")
    if "paid_at" not in columns:
        cur.execute("ALTER TABLE online_orders ADD COLUMN paid_at TEXT")
    if "updated_at" not in columns:
        cur.execute("ALTER TABLE online_orders ADD COLUMN updated_at TEXT")
    if "source" not in columns:
        cur.execute("ALTER TABLE online_orders ADD COLUMN source TEXT")
    conn.commit()
    conn.close()

def hash_password(password: str, salt: Optional[bytes] = None):
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return base64.b64encode(dk).decode("utf-8"), base64.b64encode(salt).decode("utf-8")

def verify_password(password: str, password_hash: str, password_salt: str):
    salt = base64.b64decode(password_salt.encode("utf-8"))
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return hmac.compare_digest(base64.b64encode(dk).decode("utf-8"), password_hash)

def verify_staff_password(password: str, password_hash: str):
    return hashlib.sha256(password.encode("utf-8")).hexdigest() == password_hash

def hash_staff_password(password: str):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def create_session(conn, user_id: int):
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    expires_at = now + (60 * 60 * 24 * 7)  # 7 days
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO user_sessions (user_id, token, created_at, expires_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, token, now, expires_at))
    return token, expires_at

def create_staff_session(conn, staff_id: int):
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    expires_at = now + (60 * 60 * 24 * 7)  # 7 days
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO staff_sessions (staff_id, token, created_at, expires_at)
        VALUES (?, ?, ?, ?)
    """, (staff_id, token, now, expires_at))
    return token, expires_at

def get_user_from_token(token: str):
    conn = get_db()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute("""
        SELECT u.id, u.name, u.email, u.phone
        FROM users u
        JOIN user_sessions s ON s.user_id = u.id
        WHERE s.token = ? AND s.expires_at > ?
    """, (token, now))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_staff_from_token(token: str):
    conn = get_db()
    cur = conn.cursor()
    now = int(time.time())
    cur.execute("""
        SELECT s.id, s.username, s.role
        FROM staff s
        JOIN staff_sessions ss ON ss.staff_id = s.id
        WHERE ss.token = ? AND ss.expires_at > ?
    """, (token, now))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def require_admin(authorization: Optional[str]):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.split(" ", 1)[1].strip()
    staff = get_staff_from_token(token)
    if not staff or staff.get("role", "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return staff

def create_password_reset(conn, user_id: int):
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    expires_at = now + (60 * 60)  # 1 hour
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO password_resets (user_id, token, created_at, expires_at, used)
        VALUES (?, ?, ?, ?, 0)
    """, (user_id, token, now, expires_at))
    return token, expires_at

init_auth_tables()
init_order_tables()

def init_blog_tables():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS blog_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT,
            category TEXT,
            excerpt TEXT,
            content TEXT,
            image_url TEXT,
            is_published INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT
        )
    """)
    # lightweight migration: add category column if missing
    cur.execute("PRAGMA table_info(blog_posts)")
    columns = [row[1] for row in cur.fetchall()]
    if "category" not in columns:
        cur.execute("ALTER TABLE blog_posts ADD COLUMN category TEXT")
    if "slug" not in columns:
        cur.execute("ALTER TABLE blog_posts ADD COLUMN slug TEXT")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_blog_posts_slug ON blog_posts(slug)")
    conn.commit()
    conn.close()

init_blog_tables()
ensure_audit_log()
ensure_product_public_fields()

def init_home_sections():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS home_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category_label TEXT,
            category_match TEXT,
            model_keywords TEXT,
            filter_category TEXT,
            filter_type TEXT,
            limit_count INTEGER,
            alternate_brands INTEGER DEFAULT 0,
            allow_out_of_stock INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_home_sections()

def build_whatsapp_link(phone: str, message: str) -> str:
    digits = ''.join(ch for ch in (phone or '') if ch.isdigit())
    encoded = urllib.parse.quote(message)
    return f"https://wa.me/{digits}?text={encoded}" if digits else ""

# ============================================
# ROUTES
# ============================================

@app.get("/")
def root():
    return {
        "message": "Shoes Nexus Kenya API",
        "status": "active",
        "version": "1.0.0"
    }

@app.get("/api/products")
def get_products(
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100
):
    """Get all active products with sizes and images"""
    conn = get_db()
    cur = conn.cursor()
    
    query = """
        SELECT 
            id, brand, model, color, category, selling_price, public_brand, public_title, public_description
        FROM products
        WHERE is_active = 1
    """
    
    params = []
    
    if category:
        query += " AND LOWER(category) = LOWER(?)"
        params.append(category)
    
    if search:
        query += " AND (LOWER(brand) LIKE ? OR LOWER(model) LIKE ? OR LOWER(color) LIKE ?)"
        search_term = f"%{search.lower()}%"
        params.extend([search_term, search_term, search_term])
    
    query += " ORDER BY brand, model LIMIT ?"
    params.append(limit)
    
    cur.execute(query, params)
    products = []
    
    for row in cur.fetchall():
        product = dict(row)
        
        # Get image URL (SEO-friendly)
        product['image_url'] = get_product_image_url(
            product['id'],
            product['brand'],
            product['model'],
            product['color']
        )
        
        # Get available sizes
        cur.execute("""
            SELECT size, quantity
            FROM product_sizes
            WHERE product_id = ? AND quantity > 0
            ORDER BY CAST(size AS INTEGER)
        """, (product['id'],))
        
        product['sizes'] = [
            {"size": r['size'], "stock": r['quantity']}
            for r in cur.fetchall()
        ]
        
        products.append(product)
    
    conn.close()
    return products

@app.get("/api/products/{product_id}")
def get_product(product_id: int):
    """Get single product details"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, brand, model, color, category, selling_price, public_brand, public_title, public_description
        FROM products
        WHERE id = ? AND is_active = 1
    """, (product_id,))
    
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product = dict(row)
    
    # Get image
    product['image_url'] = get_product_image_url(
        product['id'],
        product['brand'],
        product['model'],
        product['color']
    )
    
    # Get sizes
    cur.execute("""
        SELECT size, quantity
        FROM product_sizes
        WHERE product_id = ?
        ORDER BY CAST(size AS INTEGER)
    """, (product_id,))
    
    product['sizes'] = [dict(r) for r in cur.fetchall()]
    
    conn.close()
    return product

@app.get("/api/categories")
def get_categories():
    """Get product categories"""
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT DISTINCT category, COUNT(*) as count
        FROM products
        WHERE is_active = 1
        GROUP BY category
        ORDER BY category
    """)
    
    categories = [dict(row) for row in cur.fetchall()]
    conn.close()
    return categories

@app.get("/api/delivery-zones")
def get_delivery_zones():
    """Get delivery options"""
    return DELIVERY_ZONES

@app.get("/api/settings")
def get_settings():
    """Get website settings"""
    from config import BUSINESS_NAME, BUSINESS_PHONE, BUSINESS_EMAIL, WHATSAPP_NUMBER
    
    return {
        "business_name": BUSINESS_NAME,
        "phone": BUSINESS_PHONE,
        "email": BUSINESS_EMAIL,
        "whatsapp": WHATSAPP_NUMBER,
        "mpesa_paybill": MPESA_PAYBILL,
        "mpesa_account": MPESA_ACCOUNT
    }

@app.post("/api/auth/register")
def register_user(payload: RegisterRequest):
    conn = get_db()
    cur = conn.cursor()
    try:
        if not payload.phone or not payload.phone.strip():
            raise HTTPException(status_code=400, detail="Phone number is required")
        cur.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (payload.email,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")

        password_hash, password_salt = hash_password(payload.password)
        now = int(time.time())
        cur.execute("""
            INSERT INTO users (name, email, phone, password_hash, password_salt, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (payload.name, payload.email, payload.phone, password_hash, password_salt, now))
        user_id = cur.lastrowid

        token, expires_at = create_session(conn, user_id)
        conn.commit()

        return {
            "token": token,
            "expires_at": expires_at,
            "user": {
                "id": user_id,
                "name": payload.name,
                "email": payload.email,
                "phone": payload.phone
            }
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/auth/login")
def login_user(payload: LoginRequest):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, name, email, phone, password_hash, password_salt
            FROM users
            WHERE LOWER(email) = LOWER(?)
        """, (payload.email,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not verify_password(payload.password, row["password_hash"], row["password_salt"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        token, expires_at = create_session(conn, row["id"])
        conn.commit()

        return {
            "token": token,
            "expires_at": expires_at,
            "user": {
                "id": row["id"],
                "name": row["name"],
                "email": row["email"],
                "phone": row["phone"]
            }
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/auth/me")
def get_me(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.split(" ", 1)[1].strip()
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return {"user": user}

@app.post("/api/auth/staff/login")
def staff_login(payload: StaffLoginRequest):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, username, role, password_hash, is_active
            FROM staff
            WHERE LOWER(username) = LOWER(?)
        """, (payload.username,))
        row = cur.fetchone()
        if not row or row["is_active"] == 0 or not verify_staff_password(payload.password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        token, expires_at = create_staff_session(conn, row["id"])
        conn.commit()

        return {
            "token": token,
            "expires_at": expires_at,
            "staff": {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"]
            }
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/auth/staff/me")
def get_staff_me(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.split(" ", 1)[1].strip()
    staff = get_staff_from_token(token)
    if not staff:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return {"staff": staff}

# ============================================
# ADMIN ROUTES (STAFF ADMIN ONLY)
# ============================================

@app.get("/api/admin/products")
def admin_list_products(authorization: Optional[str] = Header(None), limit: int = 200):
    require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, category, brand, model, color, buying_price, selling_price, public_brand, public_title, public_description, is_active
        FROM products
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    products = []
    rows = cur.fetchall()
    for row in rows:
        product = dict(row)
        cur.execute("""
            SELECT size, quantity
            FROM product_sizes
            WHERE product_id = ?
            ORDER BY CAST(size AS INTEGER)
        """, (product["id"],))
        product["sizes"] = [{"size": r["size"], "stock": r["quantity"]} for r in cur.fetchall()]
        products.append(product)
    conn.close()
    return products

@app.get("/api/admin/low-stock")
def admin_low_stock(authorization: Optional[str] = Header(None), threshold: int = 3):
    require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.brand, p.model, p.color, p.category,
               COALESCE(SUM(ps.quantity), 0) as total_stock
        FROM products p
        LEFT JOIN product_sizes ps ON ps.product_id = p.id
        WHERE p.is_active = 1
        GROUP BY p.id
        HAVING total_stock <= ?
        ORDER BY total_stock ASC, p.brand, p.model
    """, (threshold,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

@app.post("/api/admin/products")
def admin_create_product(payload: ProductCreateRequest, authorization: Optional[str] = Header(None)):
    staff = require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        if payload.buying_price is None:
            raise HTTPException(status_code=400, detail="Buying price is required")
        cur.execute("""
            INSERT INTO products (
                category, brand, model, color, buying_price, selling_price, image_url,
                public_brand, public_title, public_description, stock, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            payload.category,
            payload.brand,
            payload.model,
            payload.color,
            payload.buying_price,
            payload.selling_price,
            payload.image_url,
            payload.public_brand,
            payload.public_title,
            payload.public_description,
            0
        ))
        product_id = cur.lastrowid
        if payload.sizes:
            for size in payload.sizes:
                cur.execute("""
                    INSERT OR REPLACE INTO product_sizes (product_id, size, quantity)
                    VALUES (?, ?, ?)
                """, (product_id, size.size, size.stock))
        conn.commit()
        log_audit_event("product_create", staff.get("username"), f"Created product {product_id}")
        return {"success": True, "id": product_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.put("/api/admin/products/{product_id}")
def admin_update_product(product_id: int, payload: ProductUpdateRequest, authorization: Optional[str] = Header(None)):
    staff = require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        fields = []
        params = []
        for field_name in [
            "category", "brand", "model", "color",
            "buying_price", "selling_price", "image_url",
            "public_brand", "public_title", "public_description"
        ]:
            value = getattr(payload, field_name)
            if value is not None:
                fields.append(f"{field_name} = ?")
                params.append(value)
        if fields:
            params.append(product_id)
            cur.execute(f"UPDATE products SET {', '.join(fields)} WHERE id = ?", params)

        if payload.sizes is not None:
            cur.execute("DELETE FROM product_sizes WHERE product_id = ?", (product_id,))
            for size in payload.sizes:
                cur.execute("""
                    INSERT OR REPLACE INTO product_sizes (product_id, size, quantity)
                    VALUES (?, ?, ?)
                """, (product_id, size.size, size.stock))

        conn.commit()
        log_audit_event("product_update", staff.get("username"), f"Updated product {product_id}")
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/admin/products/regenerate-public")
def admin_regenerate_public_fields(authorization: Optional[str] = Header(None), overwrite: bool = False):
    staff = require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, category, model, color, image_url, public_title
            FROM products
            WHERE is_active = 1
        """)
        rows = cur.fetchall()
        updated = 0
        for row in rows:
            if not overwrite and row["public_title"]:
                continue
            public_brand, public_title, public_description = generate_public_fields(
                row["category"],
                row["model"],
                row["color"],
                row["image_url"]
            )
            cur.execute(
                """
                UPDATE products
                SET public_brand = ?, public_title = ?, public_description = ?
                WHERE id = ?
                """,
                (public_brand, public_title, public_description, row["id"])
            )
            updated += 1
        conn.commit()
        log_audit_event("product_regenerate_public", staff.get("username"), f"Regenerated {updated} products")
        return {"success": True, "updated": updated}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
@app.post("/api/admin/products/{product_id}/deactivate")
def admin_deactivate_product(product_id: int, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE products SET is_active = 0 WHERE id = ?", (product_id,))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/admin/products/{product_id}/activate")
def admin_activate_product(product_id: int, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE products SET is_active = 1 WHERE id = ?", (product_id,))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/admin/staff")
def admin_list_staff(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, role, is_active FROM staff ORDER BY id DESC")
    staff = [dict(row) for row in cur.fetchall()]
    conn.close()
    return staff

@app.post("/api/admin/staff")
def admin_create_staff(payload: StaffCreateRequest, authorization: Optional[str] = Header(None)):
    staff = require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM staff WHERE LOWER(username) = LOWER(?)", (payload.username,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")
        password_hash = hash_staff_password(payload.password)
        cur.execute("""
            INSERT INTO staff (username, password_hash, role, is_active)
            VALUES (?, ?, ?, 1)
        """, (payload.username, password_hash, payload.role))
        conn.commit()
        log_audit_event("staff_create", staff.get("username"), f"Created staff {payload.username}")
        return {"success": True}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.put("/api/admin/staff/{staff_id}")
def admin_update_staff(staff_id: int, payload: StaffCreateRequest, authorization: Optional[str] = Header(None)):
    staff = require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        password_hash = hash_staff_password(payload.password)
        cur.execute("""
            UPDATE staff
            SET username = ?, password_hash = ?, role = ?
            WHERE id = ?
        """, (payload.username, password_hash, payload.role, staff_id))
        conn.commit()
        log_audit_event("staff_update", staff.get("username"), f"Updated staff {staff_id}")
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/admin/staff/{staff_id}/deactivate")
def admin_deactivate_staff(staff_id: int, authorization: Optional[str] = Header(None)):
    staff = require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE staff SET is_active = 0 WHERE id = ?", (staff_id,))
        conn.commit()
        log_audit_event("staff_deactivate", staff.get("username"), f"Deactivated staff {staff_id}")
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/admin/staff/{staff_id}/activate")
def admin_activate_staff(staff_id: int, authorization: Optional[str] = Header(None)):
    staff = require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE staff SET is_active = 1 WHERE id = ?", (staff_id,))
        conn.commit()
        log_audit_event("staff_activate", staff.get("username"), f"Activated staff {staff_id}")
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/admin/users/reset-password")
def admin_reset_user_password(payload: AdminResetUserPasswordRequest, authorization: Optional[str] = Header(None)):
    staff = require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        identifier = payload.identifier.strip()
        cur.execute(
            "SELECT id FROM users WHERE LOWER(email) = LOWER(?) OR phone = ?",
            (identifier.lower(), identifier)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        password_hash, password_salt = hash_password(payload.new_password)
        cur.execute(
            "UPDATE users SET password_hash = ?, password_salt = ? WHERE id = ?",
            (password_hash, password_salt, row["id"])
        )
        conn.commit()
        log_audit_event("user_reset_password", staff.get("username"), f"Reset password for user {row['id']}")
        return {"success": True}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/admin/users")
def admin_list_users(authorization: Optional[str] = Header(None), search: Optional[str] = None, limit: int = 200):
    require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        query = "SELECT id, name, email, phone, created_at FROM users"
        params = []
        if search:
            query += " WHERE LOWER(name) LIKE ? OR LOWER(email) LIKE ? OR phone LIKE ?"
            term = f"%{search.lower()}%"
            params.extend([term, term, f"%{search}%"])
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cur.execute(query, params)
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

@app.post("/api/admin/staff/reset-password")
def admin_reset_staff_password(payload: AdminResetStaffPasswordRequest, authorization: Optional[str] = Header(None)):
    staff = require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id FROM staff WHERE LOWER(username) = LOWER(?)",
            (payload.username.strip(),)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Staff user not found")
        password_hash = hash_staff_password(payload.new_password)
        cur.execute(
            "UPDATE staff SET password_hash = ? WHERE id = ?",
            (password_hash, row["id"])
        )
        conn.commit()
        log_audit_event("staff_reset_password", staff.get("username"), f"Reset staff password {row['id']}")
        return {"success": True}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/admin/sales")
def admin_list_sales(authorization: Optional[str] = Header(None), limit: int = 200):
    require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.id, s.product_id, s.quantity, s.revenue, s.cost, s.sale_date, s.payment_method, s.size, s.notes,
               p.brand, p.model, p.color, p.category
        FROM sales s
        LEFT JOIN products p ON p.id = s.product_id
        ORDER BY s.id DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows

@app.get("/api/admin/orders")
def admin_list_orders(authorization: Optional[str] = Header(None), limit: int = 200):
    require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT o.id, o.order_number, o.total_amount, o.delivery_method, o.created_at,
                   o.status, o.payment_status, o.payment_method, o.updated_at, o.source,
                   c.name as customer_name, c.phone as customer_phone
            FROM online_orders o
            LEFT JOIN customers c ON c.id = o.customer_id
            ORDER BY o.id DESC
            LIMIT ?
        """, (limit,))
        orders = [dict(row) for row in cur.fetchall()]
        for order in orders:
            cur.execute("""
                SELECT oi.quantity, oi.unit_price, oi.total_price, p.brand, p.model, p.color
                FROM order_items oi
                LEFT JOIN products p ON p.id = oi.product_id
                WHERE oi.order_id = ?
            """, (order["id"],))
            order["items"] = [dict(r) for r in cur.fetchall()]
        return orders
    finally:
        conn.close()

@app.get("/api/admin/audit-log")
def admin_audit_log(authorization: Optional[str] = Header(None), limit: int = 200):
    require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, event_type, actor, details, created_at
        FROM admin_audit_log
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

class OrderStatusUpdateRequest(BaseModel):
    status: str
    payment_status: Optional[str] = None
    payment_method: Optional[str] = None
    paid_at: Optional[str] = None

@app.put("/api/admin/orders/{order_id}/status")
def admin_update_order_status(order_id: int, payload: OrderStatusUpdateRequest, authorization: Optional[str] = Header(None)):
    staff = require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        fields = ["status = ?", "updated_at = datetime('now')"]
        params = [payload.status]
        if payload.payment_status is not None:
            fields.append("payment_status = ?")
            params.append(payload.payment_status)
        if payload.payment_method is not None:
            fields.append("payment_method = ?")
            params.append(payload.payment_method)
        if payload.paid_at is not None:
            fields.append("paid_at = ?")
            params.append(payload.paid_at)
        params.append(order_id)
        cur.execute(f"UPDATE online_orders SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
        log_audit_event("order_status_update", staff.get("username"), f"Order {order_id} -> {payload.status}")
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/orders/me")
def get_my_orders(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.split(" ", 1)[1].strip()
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    conn = get_db()
    cur = conn.cursor()
    try:
        email = (user.get("email") or "").lower()
        phone = user.get("phone") or ""
        cur.execute("""
            SELECT o.id, o.order_number, o.total_amount, o.delivery_method, o.created_at,
                   o.status, o.payment_status, o.payment_method, o.updated_at, o.source,
                   c.name as customer_name, c.phone as customer_phone, c.email as customer_email
            FROM online_orders o
            LEFT JOIN customers c ON c.id = o.customer_id
            WHERE (LOWER(c.email) = ? AND c.email != '')
               OR (c.phone = ? AND c.phone != '')
            ORDER BY o.id DESC
        """, (email, phone))
        orders = [dict(r) for r in cur.fetchall()]
        for order in orders:
            cur.execute("""
                SELECT oi.quantity, oi.unit_price, oi.total_price, p.brand, p.model, p.color, oi.size
                FROM order_items oi
                LEFT JOIN products p ON p.id = oi.product_id
                WHERE oi.order_id = ?
            """, (order["id"],))
            order["items"] = [dict(r) for r in cur.fetchall()]
        return orders
    finally:
        conn.close()

@app.get("/api/blog")
def list_blog_posts(limit: int = 6, offset: int = 0, category: Optional[str] = None):
    conn = get_db()
    cur = conn.cursor()
    if category:
        cur.execute("""
            SELECT id, title, slug, category, excerpt, content, image_url, created_at
            FROM blog_posts
            WHERE is_published = 1 AND category = ?
            ORDER BY datetime(created_at) DESC
            LIMIT ? OFFSET ?
        """, (category, limit, offset))
    else:
        cur.execute("""
            SELECT id, title, slug, category, excerpt, content, image_url, created_at
            FROM blog_posts
            WHERE is_published = 1
            ORDER BY datetime(created_at) DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/api/blog/{slug}")
def get_blog_post(slug: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, slug, category, excerpt, content, image_url, created_at
        FROM blog_posts
        WHERE is_published = 1 AND slug = ?
    """, (slug,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Post not found")
    return dict(row)

@app.get("/api/blog/categories")
def list_blog_categories():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT category
        FROM blog_posts
        WHERE is_published = 1 AND category IS NOT NULL AND category != ''
        ORDER BY category
    """)
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]

@app.get("/api/admin/blog")
def admin_list_blog_posts(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, slug, category, excerpt, content, image_url, is_published, created_at, updated_at
        FROM blog_posts
        ORDER BY datetime(created_at) DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/admin/blog")
def admin_create_blog_post(payload: BlogPostCreateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        slug = slugify(payload.title)
        cur.execute("SELECT id FROM blog_posts WHERE slug = ?", (slug,))
        if cur.fetchone():
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"
        cur.execute("""
            INSERT INTO blog_posts (title, slug, category, excerpt, content, image_url, is_published, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            payload.title,
            slug,
            payload.category,
            payload.excerpt,
            payload.content,
            payload.image_url,
            1 if payload.is_published is None else int(payload.is_published)
        ))
        conn.commit()
        log_audit_event("blog_create", "admin", f"Created blog post {payload.title} ({slug})")
        return {"success": True, "id": cur.lastrowid}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.put("/api/admin/blog/{post_id}")
def admin_update_blog_post(post_id: int, payload: BlogPostUpdateRequest, authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        fields = []
        params = []
        for field_name in ["title", "category", "excerpt", "content", "image_url", "is_published"]:
            value = getattr(payload, field_name)
            if value is not None:
                fields.append(f"{field_name} = ?")
                params.append(value)
        if payload.title:
            slug = slugify(payload.title)
            cur.execute("SELECT id FROM blog_posts WHERE slug = ? AND id != ?", (slug, post_id))
            if cur.fetchone():
                slug = f"{slug}-{uuid.uuid4().hex[:6]}"
            fields.append("slug = ?")
            params.append(slug)
        if fields:
            fields.append("updated_at = datetime('now')")
            params.append(post_id)
            cur.execute(f"UPDATE blog_posts SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
        log_audit_event("blog_update", "admin", f"Updated blog post {post_id}")
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/admin/blog/{post_id}/toggle")
def admin_toggle_blog_post(post_id: int, authorization: Optional[str] = Header(None)):
    staff = require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE blog_posts SET is_published = 1 - is_published, updated_at = datetime('now') WHERE id = ?", (post_id,))
        conn.commit()
        log_audit_event("blog_toggle", staff.get("username"), f"Toggled blog post {post_id}")
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/sections")
def list_home_sections():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, category_label, category_match, model_keywords, filter_category, filter_type,
               limit_count, alternate_brands, allow_out_of_stock, sort_order
        FROM home_sections
        WHERE is_active = 1
        ORDER BY sort_order ASC, id ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/api/admin/sections")
def admin_list_sections(authorization: Optional[str] = Header(None)):
    require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, category_label, category_match, model_keywords, filter_category, filter_type,
               limit_count, alternate_brands, allow_out_of_stock, sort_order, is_active, created_at, updated_at
        FROM home_sections
        ORDER BY sort_order ASC, id ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/api/admin/sections")
def admin_create_section(payload: HomeSectionCreateRequest, authorization: Optional[str] = Header(None)):
    staff = require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO home_sections
            (title, category_label, category_match, model_keywords, filter_category, filter_type, limit_count,
             alternate_brands, allow_out_of_stock, sort_order, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            payload.title,
            payload.category_label,
            payload.category_match,
            payload.model_keywords,
            payload.filter_category,
            payload.filter_type,
            payload.limit_count,
            int(payload.alternate_brands or 0),
            int(payload.allow_out_of_stock or 0),
            int(payload.sort_order or 0),
            int(payload.is_active if payload.is_active is not None else 1)
        ))
        conn.commit()
        log_audit_event("section_create", staff.get("username"), f"Created section {payload.title}")
        return {"success": True, "id": cur.lastrowid}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.put("/api/admin/sections/{section_id}")
def admin_update_section(section_id: int, payload: HomeSectionUpdateRequest, authorization: Optional[str] = Header(None)):
    staff = require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        fields = []
        params = []
        for field_name in [
            "title", "category_label", "category_match", "model_keywords", "filter_category", "filter_type",
            "limit_count", "alternate_brands", "allow_out_of_stock", "sort_order", "is_active"
        ]:
            value = getattr(payload, field_name)
            if value is not None:
                fields.append(f"{field_name} = ?")
                params.append(value)
        if fields:
            fields.append("updated_at = datetime('now')")
            params.append(section_id)
            cur.execute(f"UPDATE home_sections SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
        log_audit_event("section_update", staff.get("username"), f"Updated section {section_id}")
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/admin/sections/{section_id}/toggle")
def admin_toggle_section(section_id: int, authorization: Optional[str] = Header(None)):
    staff = require_admin(authorization)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE home_sections SET is_active = 1 - is_active, updated_at = datetime('now') WHERE id = ?",
            (section_id,)
        )
        conn.commit()
        log_audit_event("section_toggle", staff.get("username"), f"Toggled section {section_id}")
        return {"success": True}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/auth/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    conn = get_db()
    cur = conn.cursor()
    try:
        identifier = payload.identifier.strip()
        cur.execute(
            "SELECT id FROM users WHERE LOWER(email) = LOWER(?) OR phone = ?",
            (identifier.lower(), identifier)
        )
        row = cur.fetchone()
        if not row:
            # Do not reveal whether email exists
            return {"success": True}

        token, expires_at = create_password_reset(conn, row["id"])
        conn.commit()

        cur.execute("SELECT email FROM users WHERE id = ?", (row["id"],))
        user_row = cur.fetchone()
        delivered = False
        if user_row and user_row["email"]:
            delivered = send_reset_email(user_row["email"], token, expires_at)
        return {"success": True, "delivery": "email" if delivered else "pending"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/auth/reset-password")
def reset_password(payload: ResetPasswordRequest):
    conn = get_db()
    cur = conn.cursor()
    try:
        now = int(time.time())
        cur.execute("""
            SELECT id, user_id, expires_at, used
            FROM password_resets
            WHERE token = ?
        """, (payload.token,))
        row = cur.fetchone()
        if not row or row["used"] == 1 or row["expires_at"] < now:
            raise HTTPException(status_code=400, detail="Invalid or expired token")

        password_hash, password_salt = hash_password(payload.new_password)
        cur.execute("""
            UPDATE users
            SET password_hash = ?, password_salt = ?
            WHERE id = ?
        """, (password_hash, password_salt, row["user_id"]))

        cur.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (row["id"],))
        conn.commit()

        return {"success": True}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/auth/change-password")
def change_password(payload: ChangePasswordRequest, authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = authorization.split(" ", 1)[1].strip()
    user = get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, password_hash, password_salt
            FROM users
            WHERE id = ?
        """, (user["id"],))
        row = cur.fetchone()
        if not row or not verify_password(payload.current_password, row["password_hash"], row["password_salt"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        password_hash, password_salt = hash_password(payload.new_password)
        cur.execute("""
            UPDATE users
            SET password_hash = ?, password_salt = ?
            WHERE id = ?
        """, (password_hash, password_salt, user["id"]))
        conn.commit()
        return {"success": True}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/orders")
def create_order(order: OrderCreate):
    """Create new order"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # 1. Validate stock
        for item in order.items:
            cur.execute("""
                SELECT quantity FROM product_sizes
                WHERE product_id = ? AND size = ?
            """, (item.product_id, item.size))
            
            stock = cur.fetchone()
            if not stock or stock['quantity'] < item.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for product {item.product_id}, size {item.size}"
                )
        
        # 2. Create customer
        cur.execute("""
            INSERT OR REPLACE INTO customers (name, phone, email, delivery_address)
            VALUES (?, ?, ?, ?)
        """, (order.customer_name, order.customer_phone, order.customer_email, order.delivery_address))
        
        customer_id = cur.lastrowid
        
        # 3. Calculate totals
        subtotal = 0
        item_lines = []
        for item in order.items:
            cur.execute("SELECT brand, model, color, selling_price FROM products WHERE id = ?", (item.product_id,))
            row = cur.fetchone()
            price = row['selling_price']
            item_name = f"{row['brand']} {row['model']} ({row['color']})"
            subtotal += price * item.quantity
            item_lines.append(f"- {item_name} | Size {item.size} | Qty {item.quantity} | KES {price}")
        
        # Get delivery cost
        delivery_cost = next(
            (zone['cost'] for zone in DELIVERY_ZONES if zone['name'] == order.delivery_zone),
            200
        )
        
        total = subtotal + delivery_cost
        
        # 4. Create order
        order_number = f"SN{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        cur.execute("""
            INSERT INTO online_orders (
                order_number, customer_id, subtotal, delivery_cost, total_amount,
                delivery_address, delivery_method, customer_notes, source,
                status, payment_status, payment_method, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            order_number,
            customer_id,
            subtotal,
            delivery_cost,
            total,
            order.delivery_address,
            order.delivery_zone,
            order.customer_notes,
            order.source,
            "AWAITING_WHATSAPP",
            "UNPAID",
            "WHATSAPP"
        ))
        
        order_id = cur.lastrowid
        
        # 5. Add items & deduct stock
        for item in order.items:
            cur.execute("SELECT selling_price FROM products WHERE id = ?", (item.product_id,))
            unit_price = cur.fetchone()['selling_price']
            
            cur.execute("""
                INSERT INTO order_items (order_id, product_id, size, quantity, unit_price, total_price)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (order_id, item.product_id, item.size, item.quantity, unit_price, unit_price * item.quantity))
            
            cur.execute("""
                UPDATE product_sizes
                SET quantity = quantity - ?
                WHERE product_id = ? AND size = ?
            """, (item.quantity, item.product_id, item.size))
        
        conn.commit()

        message = (
            f"New Order: {order_number}\n"
            f"Customer: {order.customer_name}\n"
            f"Phone: {order.customer_phone}\n"
            f"Email: {order.customer_email or '-'}\n"
            f"Delivery: {order.delivery_zone}\n"
            f"Address: {order.delivery_address}\n"
            f"Notes: {order.customer_notes or '-'}\n"
            f"Items:\n" + "\n".join(item_lines) + "\n"
            f"Subtotal: KES {subtotal}\n"
            f"Delivery: KES {delivery_cost}\n"
            f"Total: KES {total}\n"
            "Please confirm order and payment method."
        )
        whatsapp_url = build_whatsapp_link(WHATSAPP_NUMBER, message)

        return {
            "success": True,
            "order_number": order_number,
            "total_amount": total,
            "status": "AWAITING_WHATSAPP",
            "payment_status": "UNPAID",
            "whatsapp_url": whatsapp_url
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

# ============================================
# RUN SERVER
# ============================================
if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Shoes Nexus API...")
    print(f"📁 Database: {DB_PATH}")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
