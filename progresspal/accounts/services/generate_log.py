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

        # 2. 查詢該使用者的所有 LearningRecord (作為每個單元的閱讀起點)
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

        # 5. 準備寫入 CSV
        fieldnames = [
            'timestamp', 'student_id', 'role_group', 'chapter_code', 'unit_code', 'emotion', 
            'engage_level', 'CRT_Sequence', 'Total_Struggle_Time', 
            'action_type', 'user_input', 'system_reply', 'extended_question',
            'hint_is_used', 'Task_Latency'
        ]

        with open(output_filename, mode='w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            last_event_time = None
            current_unit = None

            for row in rows:
                raw_ts = row['timestamp']
                q_time = None
                if raw_ts:
                    try:
                        q_time = datetime.strptime(raw_ts.split('.')[0], '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        continue
                
                unit = row['unit_code']
                task_latency = 0.0
                interval_emotions = []

                # 如果進入了不同的單元，重置上一個事件時間，讓程式重新去抓學習紀錄起點
                if unit != current_unit:
                    last_event_time = None
                    current_unit = unit

                if q_time:
                    # 尋找這個單元最近一次的閱讀開始時間
                    latest_start_time = None
                    for lr in lr_rows:
                        if lr['unit_code'] == unit:
                            try:
                                lr_time = datetime.strptime(lr['start_time'].split('.')[0], '%Y-%m-%d %H:%M:%S')
                                if lr_time <= q_time:
                                    latest_start_time = lr_time
                            except Exception:
                                pass
                    
                    # 決定這個任務的起點時間 (last_event_time)
                    if latest_start_time:
                        if last_event_time is None or latest_start_time > last_event_time:
                            # 這是該單元的第一題，或學生重新整理/離開後再次進入單元
                            last_event_time = latest_start_time

                    # 如果完全找不到學習紀錄(極端情況防呆)，就以提問當下為起點
                    if last_event_time is None:
                        last_event_time = q_time

                    # 過濾出該任務時間區間內的情緒紀錄
                    for em in user_emotions:
                        # 擷取時間範圍：上個任務結尾時間 <= 發生時間 <= 本次提問時間
                        if last_event_time <= em['time'] <= q_time:
                            interval_emotions.append(em)

                    # 計算 Task_Latency
                    task_latency = round((q_time - last_event_time).total_seconds(), 2)
                    
                    # === 任務結束：將本次提問時間設為下一個任務的起點 ===
                    last_event_time = q_time 

                # === 開始計算 CRT_Sequence 與 Total_Struggle_Time ===
                crt_sequence = []
                in_confusion = False
                confusion_start_time = None
                
                first_engagement_time = None
                last_confusion_time = None

                for em in interval_emotions:
                    current_emotion = em['emotion']
                    current_time = em['time']

                    # 紀錄 Total_Struggle_Time 需要的兩個端點
                    if current_emotion == 'engagement' and first_engagement_time is None:
                        first_engagement_time = current_time
                    if current_emotion == 'confusion':
                        last_confusion_time = current_time

                    # 計算 CRT_Sequence (從困惑到投入的轉變)
                    if current_emotion == 'confusion' and not in_confusion:
                        in_confusion = True
                        confusion_start_time = current_time
                    elif current_emotion == 'engagement' and in_confusion:
                        crt = (current_time - confusion_start_time).total_seconds()
                        crt_sequence.append(int(crt))
                        in_confusion = False

                # 計算 Total Struggle Time
                total_struggle_time = 0.0
                if first_engagement_time and last_confusion_time and (last_confusion_time > first_engagement_time):
                    total_struggle_time = (last_confusion_time - first_engagement_time).total_seconds()

                # === 格式轉換與寫入 ===

                formatted_ts = raw_ts
                if q_time:
                    local_dt = q_time + timedelta(hours=8)
                    formatted_ts = local_dt.strftime('%Y-%m-%d %H:%M:%S')

                emotion_str_list = [em['emotion'] for em in interval_emotions]
                emotion_val = f"[{', '.join(emotion_str_list)}]" if emotion_str_list else "[]"
                crt_val = f"[{', '.join(map(str, crt_sequence))}]"

                writer.writerow({
                    'timestamp': formatted_ts,
                    'student_id': username,
                    'role_group': role_group,
                    'chapter_code': row['chapter_code'],
                    'unit_code': row['unit_code'],
                    'emotion': emotion_val,
                    'engage_level': row['engage_level'],
                    'CRT_Sequence': crt_val,
                    'Total_Struggle_Time': round(total_struggle_time, 2),
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