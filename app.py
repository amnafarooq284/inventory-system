
import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, date
from groq import Groq
import plotly.express as px

# ============================================================
# APP CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="AI Inventory Management System",
    page_icon="📦",
    layout="wide"
)

DB_NAME = "inventory.db"

# Change this model if you want to use another Groq-supported model
DEFAULT_MODEL = "openai/gpt-oss-120b"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# DATABASE SETUP / SAFE MIGRATION
# ============================================================

def setup_database():

    conn = get_connection()
    cursor = conn.cursor()

    # --------------------------------------------------------
    # Existing Products Table
    # --------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            supplier TEXT,
            quantity INTEGER DEFAULT 0,
            price REAL DEFAULT 0,
            reorder_level INTEGER DEFAULT 5
        )
    """)

    # --------------------------------------------------------
    # Safely add missing columns to existing products table
    # --------------------------------------------------------
    cursor.execute("PRAGMA table_info(products)")
    existing_columns = [row[1] for row in cursor.fetchall()]

    required_columns = {
        "category": "TEXT",
        "supplier": "TEXT",
        "quantity": "INTEGER DEFAULT 0",
        "price": "REAL DEFAULT 0",
        "reorder_level": "INTEGER DEFAULT 5",
        "cost_price": "REAL DEFAULT 0",
        "selling_price": "REAL DEFAULT 0" 
        "min_stock": "INTEGER DEFAULT 5"
    }

    for column, column_type in required_columns.items():

        if column not in existing_columns:
            try:
                cursor.execute(
                    f"ALTER TABLE products ADD COLUMN {column} {column_type}"
                )
            except Exception:
                pass

    # --------------------------------------------------------
    # Suppliers Table
    # --------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact TEXT,
            email TEXT,
            address TEXT,
            notes TEXT,
            created_at TEXT
        )
    """)

    # --------------------------------------------------------
    # Transactions Table
    # --------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            product_name TEXT,
            transaction_type TEXT,
            quantity INTEGER,
            unit_price REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            profit REAL DEFAULT 0,
            supplier TEXT,
            customer TEXT,
            transaction_date TEXT,
            notes TEXT
        )
    """)

    conn.commit()
    conn.close()


setup_database()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_products():
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM products ORDER BY id DESC",
        conn
    )
    conn.close()

    if "cost_price" not in df.columns:
        df["cost_price"] = 0.0

    if "selling_price" not in df.columns:
        df["selling_price"] = 0.0

    return df


def get_suppliers():
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM suppliers ORDER BY id DESC",
        conn
    )
    conn.close()
    return df


def get_transactions():
    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT *
        FROM transactions
        ORDER BY transaction_date DESC, id DESC
        """,
        conn
    )
    conn.close()
    return df


def safe_number(value):
    try:
        return float(value)
    except:
        return 0.0


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("📦 Inventory System")

page = st.sidebar.radio(
    "Navigate",
    [
        "🏠 Dashboard",
        "📦 Products",
        "🔄 Stock In / Stock Out",
        "💰 Sales",
        "🛒 Purchases",
        "📋 Transactions",
        "🚚 Suppliers",
        "📊 Reports",
        "🤖 AI Assistant"
    ]
)


# ============================================================
# LOAD DATA
# ============================================================

products_df = get_products()
suppliers_df = get_suppliers()
transactions_df = get_transactions()


# ============================================================
# DASHBOARD
# ============================================================

