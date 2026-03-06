from db_config import DB_PATH
import sqlite3
import calendar
import pandas as pd
import streamlit as st
from theme_admin import apply_admin_theme


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_monthly_stock_takes_table(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS monthly_stock_takes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_key TEXT NOT NULL,
            checkpoint_type TEXT NOT NULL,
            due_date DATE NOT NULL,
            completed_at DATETIME,
            total_products INTEGER,
            total_units INTEGER,
            total_value REAL,
            completed_by TEXT,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(month_key, checkpoint_type)
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_monthly_stock_takes_month_due "
        "ON monthly_stock_takes(month_key, due_date)"
    )
    conn.commit()


def ensure_stock_take_submission_tables(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_take_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month_key TEXT,
            checkpoint_type TEXT,
            stock_take_type TEXT NOT NULL,
            stock_take_date DATE NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            submitted_by TEXT,
            submitted_role TEXT,
            approved_by TEXT,
            approved_at DATETIME,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_take_submission_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            size TEXT NOT NULL,
            counted_qty INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_stock_take_submissions_status_created "
        "ON stock_take_submissions(status, created_at)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_stock_take_lines_submission "
        "ON stock_take_submission_lines(submission_id)"
    )
    conn.commit()


def month_schedule_dates(month_key):
    year, month = [int(x) for x in str(month_key).split("-")]
    start_dt = pd.Timestamp(year=year, month=month, day=1)
    end_day = calendar.monthrange(year, month)[1]
    end_dt = pd.Timestamp(year=year, month=month, day=end_day)
    return {
        "OPENING": start_dt.strftime("%Y-%m-%d"),
        "AUDIT_1": (start_dt + pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
        "AUDIT_2": (start_dt + pd.Timedelta(days=14)).strftime("%Y-%m-%d"),
        "CLOSING": end_dt.strftime("%Y-%m-%d"),
    }


def ensure_month_schedule_rows(conn, month_key):
    schedule = month_schedule_dates(month_key)
    cur = conn.cursor()
    for checkpoint_type, due_date in schedule.items():
        cur.execute(
            """
            INSERT OR IGNORE INTO monthly_stock_takes
            (month_key, checkpoint_type, due_date)
            VALUES (?, ?, ?)
            """,
            (str(month_key), str(checkpoint_type), str(due_date)),
        )
    conn.commit()


def _stock_take_order():
    return ["OPENING", "AUDIT_1", "AUDIT_2", "CLOSING"]


def _started_checkpoints_for_date(month_key, ref_date=None):
    ref = pd.Timestamp.today().normalize() if ref_date is None else pd.Timestamp(ref_date).normalize()
    schedule = month_schedule_dates(month_key)
    started = ["OPENING"]
    if ref >= pd.Timestamp(schedule["AUDIT_1"]):
        started.append("AUDIT_1")
    if ref >= pd.Timestamp(schedule["AUDIT_2"]):
        started.append("AUDIT_2")
    if ref >= pd.Timestamp(schedule["CLOSING"]):
        started.append("CLOSING")
    return started


def required_checkpoint(conn, month_key):
    ensure_month_schedule_rows(conn, month_key)
    df = pd.read_sql(
        """
        SELECT checkpoint_type, due_date, completed_at
        FROM monthly_stock_takes
        WHERE month_key = ?
        ORDER BY due_date ASC
        """,
        conn,
        params=(month_key,),
    )
    if df.empty:
        return None, df
    started = set(_started_checkpoints_for_date(month_key))
    done = {
        str(row["checkpoint_type"]): bool(pd.notna(row["completed_at"]) and str(row["completed_at"]).strip())
        for _, row in df.iterrows()
    }
    for cp in _stock_take_order():
        if cp in started and not done.get(cp, False):
            return cp, df
    return None, df


def load_inventory_lines(conn):
    raw = pd.read_sql(
        """
        SELECT
            p.id AS product_id,
            p.brand,
            p.model,
            p.color,
            COALESCE(p.category, '') AS category,
            COALESCE(p.buying_price, 0) AS buying_price,
            ps.size,
            COALESCE(ps.quantity, 0) AS system_qty
        FROM products p
        LEFT JOIN product_sizes ps ON ps.product_id = p.id
        WHERE COALESCE(p.is_active, 0) = 1
          AND NOT (
              LOWER(TRIM(COALESCE(p.category, ''))) = 'external'
              AND LOWER(TRIM(COALESCE(p.brand, ''))) = 'brokered'
              AND LOWER(TRIM(COALESCE(p.model, ''))) = 'brokered sale'
          )
        ORDER BY p.brand, p.model, p.color, CAST(ps.size AS INTEGER)
        """,
        conn,
    )
    if raw.empty:
        return raw

    def _allowed_sizes(category):
        c = str(category or "").strip().lower()
        if c == "women":
            return [str(s) for s in range(35, 42)]
        if c == "men":
            return [str(s) for s in range(40, 46)]
        return []

    products = (
        raw[["product_id", "brand", "model", "color", "category", "buying_price"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    rows = []
    for _, p in products.iterrows():
        pid = int(p["product_id"])
        p_rows = raw[raw["product_id"] == pid].copy()
        existing_sizes = set(p_rows["size"].dropna().astype(str).tolist())
        required_sizes = set(_allowed_sizes(p.get("category", "")))
        all_sizes = sorted(existing_sizes.union(required_sizes), key=lambda x: (len(x), x))
        for size in all_sizes:
            match = p_rows[p_rows["size"].astype(str) == str(size)]
            system_qty = int(match["system_qty"].iloc[0]) if not match.empty else 0
            rows.append(
                {
                    "product_id": pid,
                    "brand": str(p["brand"]),
                    "model": str(p["model"]),
                    "color": str(p["color"]),
                    "buying_price": float(p["buying_price"] or 0),
                    "size": str(size),
                    "system_qty": int(system_qty),
                }
            )
    return pd.DataFrame(rows)


def load_stock_reconciliation_alerts(conn):
    """Compare on-hand size stock with cost-layer remaining stock."""
    try:
        system_df = pd.read_sql(
            """
            SELECT
                p.id AS product_id,
                COALESCE(p.brand, '') AS brand,
                COALESCE(p.model, '') AS model,
                COALESCE(p.color, '') AS color,
                COALESCE(ps.size, '') AS size,
                COALESCE(ps.quantity, 0) AS system_qty
            FROM products p
            JOIN product_sizes ps ON ps.product_id = p.id
            WHERE COALESCE(p.is_active, 0) = 1
              AND NOT (
                  LOWER(TRIM(COALESCE(p.category, ''))) = 'external'
                  AND LOWER(TRIM(COALESCE(p.brand, ''))) = 'brokered'
                  AND LOWER(TRIM(COALESCE(p.model, ''))) = 'brokered sale'
              )
            """,
            conn,
        )
        layer_df = pd.read_sql(
            """
            SELECT
                product_id,
                COALESCE(size, '') AS size,
                COALESCE(SUM(remaining_qty), 0) AS layer_qty
            FROM stock_cost_layers
            GROUP BY product_id, size
            """,
            conn,
        )
    except Exception:
        return pd.DataFrame()

    merged = system_df.merge(layer_df, on=["product_id", "size"], how="outer")
    if merged.empty:
        return merged

    product_meta = system_df[["product_id", "brand", "model", "color"]].drop_duplicates("product_id")
    merged = merged.merge(product_meta, on="product_id", how="left", suffixes=("", "_meta"))
    merged["brand"] = merged["brand"].fillna(merged.get("brand_meta", ""))
    merged["model"] = merged["model"].fillna(merged.get("model_meta", ""))
    merged["color"] = merged["color"].fillna(merged.get("color_meta", ""))
    merged["system_qty"] = pd.to_numeric(merged["system_qty"], errors="coerce").fillna(0).astype(int)
    merged["layer_qty"] = pd.to_numeric(merged["layer_qty"], errors="coerce").fillna(0).astype(int)
    merged["delta_qty"] = merged["system_qty"] - merged["layer_qty"]
    mismatches = merged[merged["delta_qty"] != 0].copy()
    if mismatches.empty:
        return mismatches
    return mismatches.sort_values(["brand", "model", "color", "size"]).reset_index(drop=True)


def reset_wip():
    st.session_state.stock_take_wip_lines = {}
    st.session_state.stock_take_wip_index = 0
    st.session_state.stock_take_wip_saved_pid = None


def flatten_wip_rows(wip_lines):
    rows = []
    for _, item in wip_lines.items():
        for size, qty in item["sizes"].items():
            rows.append(
                {
                    "product_id": int(item["product_id"]),
                    "brand": item["brand"],
                    "model": item["model"],
                    "color": item["color"],
                    "size": str(size),
                    "counted_qty": int(qty),
                    "buying_price": float(item["buying_price"]),
                }
            )
    return pd.DataFrame(rows)


def compute_totals_from_rows(lines_df):
    if lines_df.empty:
        return 0, 0, 0.0
    non_zero = lines_df[lines_df["counted_qty"] > 0]
    total_products = int(non_zero["product_id"].nunique()) if not non_zero.empty else 0
    total_units = int(lines_df["counted_qty"].sum())
    total_value = float((lines_df["counted_qty"] * lines_df["buying_price"]).sum())
    return total_products, total_units, total_value


def compute_reconciliation_delta(inventory_df, counted_df):
    if counted_df.empty:
        return pd.DataFrame()
    system = (
        inventory_df[["product_id", "size", "system_qty"]]
        .copy()
        .drop_duplicates(subset=["product_id", "size"], keep="first")
    )
    counted = counted_df[["product_id", "brand", "model", "color", "size", "counted_qty"]].copy()
    merged = counted.merge(system, on=["product_id", "size"], how="left")
    merged["system_qty"] = pd.to_numeric(merged["system_qty"], errors="coerce").fillna(0).astype(int)
    merged["counted_qty"] = pd.to_numeric(merged["counted_qty"], errors="coerce").fillna(0).astype(int)
    merged["delta_qty"] = merged["counted_qty"] - merged["system_qty"]
    mismatch = merged[merged["delta_qty"] != 0].copy()
    return mismatch


def record_activity(cur, event_type, role, username, message):
    cur.execute(
        """
        INSERT INTO activity_log
        (event_type, reference_id, role, username, message)
        VALUES (?, NULL, ?, ?, ?)
        """,
        (str(event_type), str(role), str(username), str(message)),
    )


st.set_page_config(page_title="Stock Take", layout="wide")
apply_admin_theme("Stock Take", "Run guided counts for mandatory and ad-hoc inventory checkpoints.")

if not st.session_state.get("logged_in", False):
    st.warning("Session expired. Please log in again.")
    if st.button("Go to Login", key="stock_take_go_login"):
        st.switch_page("app.py")
    st.stop()

role = str(st.session_state.get("role", ""))
if role not in {"Admin", "Manager", "Cashier"}:
    st.error("Access denied.")
    st.stop()

username = str(st.session_state.get("username", "unknown"))
month_key = pd.Timestamp.today().strftime("%Y-%m")

conn = get_db()
ensure_monthly_stock_takes_table(conn)
ensure_stock_take_submission_tables(conn)
ensure_month_schedule_rows(conn, month_key)

required_cp, status_df = required_checkpoint(conn, month_key)
status_df = pd.read_sql(
    """
    SELECT
        checkpoint_type,
        due_date,
        completed_at,
        COALESCE(total_products, 0) AS total_products,
        COALESCE(total_units, 0) AS total_units,
        COALESCE(total_value, 0) AS total_value
    FROM monthly_stock_takes
    WHERE month_key = ?
    ORDER BY due_date ASC
    """,
    conn,
    params=(month_key,),
)
today_str = pd.Timestamp.today().strftime("%Y-%m-%d")
if not status_df.empty:
    status_df["status"] = status_df.apply(
        lambda r: (
            "COMPLETED"
            if pd.notna(r["completed_at"]) and str(r["completed_at"]).strip()
            else ("OVERDUE" if str(r["due_date"]) < today_str else "PENDING")
        ),
        axis=1,
    )

st.subheader("Mandatory Stock Take Status")
st.caption(f"Current month: {month_key}. Mandatory sequence: OPENING, AUDIT_1, AUDIT_2, CLOSING.")
if status_df.empty:
    st.warning("No schedule rows found.")
else:
    if role in {"Manager", "Cashier"}:
        lite = status_df.rename(
            columns={
                "checkpoint_type": "Checkpoint",
                "due_date": "Due Date",
                "completed_at": "Completed Date",
            }
        )[["Checkpoint", "Due Date", "Completed Date"]]
        st.dataframe(lite, hide_index=True, use_container_width=True)
    else:
        admin_view = status_df.rename(
            columns={
                "checkpoint_type": "Checkpoint",
                "due_date": "Due Date",
                "completed_at": "Completed Date",
                "total_products": "Total Products",
                "total_units": "Total Units",
                "total_value": "Total Value (KES)",
                "status": "Status",
            }
        )
        admin_view["Total Value (KES)"] = admin_view["Total Value (KES)"].map(lambda x: int(float(x or 0)))
        st.dataframe(admin_view, hide_index=True, use_container_width=True)

if required_cp:
    st.warning(f"Required now: {required_cp}. Complete this mandatory stock take first.")
else:
    st.success("No mandatory checkpoint is currently due.")

st.divider()
st.subheader("Stock Reconciliation Alerts")
st.caption("Red alerts show size-level mismatches between on-hand stock and movement-based stock (sales, returns, exchanges, restocks).")
recon_alerts_df = load_stock_reconciliation_alerts(conn)
if recon_alerts_df.empty:
    st.success("No reconciliation mismatches detected right now.")
else:
    last_recon_at = pd.read_sql(
        "SELECT MAX(created_at) AS last_at FROM stock_take_submissions",
        conn,
    ).iloc[0]["last_at"]
    net_variance = int(recon_alerts_df["delta_qty"].sum())
    st.error(
        f"{len(recon_alerts_df)} stock line(s) are mismatched. "
        f"Net variance: {net_variance} unit(s)."
    )
    m1, m2, m3 = st.columns(3)
    m1.metric("Mismatch Lines", int(len(recon_alerts_df)))
    m2.metric("Net Variance (Units)", int(net_variance))
    m3.metric("Last Count Submitted", str(last_recon_at or "None"))

    with st.expander("Show mismatch details", expanded=False):
        view_mode = st.selectbox(
            "Detail View",
            [
                "All mismatches",
                "High variance only (>= 3 units)",
                "Only shortages (negative variance)",
                "Only overages (positive variance)",
            ],
            key="stock_take_recon_view_mode",
        )
        detail_df = recon_alerts_df.copy()
        if view_mode == "High variance only (>= 3 units)":
            detail_df = detail_df[detail_df["delta_qty"].abs() >= 3].copy()
        elif view_mode == "Only shortages (negative variance)":
            detail_df = detail_df[detail_df["delta_qty"] < 0].copy()
        elif view_mode == "Only overages (positive variance)":
            detail_df = detail_df[detail_df["delta_qty"] > 0].copy()

        brands = ["All"] + sorted(detail_df["brand"].fillna("").astype(str).unique().tolist())
        selected_brand = st.selectbox("Brand", brands, key="stock_take_recon_brand")
        if selected_brand != "All":
            detail_df = detail_df[detail_df["brand"] == selected_brand].copy()

        models = ["All"] + sorted(detail_df["model"].fillna("").astype(str).unique().tolist())
        selected_model = st.selectbox("Model", models, key="stock_take_recon_model")
        if selected_model != "All":
            detail_df = detail_df[detail_df["model"] == selected_model].copy()

        colors = ["All"] + sorted(detail_df["color"].fillna("").astype(str).unique().tolist())
        selected_color = st.selectbox("Color", colors, key="stock_take_recon_color")
        if selected_color != "All":
            detail_df = detail_df[detail_df["color"] == selected_color].copy()

        sizes = ["All"] + sorted(detail_df["size"].fillna("").astype(str).unique().tolist())
        selected_size = st.selectbox("Size", sizes, key="stock_take_recon_size")
        if selected_size != "All":
            detail_df = detail_df[detail_df["size"] == selected_size].copy()

        if detail_df.empty:
            st.info("No mismatches for the selected filters.")
        else:
            st.dataframe(
                detail_df[
                    ["brand", "model", "color", "size", "system_qty", "layer_qty", "delta_qty"]
                ].rename(
                    columns={
                        "brand": "Brand",
                        "model": "Model",
                        "color": "Color",
                        "size": "Size",
                        "system_qty": "On-hand Qty",
                        "layer_qty": "Expected Qty",
                        "delta_qty": "Variance",
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )

st.divider()
st.subheader("Guided Stock Take")
mode = st.radio(
    "Stock Take Type",
    ["Mandatory", "Ad Hoc"],
    horizontal=True,
    key="stock_take_mode",
)

if mode == "Mandatory":
    if not required_cp:
        st.info("No pending mandatory checkpoint is active now. Use Ad Hoc for optional counts.")
        checkpoint = None
    else:
        checkpoint = required_cp
        st.caption(f"Checkpoint: {checkpoint}")
else:
    checkpoint = None

stock_take_date = st.date_input("Stock Take Date", value=pd.Timestamp.today().date(), key="stock_take_date")
notes = st.text_area("Notes (optional)", key="stock_take_notes", placeholder="Counting notes or exceptions.")

inventory_df = load_inventory_lines(conn)
if inventory_df.empty:
    st.warning("No active product sizes found for counting.")
    conn.close()
    st.stop()

product_df = (
    inventory_df[["product_id", "brand", "model", "color", "buying_price"]]
    .drop_duplicates()
    .sort_values(["brand", "model", "color"])
    .reset_index(drop=True)
)

if "stock_take_wip_lines" not in st.session_state:
    reset_wip()

signature = f"{mode}|{checkpoint}|{stock_take_date}"
if st.session_state.get("stock_take_signature") != signature:
    st.session_state.stock_take_signature = signature
    reset_wip()

if st.session_state.stock_take_wip_index >= len(product_df):
    st.session_state.stock_take_wip_index = len(product_df) - 1

current_idx = int(st.session_state.stock_take_wip_index)
progress = current_idx + 1
st.caption(f"Progress: Product {progress} of {len(product_df)}")

current_product = product_df.iloc[current_idx]
pid = int(current_product["product_id"])
brand = str(current_product["brand"])
model = str(current_product["model"])
color = str(current_product["color"])
buying_price = float(current_product["buying_price"] or 0)
size_rows = inventory_df[inventory_df["product_id"] == pid].copy().sort_values("size")

st.markdown(f"### {brand} {model} ({color})")
st.caption("Enter physical counted quantity for every size, including 0 where not found.")

default_sizes = {}
if str(pid) in st.session_state.stock_take_wip_lines:
    default_sizes = st.session_state.stock_take_wip_lines[str(pid)]["sizes"]

counted_sizes = {}
for _, r in size_rows.iterrows():
    size = str(r["size"])
    initial = int(default_sizes.get(size, 0))
    key = f"stk_qty_{pid}_{size}"
    counted_sizes[size] = int(
        st.number_input(
            f"Size {size}",
            min_value=0,
            step=1,
            value=initial,
            key=key,
        )
    )

save_col, next_col, prev_col = st.columns([1, 1, 1])
with save_col:
    if st.button("Save Product Count", key=f"save_prod_{pid}", use_container_width=True):
        st.session_state.stock_take_wip_lines[str(pid)] = {
            "product_id": pid,
            "brand": brand,
            "model": model,
            "color": color,
            "buying_price": buying_price,
            "sizes": counted_sizes,
        }
        st.session_state.stock_take_wip_saved_pid = pid
        st.success("Product count saved.")
with next_col:
    if st.button("Next Product", key=f"next_prod_{pid}", use_container_width=True):
        if str(pid) not in st.session_state.stock_take_wip_lines:
            st.error("Save current product count before moving next.")
        elif current_idx < len(product_df) - 1:
            st.session_state.stock_take_wip_index = current_idx + 1
            st.rerun()
with prev_col:
    if st.button("Previous Product", key=f"prev_prod_{pid}", use_container_width=True):
        if current_idx > 0:
            st.session_state.stock_take_wip_index = current_idx - 1
            st.rerun()

if str(pid) in st.session_state.stock_take_wip_lines:
    summary_rows = []
    for size, qty in st.session_state.stock_take_wip_lines[str(pid)]["sizes"].items():
        summary_rows.append({"Size": str(size), "Counted Qty": int(qty)})
    st.caption("Current product summary")
    st.dataframe(pd.DataFrame(summary_rows), hide_index=True, use_container_width=True)

all_done = len(st.session_state.stock_take_wip_lines) == len(product_df)
st.divider()
st.subheader("Submission Summary")
st.write(f"Products counted: {len(st.session_state.stock_take_wip_lines)} / {len(product_df)}")

if all_done:
    flat = flatten_wip_rows(st.session_state.stock_take_wip_lines)
    total_products, total_units, total_value = compute_totals_from_rows(flat)
    st.dataframe(
        flat[["brand", "model", "color", "size", "counted_qty"]].rename(
            columns={"counted_qty": "Counted Qty", "brand": "Brand", "model": "Model", "color": "Color", "size": "Size"}
        ),
        hide_index=True,
        use_container_width=True,
    )
    st.info(
        f"Summary totals: Products in stock={total_products}, Units={total_units}, "
        f"Value KES {int(total_value)}."
    )

    recon_df = compute_reconciliation_delta(inventory_df, flat)
    if not recon_df.empty:
        variance_units = int(recon_df["delta_qty"].sum())
        st.error(
            f"Reconciliation alert: {len(recon_df)} size line(s) do not match system stock. "
            f"Net variance: {variance_units} unit(s)."
        )
        st.dataframe(
            recon_df[
                ["brand", "model", "color", "size", "system_qty", "counted_qty", "delta_qty"]
            ].rename(
                columns={
                    "brand": "Brand",
                    "model": "Model",
                    "color": "Color",
                    "size": "Size",
                    "system_qty": "System Qty",
                    "counted_qty": "Counted Qty",
                    "delta_qty": "Variance",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )

    can_submit = True
    if mode == "Mandatory" and not checkpoint:
        can_submit = False
    if st.button("Submit Stock Take", type="primary", disabled=not can_submit, use_container_width=True):
        cur = conn.cursor()
        submission_status = "APPROVED" if role == "Admin" else "PENDING"
        recon_df = compute_reconciliation_delta(inventory_df, flat)
        recon_count = int(len(recon_df))
        recon_units = int(recon_df["delta_qty"].sum()) if recon_count > 0 else 0
        cur.execute(
            """
            INSERT INTO stock_take_submissions
            (month_key, checkpoint_type, stock_take_type, stock_take_date, status, submitted_by, submitted_role, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                month_key if mode == "Mandatory" else None,
                checkpoint,
                "MANDATORY" if mode == "Mandatory" else "ADHOC",
                str(stock_take_date),
                submission_status,
                username,
                role,
                str(notes or ""),
            ),
        )
        submission_id = int(cur.lastrowid)
        line_rows = []
        for _, row in flat.iterrows():
            line_rows.append((submission_id, int(row["product_id"]), str(row["size"]), int(row["counted_qty"])))
        cur.executemany(
            """
            INSERT INTO stock_take_submission_lines (submission_id, product_id, size, counted_qty)
            VALUES (?, ?, ?, ?)
            """,
            line_rows,
        )

        if role == "Admin" and mode == "Mandatory" and checkpoint:
            cur.execute(
                """
                UPDATE monthly_stock_takes
                SET completed_at = CURRENT_TIMESTAMP,
                    total_products = ?,
                    total_units = ?,
                    total_value = ?,
                    completed_by = ?,
                    notes = ?
                WHERE month_key = ?
                  AND checkpoint_type = ?
                """,
                (
                    int(total_products),
                    int(total_units),
                    float(total_value),
                    username,
                    str(notes or ""),
                    month_key,
                    checkpoint,
                ),
            )

        record_activity(
            cur,
            "STOCK_TAKE_SUBMITTED",
            role,
            username,
            f"Submission #{submission_id} created ({mode}, checkpoint={checkpoint or 'N/A'}, status={submission_status}).",
        )
        if recon_count > 0:
            record_activity(
                cur,
                "STOCK_TAKE_RECON_ALERT",
                role,
                username,
                (
                    f"Submission #{submission_id} reconciliation mismatch: "
                    f"{recon_count} line(s), net variance {recon_units} unit(s). "
                    f"System stock includes sales/returns/exchanges/restocks."
                ),
            )
        conn.commit()
        reset_wip()
        if role == "Admin":
            st.success("Stock take submitted and applied.")
        else:
            st.success("Stock take submitted for admin approval.")
        st.rerun()
else:
    st.warning("Count all products before submission.")

st.divider()
st.subheader("My Recent Stock Take Submissions")
mine = pd.read_sql(
    """
    SELECT
        id,
        stock_take_type,
        COALESCE(checkpoint_type, 'ADHOC') AS checkpoint,
        stock_take_date,
        status,
        created_at,
        approved_by,
        approved_at
    FROM stock_take_submissions
    WHERE submitted_by = ?
    ORDER BY id DESC
    LIMIT 20
    """,
    conn,
    params=(username,),
)
if mine.empty:
    st.info("No submissions yet.")
else:
    st.dataframe(mine, hide_index=True, use_container_width=True)

if role == "Admin":
    st.divider()
    st.subheader("Pending Approval Queue")
    pending = pd.read_sql(
        """
        SELECT
            id,
            stock_take_type,
            COALESCE(checkpoint_type, 'ADHOC') AS checkpoint,
            stock_take_date,
            submitted_by,
            submitted_role,
            created_at
        FROM stock_take_submissions
        WHERE status = 'PENDING'
        ORDER BY created_at ASC
        """,
        conn,
    )
    if pending.empty:
        st.info("No pending stock take submissions.")
    else:
        st.dataframe(pending, hide_index=True, use_container_width=True)
        selected_id = st.selectbox(
            "Select submission to review",
            pending["id"].tolist(),
            key="stock_take_pending_select",
        )
        review_note = st.text_area("Admin review note", key="stock_take_admin_note")
        lines = pd.read_sql(
            """
            SELECT
                l.product_id,
                p.brand,
                p.model,
                p.color,
                l.size,
                l.counted_qty,
                COALESCE(p.buying_price, 0) AS buying_price
            FROM stock_take_submission_lines l
            JOIN products p ON p.id = l.product_id
            WHERE l.submission_id = ?
            ORDER BY p.brand, p.model, p.color, CAST(l.size AS INTEGER)
            """,
            conn,
            params=(int(selected_id),),
        )
        if not lines.empty:
            st.dataframe(
                lines[["brand", "model", "color", "size", "counted_qty"]].rename(
                    columns={
                        "brand": "Brand",
                        "model": "Model",
                        "color": "Color",
                        "size": "Size",
                        "counted_qty": "Counted Qty",
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )
            current_system = pd.read_sql(
                """
                SELECT product_id, size, COALESCE(quantity, 0) AS system_qty
                FROM product_sizes
                """,
                conn,
            )
            review_df = lines[["product_id", "brand", "model", "color", "size", "counted_qty"]].copy()
            review_df = review_df.merge(current_system, on=["product_id", "size"], how="left")
            review_df["system_qty"] = pd.to_numeric(review_df["system_qty"], errors="coerce").fillna(0).astype(int)
            review_df["counted_qty"] = pd.to_numeric(review_df["counted_qty"], errors="coerce").fillna(0).astype(int)
            review_df["delta_qty"] = review_df["counted_qty"] - review_df["system_qty"]
            mismatch_review = review_df[review_df["delta_qty"] != 0].copy()
            if not mismatch_review.empty:
                st.error(
                    f"Reconciliation alert: {len(mismatch_review)} line(s) mismatch current system stock."
                )
                st.dataframe(
                    mismatch_review[
                        ["brand", "model", "color", "size", "system_qty", "counted_qty", "delta_qty"]
                    ].rename(
                        columns={
                            "brand": "Brand",
                            "model": "Model",
                            "color": "Color",
                            "size": "Size",
                            "system_qty": "System Qty",
                            "counted_qty": "Counted Qty",
                            "delta_qty": "Variance",
                        }
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
            t_products, t_units, t_value = compute_totals_from_rows(
                lines.rename(columns={"counted_qty": "counted_qty", "buying_price": "buying_price"})[
                    ["product_id", "counted_qty", "buying_price"]
                ]
            )
            st.caption(f"Submission totals: Products={t_products}, Units={t_units}, Value KES {int(t_value)}")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Approve Submission", type="primary", use_container_width=True):
                cur = conn.cursor()
                row = cur.execute(
                    """
                    SELECT month_key, checkpoint_type, stock_take_type
                    FROM stock_take_submissions
                    WHERE id = ? AND status = 'PENDING'
                    """,
                    (int(selected_id),),
                ).fetchone()
                if not row:
                    st.error("Submission is no longer pending.")
                else:
                    month_key_sub, checkpoint_sub, type_sub = row
                    cur.execute(
                        """
                        UPDATE stock_take_submissions
                        SET status = 'APPROVED',
                            approved_by = ?,
                            approved_at = CURRENT_TIMESTAMP,
                            notes = COALESCE(notes, '') || CASE WHEN ? <> '' THEN ' | ADMIN: ' || ? ELSE '' END
                        WHERE id = ?
                        """,
                        (username, str(review_note or ""), str(review_note or ""), int(selected_id)),
                    )

                    if str(type_sub) == "MANDATORY" and checkpoint_sub and month_key_sub:
                        totals_row = cur.execute(
                            """
                            SELECT
                                COALESCE(COUNT(DISTINCT CASE WHEN l.counted_qty > 0 THEN l.product_id END), 0) AS total_products,
                                COALESCE(SUM(l.counted_qty), 0) AS total_units,
                                COALESCE(SUM(l.counted_qty * COALESCE(p.buying_price, 0)), 0) AS total_value
                            FROM stock_take_submission_lines l
                            JOIN products p ON p.id = l.product_id
                            WHERE l.submission_id = ?
                            """,
                            (int(selected_id),),
                        ).fetchone()
                        cur.execute(
                            """
                            UPDATE monthly_stock_takes
                            SET completed_at = CURRENT_TIMESTAMP,
                                total_products = ?,
                                total_units = ?,
                                total_value = ?,
                                completed_by = ?,
                                notes = COALESCE(notes, '') || CASE WHEN ? <> '' THEN ' | ADMIN: ' || ? ELSE '' END
                            WHERE month_key = ?
                              AND checkpoint_type = ?
                            """,
                            (
                                int(totals_row[0] or 0),
                                int(totals_row[1] or 0),
                                float(totals_row[2] or 0),
                                username,
                                str(review_note or ""),
                                str(review_note or ""),
                                str(month_key_sub),
                                str(checkpoint_sub),
                            ),
                        )

                    record_activity(
                        cur,
                        "STOCK_TAKE_APPROVED",
                        role,
                        username,
                        f"Approved stock take submission #{selected_id}.",
                    )
                    conn.commit()
                    st.success("Submission approved.")
                    st.rerun()
        with b2:
            if st.button("Reject Submission", use_container_width=True):
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE stock_take_submissions
                    SET status = 'REJECTED',
                        approved_by = ?,
                        approved_at = CURRENT_TIMESTAMP,
                        notes = COALESCE(notes, '') || CASE WHEN ? <> '' THEN ' | ADMIN: Rejected - ' || ? ELSE '' END
                    WHERE id = ? AND status = 'PENDING'
                    """,
                    (username, str(review_note or ""), str(review_note or ""), int(selected_id)),
                )
                record_activity(
                    cur,
                    "STOCK_TAKE_REJECTED",
                    role,
                    username,
                    f"Rejected stock take submission #{selected_id}.",
                )
                conn.commit()
                st.warning("Submission rejected.")
                st.rerun()

conn.close()
