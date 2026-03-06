from db_config import DB_PATH
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import time
from theme_admin import apply_admin_theme
from ui_feedback import show_success_summary

# ============================================
# DATABASE CONNECTION
# ============================================
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# ============================================
# HELPER: SAFE INT
# ============================================
def to_int(value, default=0):
    if value is None:
        return default
    if isinstance(value, (bytes, bytearray)):
        try:
            return int.from_bytes(value, byteorder="little")
        except Exception:
            return default
    try:
        return int(value)
    except Exception:
        return default

# ============================================
# HELPER FUNCTION: Sync Product Stock
# ============================================
def sync_product_stock(cur, product_id):
    """Sync main products table stock with product_sizes total"""
    cur.execute("""
        UPDATE products
        SET stock = (
            SELECT COALESCE(SUM(quantity), 0)
            FROM product_sizes
            WHERE product_id = ?
        )
        WHERE id = ?
    """, (product_id, product_id))

# ============================================
# PAGE SETUP
# ============================================
st.set_page_config(page_title="Returns & Exchanges", layout="wide")
apply_admin_theme(
    "Returns and Exchanges",
    "Review, approve, and track return and exchange requests.",
)

if not st.session_state.get("logged_in", False):
    st.warning("Session expired. Please log in again.")
    if st.button("Go to Login", key="returns_go_login"):
        st.switch_page("app.py")
    st.stop()

