import streamlit as st
import pandas as pd
from io import BytesIO
import datetime
from PIL import Image

# --- 0. 系統設定 (必須放在第一行) ---
st.set_page_config(page_title="企業倉儲管理系統_資安版", layout="wide")

# ==========================================
# 🔐 資安設定區 (在此設定你的密碼)
# ==========================================
LOGIN_PASSWORD = "mpd991219"  # <--- 請在此修改你的登入密碼
# ==========================================

# --- 1. 登入驗證邏輯 ---
def check_password():
    """驗證密碼是否正確"""
    def password_entered():
        if st.session_state["password"] == LOGIN_PASSWORD:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # 驗證後刪除密碼暫存，確保安全
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # 尚未登入狀態
        st.header("🔒 系統鎖定中")
        st.write("這是內部管理系統，請輸入授權密碼以繼續。")
        st.text_input("請輸入密碼", type="password", on_change=password_entered, key="password")
        return False
    
    elif not st.session_state["password_correct"]:
        # 密碼錯誤狀態
        st.header("🔒 系統鎖定中")
        st.text_input("請輸入密碼", type="password", on_change=password_entered, key="password")
        st.error("❌ 密碼錯誤，請重新輸入")
        return False
    
    else:
        # 登入成功
        return True

# --- 主程式執行判斷 ---
if check_password():
    # ==========================================
    # 以下為主要的應用程式邏輯 (只有登入成功才會執行)
    # ==========================================
    
    # --- 2. 初始化資料存儲 ---
    if 'df_purchase' not in st.session_state:
        st.session_state.df_purchase = pd.DataFrame(columns=['單號', '日期', '品名', '數量', '單價', '對象', '有照片'])
    if 'df_sales' not in st.session_state:
        st.session_state.df_sales = pd.DataFrame(columns=['單號', '日期', '品名', '數量', '單價', '對象', '有照片'])
    if 'df_settings' not in st.session_state:
        st.session_state.df_settings = pd.DataFrame(columns=['品名', '安全庫存量'])
    if 'image_db' not in st.session_state:
        st.session_state.image_db = {}

    # --- 3. 核心運算 ---
    def get_inventory():
        p = st.session_state.df_purchase.groupby('品名').agg({'數量': 'sum', '單價': 'mean'}).rename(columns={'數量': '進貨總數', '單價': '平均進價'})
        s = st.session_state.df_sales.groupby('品名').agg({'數量': 'sum', '單價': 'mean'}).rename(columns={'數量': '出貨總數', '單價': '平均售價'})
        
        inv = pd.concat([p, s], axis=1).fillna(0)
        inv['目前庫存'] = inv['進貨總數'] - inv['出貨總數']
        inv['庫存價值'] = inv['目前庫存'] * inv['平均進價']
        inv = inv.reset_index()

        # 關聯安全庫存
        settings = st.session_state.df_settings
        if not settings.empty:
            settings_clean = settings.drop_duplicates(subset=['品名'], keep='last')
            inv = pd.merge(inv, settings_clean, on='品名', how='left')
        else:
            inv['安全庫存量'] = 0 
        
        inv['安全庫存量'] = inv['安全庫存量'].fillna(0)
        inv['狀態'] = inv.apply(lambda x: '⚠️ 低庫存警報' if x['目前庫存'] < x['安全庫存量'] else '✅ 充足', axis=1)
        return inv

    current_inventory = get_inventory()

    # --- 4. 側邊欄：戰情中心 ---
    st.sidebar.title("🚨 戰情中心")
    
    # 低庫存警報
    low_stock_df = current_inventory[current_inventory['狀態'] == '⚠️ 低庫存警報']
    if not low_stock_df.empty:
        st.sidebar.error(f"警告：{len(low_stock_df)} 項商品缺貨！")
        for index, row in low_stock_df.iterrows():
            st.sidebar.write(f"🔴 **{row['品名']}** (剩 {row['目前庫存']})")
    else:
        st.sidebar.success("目前庫存安全")

    st.sidebar.divider()
    st.sidebar.header("📊 即時摘要")
    st.sidebar.dataframe(current_inventory[['品名', '目前庫存']], hide_index=True)

    # 報表導出
    st.sidebar.header("📥 報表導出")
    def convert_to_excel(df, sheet_name):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_export = df.drop(columns=['有照片'], errors='ignore') 
            df_export.to_excel(writer, sheet_name=sheet_name, index=False)
        return output.getvalue()

    if st.sidebar.button("📄 下載採購單"):
        if not st.session_state.df_purchase.empty:
            data = convert_to_excel(st.session_state.df_purchase, '採購單')
            st.sidebar.download_button("💾 存檔", data, "purchase.xlsx")

    if st.sidebar.button("🚚 下載出貨單"):
        if not st.session_state.df_sales.empty:
            data = convert_to_excel(st.session_state.df_sales, 'sales.xlsx')
            st.sidebar.download_button("💾 存檔", data, "sales.xlsx")

    if st.sidebar.button("📦 下載庫存表"):
        if not current_inventory.empty:
            data = convert_to_excel(current_inventory, '庫存預警表')
            st.sidebar.download_button("💾 存檔", data, "inventory.xlsx")

    # === 登出按鈕 ===
    st.sidebar.divider()
    if st.sidebar.button("🔒 安全登出"):
        del st.session_state["password_correct"]
        st.rerun()

    # --- 5. 主介面邏輯 ---
    st.title("🏗️ 企業營建倉儲系統 (已加密)")
    tabs = st.tabs(["🆕 單據錄入", "📋 對帳與庫存", "⚙️ 設定"]) 

    # 分頁 1: 錄入
    with tabs[0]:
        col_in, col_out = st.columns(2)
        with col_in:
            st.subheader("➕ 進貨錄入")
            with st.form("p_form", clear_on_submit=True):
                p_no = st.text_input("進貨單號")
                p_name = st.text_input("品名")
                p_qty = st.number_input("數量", min_value=0, step=1)
                p_price = st.number_input("單價", min_value=0, step=1)
                p_obj = st.text_input("供應商")
                p_img = st.file_uploader("照片", type=['png', 'jpg', 'jpeg'], key="p_up")
                if st.form_submit_button("確認進貨"):
                    if p_name and p_no:
                        has_img = "❌"
                        if p_img:
                            img = Image.open(p_img).convert('RGB')
                            img.thumbnail((400, 400))
                            st.session_state.image_db[p_no] = img
                            has_img = "✅"
                        new_row = pd.DataFrame([[p_no, datetime.date.today(), p_name, p_qty, p_price, p_obj, has_img]], columns=st.session_state.df_purchase.columns)
                        st.session_state.df_purchase = pd.concat([st.session_state.df_purchase, new_row], ignore_index=True)
                        st.rerun()

        with col_out:
            st.subheader("➖ 出貨錄入")
            with st.form("s_form", clear_on_submit=True):
                s_no = st.text_input("出貨單號")
                s_name = st.text_input("品名")
                s_qty = st.number_input("數量", min_value=0, step=1)
                s_price = st.number_input("售價", min_value=0, step=1)
                s_obj = st.text_input("客戶")
                s_img = st.file_uploader("照片", type=['png', 'jpg', 'jpeg'], key="s_up")
                if st.form_submit_button("確認出貨"):
                    stock = current_inventory[current_inventory['品名'] == s_name]['目前庫存'].sum()
                    if stock >= s_qty:
                        has_img = "❌"
                        if s_img:
                            img = Image.open(s_img).convert('RGB')
                            img.thumbnail((400, 400))
                            st.session_state.image_db[s_no] = img
                            has_img = "✅"
                        new_row = pd.DataFrame([[s_no, datetime.date.today(), s_name, s_qty, s_price, s_obj, has_img]], columns=st.session_state.df_sales.columns)
                        st.session_state.df_sales = pd.concat([st.session_state.df_sales, new_row], ignore_index=True)
                        st.rerun()
                    else:
                        st.error("庫存不足")

    # 分頁 2: 庫存與對帳
    with tabs[1]:
        st.subheader("📊 庫存總覽")
        def highlight_low_stock(row):
            return ['background-color: #ffcccc; color: black'] * len(row) if row['目前庫存'] < row['安全庫存量'] else [''] * len(row)
        
        st.dataframe(current_inventory.style.apply(highlight_low_stock, axis=1).format({"庫存價值": "${:,.0f}"}), use_container_width=True)
        st.divider()
        
        # 照片與刪除
        with st.expander("🔍 照片查詢 / 🗑️ 數據刪除"):
            c1, c2 = st.columns(2)
            s_no = c1.text_input("輸入單號查照片")
            if s_no in st.session_state.image_db:
                c1.image(st.session_state.image_db[s_no])
            
            if not st.session_state.df_purchase.empty:
                idx = c2.number_input("刪除進貨Index", 0, len(st.session_state.df_purchase)-1, step=1)
                if c2.button("刪除進貨"):
                    st.session_state.df_purchase = st.session_state.df_purchase.drop(idx).reset_index(drop=True)
                    st.rerun()

    # 分頁 3: 設定
    with tabs[2]:
        st.subheader("⚙️ 安全庫存設定")
        with st.form("set_form"):
            all_prods = list(set(st.session_state.df_purchase['品名']) | set(st.session_state.df_sales['品名']))
            name = st.selectbox("產品", all_prods + ["(新手動輸入)"])
            if name == "(新手動輸入)": name = st.text_input("輸入名稱")
            qty = st.number_input("安全庫存量", 1)
            if st.form_submit_button("儲存"):
                if name:
                    new = pd.DataFrame([[name, qty]], columns=['品名', '安全庫存量'])
                    st.session_state.df_settings = pd.concat([st.session_state.df_settings, new], ignore_index=True).drop_duplicates('品名', keep='last')
                    st.success(f"已設定 {name}")
                    st.rerun()
        st.dataframe(st.session_state.df_settings)
