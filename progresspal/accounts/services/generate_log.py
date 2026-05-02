import sqlite3
import csv
import os
import sys
from datetime import datetime, timedelta

def generate_user_log(username):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    accounts_dir = os.path.dirname(current_dir)
    project_root = os.path.dirname(accounts_dir)
    
    db_path = os.path.join(project_root, 'db.sqlite3')
    output_filename = os.path.join(project_root, f"{username}_log.csv")
    
    if not os.path.exists(db_path):
        print(f"錯誤: 找不到資料庫檔案 {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. 查詢使用者基本資訊
        user_query = "SELECT id, username, role FROM accounts_customuser WHERE username = ?"
        cursor.execute(user_query, (username,))
        user_data = cursor.fetchone()

        if not user_data:
            print(f"找不到使用者: {username}")
            return

        user_id = user_data['id']
        role_group = user_data['role']

        # 2. 查詢該使用者的所有 LearningRecord
        lr_query = "SELECT chapter_code, unit_code, start_time FROM accounts_learningrecord WHERE user_id = ? ORDER BY start_time ASC"
        cursor.execute(lr_query, (user_id,))
        lr_rows = cursor.fetchall()

        # 3. 查詢該使用者的所有情緒紀錄
        emotion_query = "SELECT timestamp, emotion FROM emotion_emotionrecord WHERE user_id = ? ORDER BY timestamp ASC"
        cursor.execute(emotion_query, (user_id,))
        emotion_rows = cursor.fetchall()
        
        user_emotions = []
        for er in emotion_rows:
            if er['timestamp']:
                try:
                    er_time = datetime.strptime(er['timestamp'].split('.')[0], '%Y-%m-%d %H:%M:%S')
                    user_emotions.append({'time': er_time, 'emotion': er['emotion']})
                except Exception:
                    pass

        # 4. 查詢問答紀錄
        log_query = """
        SELECT 
            ql.chapter_code,
            ql.unit_code,
            ql.created_at as timestamp,
            ql.engagement as engage_level,
            ql.type as action_type,
            ql.stu_input as user_input,
            ql.system_question as extended_question,
            ql.answer as system_reply,
            ql.hint_is_used as hint_is_used
        FROM accounts_questionlog ql
        WHERE ql.user_id = ?
        ORDER BY ql.created_at ASC
        """
        cursor.execute(log_query, (user_id,))
        rows = cursor.fetchall()

        if not rows:
            print(f"使用者 {username} 目前沒有任何問答紀錄。")
            return

        # 5. 準備寫入 CSV (★★★ 這裡調整了欄位順序 ★★★)
        fieldnames = [
            'timestamp', 'student_id', 'role_group', 'chapter_code', 'unit_code', 'emotion', 
            'engage_level', 'action_type', 'user_input', 'system_reply', 'extended_question', 
            'hint_is_used', 'Task_Latency'  
        ]

        with open(output_filename, mode='w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            last_event_time = None

            for row in rows:
                raw_ts = row['timestamp']
                q_time = None
                if raw_ts:
                    try:
                        q_time = datetime.strptime(raw_ts.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass
                
                unit = row['unit_code']
                task_latency = 0.0
                emotion_sequence = []

                if q_time:
                    latest_start_time = None
                    for lr in lr_rows:
                        if lr['unit_code'] == unit:
                            try:
                                lr_time = datetime.strptime(lr['start_time'].split('.')[0], '%Y-%m-%d %H:%M:%S')
                                if lr_time <= q_time:
                                    latest_start_time = lr_time
                            except Exception:
                                pass
                    
                    if latest_start_time:
                        if last_event_time is None or latest_start_time > last_event_time:
                            last_event_time = latest_start_time

                    if last_event_time is None:
                        last_event_time = q_time

                    for em in user_emotions:
                        if last_event_time <= em['time'] <= q_time:
                            emotion_sequence.append(em['emotion'])

                    task_latency = round((q_time - last_event_time).total_seconds(), 2)
                    last_event_time = q_time 

                formatted_ts = raw_ts
                if q_time:
                    local_dt = q_time + timedelta(hours=8)
                    formatted_ts = local_dt.strftime('%Y-%m-%d %H:%M:%S')

                emotion_val = f"[{', '.join(emotion_sequence)}]" if emotion_sequence else "[]"

                # 寫入資料時，雖然字典沒有順序問題，但也順手排整齊方便閱讀
                writer.writerow({
                    'timestamp': formatted_ts,
                    'student_id': username,
                    'role_group': role_group,
                    'chapter_code': row['chapter_code'],
                    'unit_code': row['unit_code'],
                    'emotion': emotion_val,
                    'engage_level': row['engage_level'],
                    'action_type': row['action_type'],
                    'user_input': row['user_input'],
                    'system_reply': row['system_reply'],
                    'extended_question': row['extended_question'] if row['extended_question'] else "Null",
                    'hint_is_used': bool(row['hint_is_used']),
                    'Task_Latency': task_latency
                })

        print(f"✅ 成功生成報表！")
        print(f"檔案位置: {output_filename}")

    except sqlite3.Error as e:
        print(f"資料庫錯誤: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_username = sys.argv[1]
    else:
        try:
            target_username = input("請輸入要匯出 log 的使用者帳號 (username): ").strip()
            if not target_username:
                print("未輸入帳號，程式結束。")
                sys.exit()
        except KeyboardInterrupt:
            print("\n程式已取消。")
            sys.exit()

    generate_user_log(target_username)