# ============================================
# CUSTOM CSS
# ============================================
st.markdown("""
    <style>
    .return-header {
        background: linear-gradient(135deg, #ffffff 0%, #f7f7f9 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        color: #111111;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        border: 1px solid #d0d5df;
    }
    
    .return-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    .return-subtitle {
        font-size: 1.1rem;
        opacity: 0.9;
    }
    
    .request-card {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #e11d2a;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================
# DB PATH BANNER
# ============================================
st.markdown(
    f"""
    <div style="margin-bottom: 1rem; padding: 0.75rem 1rem; border-radius: 10px; background: #111827; color: #e5e7eb; border: 1px solid #374151;">
        <strong>Database:</strong> {DB_PATH}
    </div>
    """,
    unsafe_allow_html=True
)

# ============================================
# HEADER
# ============================================
st.markdown(f"""
    <div class="return-header">
        <div class="return-title">🔁 Returns & Exchanges</div>
        <div class="return-subtitle">Manage product returns and exchanges</div>
    </div>
""", unsafe_allow_html=True)

# ============================================
# ROLE-BASED INTERFACE
# ============================================

if st.session_state.role == "Cashier":
    # ========================================
    # CASHIER: REQUEST RETURN
    # ========================================
    st.subheader("📝 Request Product Return")
    
    conn = get_db()
    
    # Get recent sales (last 30 days)
    recent_sales = pd.read_sql("""
        SELECT 
            s.id,
            s.sale_date,
            p.brand,
            p.model,
            p.color,
            s.size,
            s.quantity,
            s.returned_quantity,
            s.return_status,
            s.revenue,
            s.payment_method
        FROM sales s
        JOIN products p ON p.id = s.product_id
        WHERE s.sale_date >= date('now', '-30 days')
          AND s.return_status != 'FULL'
        ORDER BY s.sale_date DESC
    """, conn)
    
    if recent_sales.empty:
        st.info("ℹ️ No recent sales found (last 30 days)")
        conn.close()
        st.stop()
    
    # Display recent sales
    st.dataframe(
        recent_sales,
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("---")
    
    # Return request form
    with st.form("return_request_form"):
        st.subheader("Submit Return Request")
        
        sale_id = st.selectbox(
            "Select Sale ID",
            recent_sales["id"],
            format_func=lambda x: f"Sale #{x} - {recent_sales[recent_sales['id']==x]['brand'].values[0]} {recent_sales[recent_sales['id']==x]['model'].values[0]} (Size {recent_sales[recent_sales['id']==x]['size'].values[0]})"
        )
        
        # Get selected sale details
        selected_sale = recent_sales[recent_sales["id"] == sale_id].iloc[0]
        
        # Calculate returnable quantity (account for pending requests)
        sold_qty = int(selected_sale["quantity"])
        already_returned = int(selected_sale["returned_quantity"]) if selected_sale["returned_quantity"] else 0
        pending_qty = 0
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT COALESCE(SUM(quantity), 0)
                FROM returns_exchanges
                WHERE sale_id = ?
                  AND type = 'RETURN'
                  AND status = 'PENDING'
            """, (int(sale_id),))
            pending_qty = to_int(cur.fetchone()[0])
        except Exception:
            pending_qty = 0
        returnable_qty = sold_qty - already_returned - pending_qty
        
        st.info(f"""
        **Sale Details:**
        - Product: {selected_sale['brand']} {selected_sale['model']} ({selected_sale['color']})
        - Size: {selected_sale['size']}
        - Sold: {sold_qty} pairs
        - Already Returned: {already_returned} pairs
        - Pending Return Requests: {pending_qty} pairs
        - Available to Return: {returnable_qty} pairs
        - Sale Date: {selected_sale['sale_date']}
        """)
        
        if returnable_qty <= 0:
            st.error("❌ This sale has no returnable quantity left (already returned or pending)")
            st.stop()
        
        return_quantity = st.number_input(
            "Quantity to Return",
            min_value=1,
            max_value=returnable_qty,
            value=1
        )
        
        reason = st.text_area(
            "Reason for Return",
            placeholder="Why is the customer returning this product?",
            help="Be specific: size issue, defect, wrong item, etc."
        )
        
        submit = st.form_submit_button("📤 Submit Return Request", type="primary")
        
        if submit:
            if not reason.strip():
                st.error("⚠️ Please provide a reason for the return")
            else:
                cur = conn.cursor()
                
                try:
                    # Insert return request
                    cur.execute("""
                        INSERT INTO returns_exchanges
                        (sale_id, type, quantity, size, notes, initiated_by, status)
                        VALUES (?, 'RETURN', ?, ?, ?, ?, 'PENDING')
                    """, (
                        int(sale_id),
                        int(return_quantity),
                        str(selected_sale['size']),
                        reason,
                        st.session_state.username
                    ))
                    
                    request_id = cur.lastrowid
                    
                    # Activity log
                    cur.execute("""
                        INSERT INTO activity_log
                        (event_type, reference_id, role, username, message)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        "RETURN_REQUESTED",
                        request_id,
                        st.session_state.role,
                        st.session_state.username,
                        f"Return request for Sale #{sale_id}, Qty {return_quantity}, Size {selected_sale['size']}"
                    ))
                    
                    conn.commit()
                    
                    show_success_summary(
                        "Return request submitted successfully.",
                        [
                            ("Request ID", int(request_id)),
                            ("Sale ID", int(sale_id)),
                            ("Size", str(selected_sale["size"])),
                            ("Quantity", int(return_quantity)),
                            ("Status", "PENDING"),
                        ],
                    )
                                        
                except Exception as e:
                    conn.rollback()
                    st.error(f"❌ Error: {e}")
                finally:
                    conn.close()

elif st.session_state.role == "Manager":
    # ========================================
    # MANAGER: VIEW & APPROVE RETURNS
    # ========================================
    
    tab1, tab2 = st.tabs(["📋 Pending Requests", "✅ Approved Returns"])
    
    with tab1:
        st.subheader("Pending Return Requests")
        
        conn = get_db()
        
        pending_df = pd.read_sql("""
            SELECT
                r.id AS request_id,
                r.sale_id,
                r.quantity,
                r.size,
                r.notes,
                r.initiated_by,
                r.created_at,
                COALESCE(p.brand, 'Unknown') AS brand,
                COALESCE(p.model, 'Unknown') AS model,
                COALESCE(p.color, '') AS color,
                s.revenue
            FROM returns_exchanges r
            LEFT JOIN sales s ON s.id = r.sale_id
            LEFT JOIN products p ON p.id = s.product_id
            WHERE r.type = 'RETURN'
              AND r.status = 'PENDING'
            ORDER BY r.created_at ASC
        """, conn)
        
        if pending_df.empty:
            st.success("🎉 No pending return requests")
        else:
            st.dataframe(pending_df, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.info("ℹ️ Only Admin can approve returns. You can view them here.")
        
        conn.close()
    
    with tab2:
        st.subheader("Approved Returns History")
        
        conn = get_db()
        
        approved_df = pd.read_sql("""
            SELECT
                r.id,
                r.sale_id,
                r.quantity,
                r.size,
                r.approved_by,
                r.created_at,
                COALESCE(p.brand, 'Unknown') AS brand,
                COALESCE(p.model, 'Unknown') AS model
            FROM returns_exchanges r
            LEFT JOIN sales s ON s.id = r.sale_id
            LEFT JOIN products p ON p.id = s.product_id
            WHERE r.type = 'RETURN'
              AND r.status = 'APPROVED'
            ORDER BY r.created_at DESC
            LIMIT 50
        """, conn)
        
        if approved_df.empty:
            st.info("No approved returns yet")
        else:
            st.dataframe(approved_df, use_container_width=True, hide_index=True)
        
        conn.close()

elif st.session_state.role == "Admin":
    # ========================================
    # ADMIN: FULL RETURN MANAGEMENT
    # ========================================
    
    tab1, tab2, tab3 = st.tabs(["🛂 Approve Returns", "📊 Return Analytics", "📋 All Returns"])
    
    with tab1:
        st.subheader("🛂 Pending Return Requests")
        
        conn = get_db()
        df = pd.read_sql("""
            SELECT
                r.id AS request_id,
                r.sale_id,
                r.size,
                r.quantity AS return_qty,
                r.notes,
                r.initiated_by,
                p.id AS product_id,
                COALESCE(p.brand, 'Unknown') AS brand,
                COALESCE(p.model, 'Unknown') AS model,
                COALESCE(p.color, '') AS color,
                s.quantity AS sold_qty,
                s.revenue
            FROM returns_exchanges r
            LEFT JOIN sales s ON s.id = r.sale_id
            LEFT JOIN products p ON p.id = s.product_id
            WHERE r.type = 'RETURN'
              AND r.status = 'PENDING'
            ORDER BY r.created_at ASC
        """, conn)
        
        if df.empty:
            st.success("🎉 No pending return requests!")
            conn.close()
        else:
            # Display pending requests
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            # Approval interface
            request_id = st.selectbox(
                "Select Request to Process",
                df["request_id"],
                format_func=lambda x: (
                    f"Request #{x} - " +
                    df[df["request_id"]==x]["brand"].values[0] + " " +
                    df[df["request_id"]==x]["model"].values[0] + " " +
                    f"(Size {df[df['request_id']==x]['size'].values[0]}, " +
                    f"Qty {df[df['request_id']==x]['return_qty'].values[0]})"
                )
            )
            
            row = df[df["request_id"] == request_id].iloc[0]

            st.markdown(f"""
            <div class="request-card">
                <h4>📦 Return Request Details</h4>
                <p><strong>Product:</strong> {row['brand']} {row['model']} ({row['color']})</p>
                <p><strong>Size:</strong> {row['size']}</p>
                <p><strong>Quantity:</strong> {row['return_qty']} pairs</p>
                <p><strong>Requested by:</strong> {row['initiated_by']}</p>
                <p><strong>Reason:</strong> {row['notes']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            admin_note = st.text_area(
                "📝 Admin Notes",
                placeholder="Your decision reason..."
            )

            st.markdown("**Cancel Pending Returns**")
            cancel_confirm = st.text_input(
                "Type CANCEL PENDING to enable cancel",
                key="cancel_pending_confirm"
            )
            cancel_cols = st.columns(2)
            with cancel_cols[0]:
                if st.button("🗑️ Cancel This Pending Return", use_container_width=True):
                    if cancel_confirm.strip().upper() != "CANCEL PENDING":
                        st.error("❌ Confirmation required.")
                    else:
                        cur = conn.cursor()
                        try:
                            cur.execute(
                                """
                                UPDATE returns_exchanges
                                SET status = 'CANCELLED',
                                    notes = COALESCE(notes, '') || ' | ADMIN: Cancelled pending'
                                WHERE id = ? AND status = 'PENDING'
                                """,
                                (to_int(request_id),)
                            )
                            cur.execute(
                                """
                                INSERT INTO activity_log
                                (event_type, reference_id, role, username, message)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (
                                    "RETURN_CANCELLED",
                                    to_int(request_id),
                                    "Admin",
                                    st.session_state.username,
                                    f"Cancelled pending return #{request_id}"
                                )
                            )
                            conn.commit()
                            show_success_summary(
                                "Pending return cancelled.",
                                [
                                    ("Request ID", int(request_id)),
                                    ("Status", "CANCELLED"),
                                ],
                            )
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"❌ Error: {e}")
            with cancel_cols[1]:
                if st.button("🧹 Cancel All Pending for This Sale", use_container_width=True):
                    if cancel_confirm.strip().upper() != "CANCEL PENDING":
                        st.error("❌ Confirmation required.")
                    else:
                        cur = conn.cursor()
                        try:
                            cur.execute(
                                """
                                UPDATE returns_exchanges
                                SET status = 'CANCELLED',
                                    notes = COALESCE(notes, '') || ' | ADMIN: Cancelled pending'
                                WHERE sale_id = ? AND status = 'PENDING'
                                """,
                                (to_int(row["sale_id"]),)
                            )
                            cur.execute(
                                """
                                INSERT INTO activity_log
                                (event_type, reference_id, role, username, message)
                                VALUES (?, ?, ?, ?, ?)
                                """,
                                (
                                    "RETURN_CANCELLED",
                                    to_int(row["sale_id"]),
                                    "Admin",
                                    st.session_state.username,
                                    f"Cancelled all pending returns for sale {to_int(row['sale_id'])}"
                                )
                            )
                            conn.commit()
                            show_success_summary(
                                "All pending returns for this sale cancelled.",
                                [
                                    ("Sale ID", to_int(row["sale_id"])),
                                    ("Status", "CANCELLED"),
                                ],
                            )
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"❌ Error: {e}")

            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("✅ Approve Return", type="primary", use_container_width=True):
                    cur = conn.cursor()
                    
                    try:
                        # Check sale status
                        cur.execute("""
                            SELECT quantity, COALESCE(returned_quantity, 0), return_status
                            FROM sales WHERE id = ?
                        """, (int(row["sale_id"]),))
                        
                        result = cur.fetchone()
                        if not result:
                            st.error("❌ Sale not found")
                            conn.close()
                            st.stop()
                        
                        sold_qty = to_int(result[0])
                        already_returned = to_int(result[1])
                        is_brokered = (
                            str(row["brand"]).strip().lower() == "brokered"
                            and str(row["model"]).strip().lower() == "brokered sale"
                        )
                        # Validate (account for other pending requests)
                        return_qty = to_int(row["return_qty"])
                        cur.execute("""
                            SELECT COALESCE(SUM(quantity), 0)
                            FROM returns_exchanges
                            WHERE sale_id = ?
                              AND type = 'RETURN'
                              AND status = 'PENDING'
                              AND id != ?
                        """, (to_int(row["sale_id"]), to_int(request_id)))
                        pending_other = to_int(cur.fetchone()[0])
                        remaining_qty = sold_qty - already_returned - (0 if is_brokered else pending_other)
                        if return_qty > remaining_qty:
                            st.error(f"❌ Cannot return more than sold quantity. Remaining: {remaining_qty} (Sold {sold_qty}, Returned {already_returned}, Pending {pending_other})")
                            conn.close()
                            st.stop()
                        # Update sales
                        new_returned = already_returned + return_qty
                        new_status = 'FULL' if new_returned >= sold_qty else 'PARTIAL'
                        
                        cur.execute("""
                            UPDATE sales
                            SET returned_quantity = ?,
                                return_status = ?
                            WHERE id = ?
                        """, (new_returned, new_status, to_int(row["sale_id"])))
                        
                        # Restore stock (skip for brokered sales)
                        if not is_brokered:
                            cur.execute("""
                                INSERT INTO product_sizes (product_id, size, quantity)
                                VALUES (?, ?, 0)
                                ON CONFLICT(product_id, size) DO NOTHING
                            """, (to_int(row["product_id"]), str(row["size"])))
                            
                            cur.execute("""
                                UPDATE product_sizes
                                SET quantity = quantity + ?
                                WHERE product_id = ? AND size = ?
                            """, (return_qty, to_int(row["product_id"]), str(row["size"])))
                            
                            sync_product_stock(cur, to_int(row["product_id"]))
                        
                        # Approve return request
                        cur.execute("""
                            UPDATE returns_exchanges
                            SET status = 'APPROVED',
                                approved_by = ?,
                                notes = COALESCE(notes, '') || ' | ADMIN: ' || ?
                            WHERE id = ?
                        """, (st.session_state.username, admin_note, to_int(request_id)))
                        
                        # Log
                        cur.execute("""
                            INSERT INTO activity_log
                            (event_type, reference_id, role, username, message)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            "RETURN_APPROVED",
                            to_int(request_id),
                            "Admin",
                            st.session_state.username,
                            f"Approved return #{request_id} - {row['brand']} {row['model']}, Size {row['size']}, Qty {return_qty}"
                        ))
                        
                        conn.commit()
                        show_success_summary(
                            "Return approved.",
                            [
                                ("Request ID", to_int(request_id)),
                                ("Sale ID", to_int(row["sale_id"])),
                                ("Size", str(row["size"])),
                                ("Quantity", int(return_qty)),
                                ("Status", "APPROVED"),
                            ],
                        )
                        time.sleep(1)
                        st.rerun()
                        
                    except Exception as e:
                        conn.rollback()
                        st.error(f"❌ Error: {e}")
                    finally:
                        conn.close()
            
            with col2:
                if st.button("❌ Reject Return", type="secondary", use_container_width=True):
                    cur = conn.cursor()
                    
                    try:
                        cur.execute("""
                            UPDATE returns_exchanges
                            SET status = 'REJECTED',
                                notes = COALESCE(notes, '') || ' | ADMIN: ' || ?
                            WHERE id = ?
                        """, (admin_note, int(request_id)))
                        
                        cur.execute("""
                            INSERT INTO activity_log
                            (event_type, reference_id, role, username, message)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            "RETURN_REJECTED",
                            int(request_id),
                            "Admin",
                            st.session_state.username,
                            f"Rejected return #{request_id}"
                        ))
                        
                        conn.commit()
                        st.warning("❌ Return rejected")
                        time.sleep(1)
                        st.rerun()
                        
                    except Exception as e:
                        conn.rollback()
                        st.error(f"❌ Error: {e}")
                    finally:
                        conn.close()
    
    with tab2:
        st.subheader("📊 Return Analytics")
        
        conn = get_db()
        
        # Return statistics
        stats = pd.read_sql("""
            SELECT
                COUNT(*) as total_returns,
                COALESCE(SUM(CASE WHEN status = 'APPROVED' THEN 1 ELSE 0 END), 0) as approved,
                COALESCE(SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END), 0) as rejected,
                COALESCE(SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END), 0) as pending
            FROM returns_exchanges
            WHERE type = 'RETURN'
        """, conn).iloc[0]

        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Returns", int(stats['total_returns']))
        with col2:
            st.metric("Approved", int(stats['approved']), delta=None, delta_color="normal")
        with col3:
            st.metric("Rejected", int(stats['rejected']), delta=None, delta_color="inverse")
        with col4:
            st.metric("Pending", int(stats['pending']), delta=None, delta_color="off")
        
        conn.close()
    
    with tab3:
        st.subheader("📋 Complete Returns History")
        
        conn = get_db()
        
        all_returns = pd.read_sql("""
            SELECT
                r.id,
                r.sale_id,
                r.quantity,
                r.size,
                r.status,
                r.initiated_by,
                r.approved_by,
                r.created_at,
                COALESCE(p.brand, 'Unknown') AS brand,
                COALESCE(p.model, 'Unknown') AS model
            FROM returns_exchanges r
            LEFT JOIN sales s ON s.id = r.sale_id
            LEFT JOIN products p ON p.id = s.product_id
            WHERE r.type = 'RETURN'
            ORDER BY r.created_at DESC
            LIMIT 100
        """, conn)
        
        if all_returns.empty:
            st.info("No returns history")
        else:
            st.dataframe(all_returns, use_container_width=True, hide_index=True)
        
        conn.close()

else:
    st.error("⛔ Access Denied")










