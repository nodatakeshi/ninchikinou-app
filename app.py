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

total_question = 16


#認証部分
def get_gspread_client():
    """環境に合わせて認証情報を取得する"""
    # 1.colab環境（ファイルがある場合で識別。Streamlitはcolabシークレットキーは読めないのでdriveから読む）
    if os.path.exists('/content/drive/MyDrive/ninchi-kinou-c879e034df64.json'):
        with open('/content/drive/MyDrive/ninchi-kinou-c879e034df64.json', 'r') as f:
          creds_dict = json.load(f)
    # 2. 公開環境（Streamlit CloudのSecretsを使う場合）
    else:
        creds_dict = st.secrets["connections"]["gsheets"]

    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(credentials)

#googleスプレッドシートのアドレス
SPREADSHEET_ID = "1xw5ilkQdxqUoOQ_Nohi16nF_WlcMElb8J8LF_4vrU9s"#google driveの認知点数表のURLのID部分
WORKSHEET_NAME = "Sheet1"


#googleスプレッドシートからデータ読み込み


def load_data():
    client = get_gspread_client()
    sh = client.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet(WORKSHEET_NAME)
    return pd.DataFrame(worksheet.get_all_records())

#googleスプレッドシートにデータ保存
def save_to_sheets():
    try:
        df = load_data()
        user_name = st.session_state.user_name
        # 保存用の新しいデータを作成
        new_row = {"name": user_name, "total": sum(st.session_state.scores)}
        for i, s in enumerate(st.session_state.scores):
            new_row[f"q{i+1}"] = s

        #書き込むユーザー以外の情報を消す。シートがカラのときは消せないのでスキップ
        if not df.empty:
          df = df[df["name"] != user_name].copy()
        
        
        #保存用データのデータを下にくっつけて、新しく作りなおし。これはシートがカラでも新しく作ってくれる。
        updated_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        client = get_gspread_client()
        worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
        #一旦シートをクリア
        worksheet.clear()
        #表の「見出し（name, total, q1...）」を２次元リストに、値は最初から２次元
        worksheet.update([updated_df.columns.values.tolist()] + updated_df.values.tolist())
    except Exception as e:
        st.error(f"保存に失敗しました: {e}")

def update_data(index):
    st.session_state.scores[index] = st.session_state[f"q_{index}"]
    save_to_sheets()

def style_ranking(row):
    color = ''
    if row.name == 0:    # 1位　金
        color = 'background-color: #ffd700; color: black; font-weight: bold;'
    elif row.name == 1:  # 2位　銀
        color = 'background-color: #c0c0c0; color: black; font-weight: bold;'
    elif row.name == 2:  # 3位　銅
        color = 'background-color: #cd7f32; color: white; font-weight: bold;'
    return [color] * len(row)


if 'user_name' not in st.session_state:
    st.session_state.user_name = ""

if not st.session_state.user_name:
    name = st.text_input("あなたの名前を入力してください")
    #名前が入力されたら
    if name:
        #名前を保持
        st.session_state.user_name = name
        try:
            #データロード
            df = load_data()
            #名前があるか確認
            user_data = df[df["name"] == name]
            if not user_data.empty:
                # すでに名前があれば点数を取得
                row = user_data.iloc[0]
                st.session_state.scores = [int(row[f"q{i+1}"]) for i in range(total_question)]
            else:
                #新しい名前なら全部0点で初期化
                st.session_state.scores = [0] * total_question
        except:
            st.session_state.scores = [0] * total_question
        st.rerun()
    #名前が入力されなかったら最初に戻る
    st.stop()

st.write(f"こんにちは、**{st.session_state.user_name}** さん！")


#折り畳み式のスコアを作成してそのなかで作業する
with st.expander("📝 スコアを入力してね", expanded=True):
    # 3問ずつのセットにしてループを回す
    for i in range(0, total_question, 3):
        #画面を横に3分割するエリアを作ります
        cols = st.columns(3)
        # 1行（3列）の中に、順番に問を入れていく
        for j in range(3):
            idx = i + j
            if idx < total_question:
                with cols[j]:#今から実行する st.number_inputはcols[j] の中で作成しろという意味
                    st.number_input(
                        f"問{idx+1}", 
                        key=f"q_{idx}", #st.session_state["q_0"]でデータアクセスできる(update_dataの中で使う)
                        value=st.session_state.scores[idx], 
                        step=1, 
                        on_change=update_data, 
                        args=(idx,)#updateに渡す、引数。タプルで書くので,が必要
                    )
    st.subheader(f"合計点: {sum(st.session_state.scores)}")

st.divider()#水平の区切り線
st.subheader("🏆 ランキング")

@st.fragment(run_every=10)
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

        # 「順位」列を追加（インデックスは0から始まるので +1 する）
        display_df['順位'] = (display_df.index + 1).astype(str) + "位"
        #列の順番を整える（順位を一番左に持ってくる）
        display_df = display_df[['順位', '名前', '合計点']]

        # グラフの表示
        chart = alt.Chart(display_df).mark_bar().encode(
            x=alt.X('合計点:Q', title="スコア"),
            y=alt.Y('名前:N', sort=None, title=None),
            color=alt.Color('合計点:Q', scale=alt.Scale(scheme='oranges'), legend=None)
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)

        # 順位表の表示（ここで style_ranking を適用！）axis=1 は行ごとに処理を行う設定
        styled_df = display_df.style.apply(style_ranking, axis=1)
        st.dataframe(styled_df, hide_index=True, use_container_width=True)
    except Exception as e:
        # デバッグ用にエラーを表示させる場合は st.error(e) にしてください
        pass


show_ranking()