if page == "🏠 Dashboard":

    st.title("📊 Inventory Dashboard")
    st.write("AI-powered Inventory Management System")

    if products_df.empty:

        st.info("No products found. Add your first product from the Products page.")

    else:

        # ----------------------------------------------------
        # Dashboard Calculations
        # ----------------------------------------------------

        total_products = len(products_df)

        total_units = products_df["quantity"].fillna(0).sum()

        inventory_value = (
            products_df["quantity"].fillna(0)
            * products_df["cost_price"].fillna(0)
        ).sum()

        potential_sales = (
            products_df["quantity"].fillna(0)
            * products_df["selling_price"].fillna(0)
        ).sum()

        potential_profit = potential_sales - inventory_value

        low_stock_count = len(
            products_df[
                products_df["quantity"].fillna(0)
                <= products_df["reorder_level"].fillna(5)
            ]
        )

        # ----------------------------------------------------
        # Metrics
        # ----------------------------------------------------

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric("📦 Products", total_products)
        col2.metric("🔢 Units", int(total_units))
        col3.metric("💵 Inventory Value", f"${inventory_value:,.2f}")
        col4.metric("📈 Potential Profit", f"${potential_profit:,.2f}")
        col5.metric("⚠️ Low Stock", low_stock_count)

        st.divider()

        # ----------------------------------------------------
        # Low Stock Alerts
        # ----------------------------------------------------

        st.subheader("⚠️ Low Stock Alerts")

        low_stock = products_df[
            products_df["quantity"].fillna(0)
            <= products_df["reorder_level"].fillna(5)
        ]

        if low_stock.empty:

            st.success("All products have sufficient stock.")

        else:

            st.warning(
                f"{len(low_stock)} product(s) need attention."
            )

            st.dataframe(
                low_stock[
                    [
                        "id",
                        "name",
                        "category",
                        "supplier",
                        "quantity",
                        "reorder_level"
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )

        # ----------------------------------------------------
        # Inventory by Category
        # ----------------------------------------------------

        st.subheader("📊 Inventory by Category")

        category_data = (
            products_df
            .groupby("category", dropna=False)["quantity"]
            .sum()
            .reset_index()
        )

        category_data["category"] = category_data["category"].fillna(
            "Uncategorized"
        )

        if not category_data.empty:

            fig = px.bar(
                category_data,
                x="category",
                y="quantity",
                title="Stock Quantity by Category"
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        # ----------------------------------------------------
        # Recent Transactions
        # ----------------------------------------------------

        st.subheader("🕒 Recent Transactions")

        if transactions_df.empty:

            st.info("No transactions recorded yet.")

        else:

            st.dataframe(
                transactions_df.head(10),
                use_container_width=True,
                hide_index=True
            )


# ============================================================
# PRODUCTS
# ============================================================


elif page == "📦 Products":

    st.title("📦 Product Management")

    tab1, tab2, tab3 = st.tabs([
        "➕ Add Product",
        "👀 View Products",
        "✏️ Edit / Delete"
    ])

    # ========================================================
    # ADD PRODUCT
    # ========================================================

    with tab1:

        st.subheader("➕ Add New Product")

        with st.form("add_product_form"):

            name = st.text_input("Product Name")

            category = st.text_input("Category")

            supplier = st.text_input("Supplier")

            col1, col2 = st.columns(2)

            with col1:

                quantity = st.number_input(
                    "Quantity",
                    min_value=0,
                    value=0,
                    step=1
                )

                cost_price = st.number_input(
                    "Cost Price",
                    min_value=0.0,
                    value=0.0,
                    step=0.01
                )

            with col2:

                selling_price = st.number_input(
                    "Selling Price",
                    min_value=0.0,
                    value=0.0,
                    step=0.01
                )

                reorder_level = st.number_input(
                    "Low Stock Level",
                    min_value=0,
                    value=5,
                    step=1
                )

            add_button = st.form_submit_button(
                "➕ Add Product"
            )

            if add_button:

                if not name.strip():

                    st.error("Please enter a product name.")

                else:

                    conn = get_connection()

                    conn.execute("""
                        INSERT INTO products
                        (
                            name,
                            category,
                            supplier,
                            quantity,
                            price,
                            reorder_level,
                            cost_price,
                            selling_price,
                            min_stock
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        name,
                        category,
                        supplier,
                        quantity,
                        cost_price,
                        reorder_level,
                        cost_price,
                        selling_price,
                        reorder_level
                    ))

                    conn.commit()
                    conn.close()

                    st.success(
                        f"✅ '{name}' added successfully!"
                    )

                    
    # VIEW PRODUCTS
    # ========================================================

    with tab2:

        st.subheader("👀 All Products")

        products = get_products()

        if products.empty:

            st.info("No products found.")

        else:

            search = st.text_input(
                "🔎 Search Product"
            )

            filtered = products.copy()

            if search:

                filtered = filtered[
                    filtered["name"]
                    .astype(str)
                    .str.contains(
                        search,
                        case=False,
                        na=False
                    )
                    |
                    filtered["category"]
                    .astype(str)
                    .str.contains(
                        search,
                        case=False,
                        na=False
                    )
                    |
                    filtered["supplier"]
                    .astype(str)
                    .str.contains(
                        search,
                        case=False,
                        na=False
                    )
                ]

            st.dataframe(
                filtered,
                use_container_width=True,
                hide_index=True
            )

    # ========================================================
    # EDIT / DELETE
    # ========================================================

    with tab3:

        st.subheader("✏️ Edit / 🗑️ Delete Product")

        products = get_products()

        if products.empty:

            st.info("No products available.")

        else:

            product_options = {
                f"{row['id']} - {row['name']}": row["id"]
                for _, row in products.iterrows()
            }

            selected_product = st.selectbox(
                "Select Product",
                list(product_options.keys())
            )

            product_id = product_options[selected_product]

            product = products[
                products["id"] == product_id
            ].iloc[0]

            # ------------------------------------------------
            # EDIT
            # ------------------------------------------------

            st.markdown("### ✏️ Edit Product")

            with st.form("edit_product_form"):

                edit_name = st.text_input(
                    "Product Name",
                    value=str(product["name"])
                )

                edit_category = st.text_input(
                    "Category",
                    value=str(product["category"])
                    if pd.notna(product["category"])
                    else ""
                )

                edit_supplier = st.text_input(
                    "Supplier",
                    value=str(product["supplier"])
                    if pd.notna(product["supplier"])
                    else ""
                )

                col1, col2 = st.columns(2)

                with col1:

                    edit_quantity = st.number_input(
                        "Quantity",
                        min_value=0,
                        value=int(product["quantity"] or 0),
                        step=1
                    )

                    edit_cost = st.number_input(
                        "Cost Price",
                        min_value=0.0,
                        value=float(product["cost_price"] or 0),
                        step=0.01
                    )

                with col2:

                    edit_selling = st.number_input(
                        "Selling Price",
                        min_value=0.0,
                        value=float(
                            product["selling_price"] or 0
                        ),
                        step=0.01
                    )

                    edit_reorder = st.number_input(
                        "Low Stock Level",
                        min_value=0,
                        value=int(
                            product["reorder_level"] or 5
                        ),
                        step=1
                    )

                update_button = st.form_submit_button(
                    "💾 Update Product"
                )

                if update_button:

                    conn = get_connection()

                    conn.execute("""
                        UPDATE products
                        SET
                            name = ?,
                            category = ?,
                            supplier = ?,
                            quantity = ?,
                            price = ?,
                            reorder_level = ?,
                            cost_price = ?,
                            selling_price = ?
                        WHERE id = ?
                    """, (
                        edit_name,
                        edit_category,
                        edit_supplier,
                        edit_quantity,
                        edit_selling,
                        edit_reorder,
                        edit_cost,
                        edit_selling,
                        product_id
                    ))

                    conn.commit()
                    conn.close()

                    st.success(
                        "✅ Product updated successfully!"
                    )

                    

            st.divider()

            # ------------------------------------------------
            # DELETE
            # ------------------------------------------------

            st.markdown("### 🗑️ Delete Product")

            st.warning(
                f"You selected: **{product['name']}**"
            )

            confirm_delete = st.checkbox(
                "I understand that this product will be deleted."
            )

            if st.button(
                "🗑️ Delete Product",
                type="primary"
            ):

                if confirm_delete:

                    conn = get_connection()

                    conn.execute(
                        "DELETE FROM products WHERE id = ?",
                        (product_id,)
                    )

                    conn.commit()
                    conn.close()

                    st.success(
                        "✅ Product deleted successfully!"
                    )

                    

                else:

                    st.error(
                        "Please confirm deletion first."
                    )



elif page == "🔄 Stock In / Stock Out":

    st.title("🔄 Stock In / Stock Out")

    if products_df.empty:

        st.warning(
            "Please add products before recording stock transactions."
        )

    else:

        transaction_type = st.radio(
            "Transaction Type",
            [
                "📥 Stock In",
                "📤 Stock Out"
            ],
            horizontal=True
        )

        product_options = {
            f"{row['name']} (Stock: {int(row['quantity'])})": row["id"]
            for _, row in products_df.iterrows()
        }

        selected = st.selectbox(
            "Select Product",
            list(product_options.keys())
        )

        product_id = product_options[selected]

        product = products_df[
            products_df["id"] == product_id
        ].iloc[0]

        current_stock = int(product["quantity"])

        st.info(
            f"Current Stock: **{current_stock} units**"
        )

        quantity = st.number_input(
            "Quantity",
            min_value=1,
            value=1,
            step=1
        )

        if transaction_type == "📥 Stock In":

            unit_price = st.number_input(
                "Purchase / Cost Price per Unit",
                min_value=0.0,
                value=float(product["cost_price"] or 0),
                step=0.01
            )

            supplier = st.text_input(
                "Supplier",
                value=str(product["supplier"])
                if pd.notna(product["supplier"])
                else ""
            )

            customer = ""

            actual_type = "Stock In"

        else:

            unit_price = st.number_input(
                "Selling Price per Unit",
                min_value=0.0,
                value=float(product["selling_price"] or 0),
                step=0.01
            )

            customer = st.text_input(
                "Customer (Optional)"
            )

            supplier = ""

            actual_type = "Stock Out"

        notes = st.text_area(
            "Notes (Optional)"
        )

        transaction_date = st.date_input(
            "Transaction Date",
            value=date.today()
        )

        if st.button(
            "✅ Record Transaction"
        ):

            if actual_type == "Stock Out" and quantity > current_stock:

                st.error(
                    f"Not enough stock. Available: {current_stock}"
                )

            else:

                if actual_type == "Stock In":

                    new_stock = current_stock + quantity
                    profit = 0

                else:

                    new_stock = current_stock - quantity

                    cost_price = float(
                        product["cost_price"] or 0
                    )

                    profit = (
                        unit_price - cost_price
                    ) * quantity

                total_amount = unit_price * quantity

                conn = get_connection()

                conn.execute(
                    """
                    UPDATE products
                    SET quantity = ?
                    WHERE id = ?
                    """,
                    (
                        new_stock,
                        product_id
                    )
                )

                conn.execute(
                    """
                    INSERT INTO transactions
                    (
                        product_id,
                        product_name,
                        transaction_type,
                        quantity,
                        unit_price,
                        total_amount,
                        profit,
                        supplier,
                        customer,
                        transaction_date,
                        notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product_id,
                        product["name"],
                        actual_type,
                        quantity,
                        unit_price,
                        total_amount,
                        profit,
                        supplier,
                        customer,
                        str(transaction_date),
                        notes
                    )
                )

                conn.commit()
                conn.close()

                st.success(
                    f"{actual_type} recorded successfully!"
                )

                st.info(
                    f"New Stock Level: **{new_stock} units**"
                )

                


# ============================================================
# SALES
# ============================================================

elif page == "💰 Sales":

    st.title("💰 Sales Records")

    if products_df.empty:

        st.info("Add products first.")

    else:

        product_options = {
            row["name"]: row["id"]
            for _, row in products_df.iterrows()
        }

        product_name = st.selectbox(
            "Product",
            list(product_options.keys())
        )

        product_id = product_options[product_name]

        product = products_df[
            products_df["id"] == product_id
        ].iloc[0]

        current_stock = int(product["quantity"])

        st.info(
            f"Available Stock: **{current_stock}**"
        )

        quantity = st.number_input(
            "Quantity Sold",
            min_value=1,
            value=1,
            step=1
        )

        selling_price = st.number_input(
            "Selling Price per Unit",
            min_value=0.0,
            value=float(product["selling_price"] or 0),
            step=0.01
        )

        customer = st.text_input(
            "Customer Name (Optional)"
        )

        sale_date = st.date_input(
            "Sale Date",
            value=date.today()
        )

        notes = st.text_area(
            "Notes"
        )

        total = quantity * selling_price

        cost = float(
            product["cost_price"] or 0
        )

        profit = (
            selling_price - cost
        ) * quantity

        col1, col2 = st.columns(2)

        col1.metric(
            "Sale Amount",
            f"${total:,.2f}"
        )

        col2.metric(
            "Profit",
            f"${profit:,.2f}"
        )

        if st.button(
            "💰 Record Sale"
        ):

            if quantity > current_stock:

                st.error(
                    "Sale quantity is greater than available stock."
                )

            else:

                new_stock = current_stock - quantity

                conn = get_connection()

                conn.execute(
                    """
                    UPDATE products
                    SET quantity = ?
                    WHERE id = ?
                    """,
                    (
                        new_stock,
                        product_id
                    )
                )

                conn.execute(
                    """
                    INSERT INTO transactions
                    (
                        product_id,
                        product_name,
                        transaction_type,
                        quantity,
                        unit_price,
                        total_amount,
                        profit,
                        supplier,
                        customer,
                        transaction_date,
                        notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product_id,
                        product_name,
                        "Sale",
                        quantity,
                        selling_price,
                        total,
                        profit,
                        "",
                        customer,
                        str(sale_date),
                        notes
                    )
                )

                conn.commit()
                conn.close()

                st.success("Sale recorded successfully!")

                


# ============================================================
# PURCHASES
# ============================================================

elif page == "🛒 Purchases":

    st.title("🛒 Purchase Records")

    if products_df.empty:

        st.info("Add products first.")

    else:

        product_options = {
            row["name"]: row["id"]
            for _, row in products_df.iterrows()
        }

        product_name = st.selectbox(
            "Product",
            list(product_options.keys())
        )

        product_id = product_options[product_name]

        product = products_df[
            products_df["id"] == product_id
        ].iloc[0]

        quantity = st.number_input(
            "Quantity Purchased",
            min_value=1,
            value=1,
            step=1
        )

        purchase_price = st.number_input(
            "Purchase Price per Unit",
            min_value=0.0,
            value=float(product["cost_price"] or 0),
            step=0.01
        )

        supplier = st.text_input(
            "Supplier",
            value=str(product["supplier"])
            if pd.notna(product["supplier"])
            else ""
        )

        purchase_date = st.date_input(
            "Purchase Date",
            value=date.today()
        )

        notes = st.text_area(
            "Notes"
        )

        total = quantity * purchase_price

        st.metric(
            "Total Purchase Cost",
            f"${total:,.2f}"
        )

        if st.button(
            "🛒 Record Purchase"
        ):

            current_stock = int(product["quantity"])

            new_stock = current_stock + quantity

            conn = get_connection()

            conn.execute(
                """
                UPDATE products
                SET
                    quantity = ?,
                    cost_price = ?,
                    supplier = ?
                WHERE id = ?
                """,
                (
                    new_stock,
                    purchase_price,
                    supplier,
                    product_id
                )
            )

            conn.execute(
                """
                INSERT INTO transactions
                (
                    product_id,
                    product_name,
                    transaction_type,
                    quantity,
                    unit_price,
                    total_amount,
                    profit,
                    supplier,
                    customer,
                    transaction_date,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    product_name,
                    "Purchase",
                    quantity,
                    purchase_price,
                    total,
                    0,
                    supplier,
                    "",
                    str(purchase_date),
                    notes
                )
            )

            conn.commit()
            conn.close()

            st.success("Purchase recorded successfully!")

            


# ============================================================
# TRANSACTION HISTORY
# ============================================================

elif page == "📋 Transactions":

    st.title("📋 Transaction History")

    transactions_df = get_transactions()

    if transactions_df.empty:

        st.info(
            "No transactions recorded yet."
        )

    else:

        # ----------------------------------------------------
        # Filters
        # ----------------------------------------------------

        col1, col2, col3 = st.columns(3)

        with col1:

            transaction_types = [
                "All"
            ] + sorted(
                transactions_df[
                    "transaction_type"
                ]
                .dropna()
                .unique()
                .tolist()
            )

            selected_type = st.selectbox(
                "Transaction Type",
                transaction_types
            )

        with col2:

            min_date = pd.to_datetime(
                transactions_df[
                    "transaction_date"
                ]
            ).min().date()

            max_date = pd.to_datetime(
                transactions_df[
                    "transaction_date"
                ]
            ).max().date()

            start_date = st.date_input(
                "Start Date",
                value=min_date
            )

        with col3:

            end_date = st.date_input(
                "End Date",
                value=max_date
            )

        filtered_transactions = transactions_df.copy()

        filtered_transactions[
            "transaction_date"
        ] = pd.to_datetime(
            filtered_transactions[
                "transaction_date"
            ]
        )

        filtered_transactions = filtered_transactions[
            (
                filtered_transactions[
                    "transaction_date"
                ].dt.date >= start_date
            )
            &
            (
                filtered_transactions[
                    "transaction_date"
                ].dt.date <= end_date
            )
        ]

        if selected_type != "All":

            filtered_transactions = filtered_transactions[
                filtered_transactions[
                    "transaction_type"
                ] == selected_type
            ]

        st.subheader("Filtered Transactions")

        st.dataframe(
            filtered_transactions,
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

        total_sales = filtered_transactions[
            filtered_transactions["transaction_type"]
            == "Sale"
        ]["total_amount"].sum()

        total_purchases = filtered_transactions[
            filtered_transactions["transaction_type"]
            == "Purchase"
        ]["total_amount"].sum()

        total_profit = filtered_transactions[
            filtered_transactions["transaction_type"]
            == "Sale"
        ]["profit"].sum()

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Sales",
            f"${total_sales:,.2f}"
        )

        c2.metric(
            "Purchases",
            f"${total_purchases:,.2f}"
        )

        c3.metric(
            "Profit",
            f"${total_profit:,.2f}"
        )


# ============================================================
# SUPPLIER MANAGEMENT
# ============================================================

elif page == "🚚 Suppliers":

    st.title("🚚 Supplier Management")

    tab1, tab2 = st.tabs(
        [
            "➕ Add Supplier",
            "📋 Supplier List"
        ]
    )

    with tab1:

        with st.form("supplier_form"):

            supplier_name = st.text_input(
                "Supplier Name"
            )

            contact = st.text_input(
                "Contact Number"
            )

            email = st.text_input(
                "Email"
            )

            address = st.text_area(
                "Address"
            )

            notes = st.text_area(
                "Notes"
            )

            submitted = st.form_submit_button(
                "➕ Add Supplier"
            )

            if submitted:

                if not supplier_name.strip():

                    st.error(
                        "Please enter supplier name."
                    )

                else:

                    conn = get_connection()

                    conn.execute(
                        """
                        INSERT INTO suppliers
                        (
                            name,
                            contact,
                            email,
                            address,
                            notes,
                            created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            supplier_name,
                            contact,
                            email,
                            address,
                            notes,
                            datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                        )
                    )

                    conn.commit()
                    conn.close()

                    st.success(
                        "Supplier added successfully!"
                    )

                    

    with tab2:

        suppliers_df = get_suppliers()

        if suppliers_df.empty:

            st.info(
                "No suppliers added yet."
            )

        else:

            st.dataframe(
                suppliers_df,
                use_container_width=True,
                hide_index=True
            )


# ============================================================
# REPORTS
# ============================================================

elif page == "📊 Reports":

    st.title("📊 Business Reports")

    products_df = get_products()
    transactions_df = get_transactions()

    # --------------------------------------------------------
    # Inventory Report
    # --------------------------------------------------------

    st.subheader("📦 Current Inventory Report")

    if products_df.empty:

        st.info("No inventory data.")

    else:

        inventory_report = products_df.copy()

        inventory_report[
            "inventory_value"
        ] = (
            inventory_report["quantity"]
            * inventory_report["cost_price"]
        )

        inventory_report[
            "potential_sales"
        ] = (
            inventory_report["quantity"]
            * inventory_report["selling_price"]
        )

        inventory_report[
            "potential_profit"
        ] = (
            inventory_report["potential_sales"]
            - inventory_report["inventory_value"]
        )

        st.dataframe(
            inventory_report,
            use_container_width=True,
            hide_index=True
        )

        csv_inventory = inventory_report.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "⬇️ Download Inventory CSV",
            data=csv_inventory,
            file_name="inventory_report.csv",
            mime="text/csv"
        )

    st.divider()

    # --------------------------------------------------------
    # Sales Report
    # --------------------------------------------------------

    st.subheader("💰 Sales Report")

    if transactions_df.empty:

        st.info("No transaction data.")

    else:

        sales_report = transactions_df[
            transactions_df[
                "transaction_type"
            ] == "Sale"
        ].copy()

        if sales_report.empty:

            st.info("No sales recorded yet.")

        else:

            st.dataframe(
                sales_report,
                use_container_width=True,
                hide_index=True
            )

            csv_sales = sales_report.to_csv(
                index=False
            ).encode("utf-8")

            st.download_button(
                "⬇️ Download Sales CSV",
                data=csv_sales,
                file_name="sales_report.csv",
                mime="text/csv"
            )

    st.divider()

    # --------------------------------------------------------
    # Purchase Report
    # --------------------------------------------------------

    st.subheader("🛒 Purchase Report")

    if transactions_df.empty:

        st.info("No purchase data.")

    else:

        purchase_report = transactions_df[
            transactions_df[
                "transaction_type"
            ] == "Purchase"
        ].copy()

        if purchase_report.empty:

            st.info(
                "No purchases recorded yet."
            )

        else:

            st.dataframe(
                purchase_report,
                use_container_width=True,
                hide_index=True
            )

            csv_purchase = purchase_report.to_csv(
                index=False
            ).encode("utf-8")

            st.download_button(
                "⬇️ Download Purchase CSV",
                data=csv_purchase,
                file_name="purchase_report.csv",
                mime="text/csv"
            )

    st.divider()

    # --------------------------------------------------------
    # Complete Transactions CSV
    # --------------------------------------------------------

    if not transactions_df.empty:

        csv_transactions = transactions_df.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "⬇️ Download Complete Transaction History",
            data=csv_transactions,
            file_name="transaction_history.csv",
            mime="text/csv"
        )


# ============================================================
# AI ASSISTANT
# ============================================================

elif page == "🤖 AI Assistant":

    st.title("🤖 AI Inventory Assistant")

    st.write(
        "Ask questions about your inventory, sales, "
        "purchases, stock levels, and business data."
    )

    # --------------------------------------------------------
    # API Key
    # --------------------------------------------------------

    api_key = os.environ.get("GROQ_API_KEY", "")

    # --------------------------------------------------------
    # Quick Questions
    # --------------------------------------------------------

    st.subheader("💡 Quick Questions")

    quick_question = st.selectbox(
        "Choose a question",
        [
            "Select a question",
            "Which products are low in stock?",
            "What is the current inventory value?",
            "Which products have the highest potential profit?",
            "Summarize my recent sales.",
            "Summarize my recent purchases.",
            "Give me useful inventory management suggestions."
        ]
    )

    user_question = st.text_area(
        "Or type your own question"
    )

    if st.button(
        "🤖 Ask AI"
    ):

        if not api_key:

            st.error(
                "Please enter your Groq API key."
            )

        else:

            question = user_question.strip()

            if not question and quick_question != "Select a question":

                question = quick_question

            if not question:

                st.warning(
                    "Please select or type a question."
                )

            else:

                try:

                    client = Groq(
                        api_key=api_key
                    )

                    # ------------------------------------------------
                    # Prepare inventory information for AI
                    # ------------------------------------------------

                    inventory_context = products_df[
                        [
                            "name",
                            "category",
                            "supplier",
                            "quantity",
                            "cost_price",
                            "selling_price",
                            "reorder_level"
                        ]
                    ].to_string(
                        index=False
                    )

                    transaction_context = transactions_df.head(
                        50
                    ).to_string(
                        index=False
                    )

                    system_prompt = f"""
You are a helpful business inventory assistant.

Analyze the inventory information below.

CURRENT INVENTORY:
{inventory_context}

RECENT TRANSACTIONS:
{transaction_context}

Give practical, clear and beginner-friendly answers.

Do not invent inventory numbers.

If the requested information is not available,
say that clearly.

You can help with:
- Stock analysis
- Low-stock identification
- Sales analysis
- Purchase analysis
- Inventory value
- Profit calculations
- Restocking suggestions
- General inventory management
"""

                    response = client.chat.completions.create(
                        model=DEFAULT_MODEL,
                        messages=[
                            {
                                "role": "system",
                                "content": system_prompt
                            },
                            {
                                "role": "user",
                                "content": question
                            }
                        ],
                        temperature=0.2
                    )

                    answer = response.choices[
                        0
                    ].message.content

                    st.subheader(
                        "🤖 AI Response"
                    )

                    st.write(answer)

                except Exception as e:

                    st.error(
                        f"AI Error: {e}"
                    )


# ============================================================
# FOOTER
# ============================================================

st.sidebar.divider()

st.sidebar.caption(
    "📦 AI Inventory Management System"
)

st.sidebar.caption(
    "SQLite database • Streamlit • Groq AI"
)
