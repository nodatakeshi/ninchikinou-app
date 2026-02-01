import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import json
from google.oauth2.service_account import Credentials
import gspread
import os

st.set_page_config(page_title="認知機能回復プログラム", layout="wide")
st.title("認知機能回復プログラム")

#/content/drive/MyDrive/secrets.json

def get_gspread_client():
    """環境に合わせて認証情報を取得する"""
    # 1. ローカル/Colab環境（ファイルがある場合）
    if os.path.exists('/content/drive/MyDrive/secrets.json'):
        with open('/content/drive/MyDrive/secrets.json', 'r') as f:
            creds_dict = json.load(f)
    # 2. 公開環境（Streamlit CloudのSecretsを使う場合）
    else:
        creds_dict = dict(st.secrets["connections"]["gsheets"])
        
        # Streamlit Cloud上でも改行コードの置換が必要な場合があります
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(credentials)

SPREADSHEET_ID = "1xw5ilkQdxqUoOQ_Nohi16nF_WlcMElb8J8LF_4vrU9s"
WORKSHEET_NAME = "Sheet1"

# --- 以下、データ操作とUI部分はそのまま ---
def load_data():
    client = get_gspread_client()
    sh = client.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet(WORKSHEET_NAME)
    return pd.DataFrame(worksheet.get_all_records())

def save_to_sheets():
    try:
        df = load_data()
        user_name = st.session_state.user_name
        new_row = {"name": user_name, "total": sum(st.session_state.scores)}
        for i, s in enumerate(st.session_state.scores):
            new_row[f"q{i+1}"] = s

        if not df.empty:
            df = df[df["name"] != user_name].copy()

        updated_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        client = get_gspread_client()
        worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
        worksheet.clear()
        worksheet.update([updated_df.columns.values.tolist()] + updated_df.values.tolist())
    except Exception as e:
        st.error(f"保存に失敗しました: {e}")

def style_ranking(row):
    color = ''
    if row.name == 0:    # 1位
        color = 'background-color: #ffd700; color: black; font-weight: bold;'
    elif row.name == 1:  # 2位
        color = 'background-color: #c0c0c0; color: black; font-weight: bold;'
    elif row.name == 2:  # 3位
        color = 'background-color: #cd7f32; color: white; font-weight: bold;'
    return [color] * len(row)


if 'user_name' not in st.session_state:
    st.session_state.user_name = ""

if not st.session_state.user_name:
    name = st.text_input("あなたの名前（ニックネーム）を入力してください")
    if name:
        st.session_state.user_name = name
        # ログインした瞬間に、DBからその人の過去データをロードする
        try:
            df = load_data()
            user_data = df[df["name"] == name]
            if not user_data.empty:
                # すでにデータがあれば、q1〜q15をリストとして取り出す
                row = user_data.iloc[0]
                st.session_state.scores = [int(row[f"q{i+1}"]) for i in range(15)]
            else:
                st.session_state.scores = [0] * 15
        except:
            st.session_state.scores = [0] * 15
        st.rerun()
    st.stop()

st.write(f"こんにちは、**{st.session_state.user_name}** さん！")

if 'scores' not in st.session_state:
    st.session_state.scores = [0] * 15

def update_data(index):
    st.session_state.scores[index] = st.session_state[f"q_{index}"]
    save_to_sheets()

with st.expander("📝 スコアを入力してね", expanded=True):
    # 15問を3問ずつのセットにしてループを回す
    for i in range(0, 15, 3):
        cols = st.columns(3)
        # 1行（3列）の中に、順番に問を入れていく
        for j in range(3):
            idx = i + j
            if idx < 15:
                with cols[j]:
                    st.number_input(
                        f"問{idx+1}", 
                        key=f"q_{idx}", 
                        value=st.session_state.scores[idx], 
                        step=1, 
                        on_change=update_data, 
                        args=(idx,)
                    )
    st.subheader(f"合計点: {sum(st.session_state.scores)}")with st.expander("📝 スコアを入力してね", expanded=True):
    # 15問を3問ずつのセットにしてループを回す
    for i in range(0, 15, 3):
        cols = st.columns(3)
        # 1行（3列）の中に、順番に問を入れていく
        for j in range(3):
            idx = i + j
            if idx < 15:
                with cols[j]:
                    st.number_input(
                        f"問{idx+1}", 
                        key=f"q_{idx}", 
                        value=st.session_state.scores[idx], 
                        step=1, 
                        on_change=update_data, 
                        args=(idx,)
                    )
    st.subheader(f"合計点: {sum(st.session_state.scores)}")
    
st.divider()
st.subheader("🏆 ランキング")

@st.fragment(run_every=5)
def show_ranking():
    try:
        all_data = load_data()
        if all_data.empty: 
            st.info("まだデータがありません。")
            return
        
        # データの整理
        display_df = all_data[['name', 'total']].copy()
        display_df.columns = ['名前', '合計点']
        # 合計点で降順ソートし、インデックスを振り直す（これで row.name が順位になる）
        display_df = display_df.sort_values('合計点', ascending=False).reset_index(drop=True)

        # 1. グラフの表示
        chart = alt.Chart(display_df).mark_bar().encode(
            x=alt.X('合計点:Q', title="スコア"),
            y=alt.Y('名前:N', sort=None, title=None),
            color=alt.Color('合計点:Q', scale=alt.Scale(scheme='oranges'), legend=None)
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)

        # 2. 順位表の表示（ここで style_ranking を適用！）
        # axis=1 は行ごとに処理を行う設定です
        styled_df = display_df.style.apply(style_ranking, axis=1)
        
        st.dataframe(
            styled_df, 
            hide_index=True, 
            use_container_width=True
        )
    except Exception as e:
        # デバッグ用にエラーを表示させる場合は st.error(e) にしてください
        pass


show_ranking()


