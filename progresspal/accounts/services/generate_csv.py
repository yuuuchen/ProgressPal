import sqlite3
import csv
import os
from datetime import datetime, timedelta
from django.conf import settings

def generate_user_csv_reports(username, system_type="control"):
    """
    負責從資料庫撈取特定使用者的學習與情緒紀錄，並生成三份 CSV 報表。
    回傳格式: dict 包含 status, message, files(若成功)
    """
    db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
    
    # 1. 根據使用者名稱動態定義資料夾路徑 (格式: username_data)
    data_dir = os.path.join(settings.BASE_DIR, f'{username}_data')
    
    # 若該使用者的資料夾不存在，則自動建立
    os.makedirs(data_dir, exist_ok=True)
    
    # 將檔案路徑指向該專屬資料夾內部
    log_filename = os.path.join(data_dir, f"{username}_log.csv")
    emotion_filename = os.path.join(data_dir, f"{username}_emotion.csv")
    duration_filename = os.path.join(data_dir, f"{username}_duration.csv")

    if not os.path.exists(db_path):
        return {'status': 'error', 'message': f'找不到資料庫檔案 {db_path}'}

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. 查詢使用者基本資訊
        user_query = "SELECT id, username, role FROM accounts_customuser WHERE username = ?"
        cursor.execute(user_query, (username,))
        user_data = cursor.fetchone()

        if not user_data:
            return {'status': 'error', 'message': f'找不到使用者: {username}'}

        user_id = user_data['id']
        role_group = user_data['role']

        # ==========================================
        # 準備查詢各資料表的 Raw Data
        # ==========================================
        lr_query = "SELECT chapter_code, unit_code, start_time, end_time FROM accounts_learningrecord WHERE user_id = ? ORDER BY start_time ASC"
        cursor.execute(lr_query, (user_id,))
        lr_rows = cursor.fetchall()

        emotion_query = "SELECT timestamp, emotion FROM emotion_emotionrecord WHERE user_id = ? ORDER BY timestamp ASC"
        cursor.execute(emotion_query, (user_id,))
        emotion_rows = cursor.fetchall()

        log_query = """
        SELECT 
            ql.chapter_code, ql.unit_code, ql.created_at as timestamp, 
            ql.engagement as engage_level, ql.type as action_type, 
            ql.stu_input as user_input, ql.system_question as extended_question, 
            ql.answer as system_reply, ql.hint_is_used as hint_is_used, 
            ql.click_time as click_time
        FROM accounts_questionlog ql
        WHERE ql.user_id = ?
        ORDER BY ql.created_at ASC
        """
        cursor.execute(log_query, (user_id,))
        question_rows = cursor.fetchall()

        # ==========================================
        # 產出 1: Emotion CSV
        # ==========================================
        emotion_fieldnames = ['system_type', 'username', 'chapter_code', 'unit_code', 'timestamp', 'emotion']
        with open(emotion_filename, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=emotion_fieldnames)
            writer.writeheader()
            
            for er in emotion_rows:
                raw_ts = er['timestamp']
                formatted_ts = raw_ts
                mapped_chapter = "Null"
                mapped_unit = "Null"

                if raw_ts:
                    try:
                        er_time = datetime.strptime(raw_ts.split('.')[0], '%Y-%m-%d %H:%M:%S')
                        
                        for lr in lr_rows:
                            if lr['start_time'] and lr['end_time']:
                                try:
                                    lr_st = datetime.strptime(lr['start_time'].split('.')[0], '%Y-%m-%d %H:%M:%S')
                                    lr_et = datetime.strptime(lr['end_time'].split('.')[0], '%Y-%m-%d %H:%M:%S')
                                    if lr_st <= er_time <= lr_et:
                                        mapped_chapter = lr['chapter_code']
                                        mapped_unit = lr['unit_code']
                                        break  
                                except Exception:
                                    continue

                        formatted_ts = (er_time + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass

                writer.writerow({
                    'system_type': system_type,
                    'username': username,
                    'chapter_code': mapped_chapter,
                    'unit_code': mapped_unit,
                    'timestamp': formatted_ts,
                    'emotion': er['emotion']
                })

        # ==========================================
        # 產出 2: Duration CSV
        # ==========================================
        duration_fieldnames = ['system_type', 'username', 'chapter_code', 'unit_code', 'duration_seconds']
        with open(duration_filename, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=duration_fieldnames)
            writer.writeheader()
            for lr in lr_rows:
                duration_sec = 0.0
                start_str = lr['start_time']
                end_str = lr['end_time']
                
                if start_str and end_str:
                    try:
                        st = datetime.strptime(start_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                        et = datetime.strptime(end_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                        duration_sec = round((et - st).total_seconds(), 2)
                    except Exception:
                        pass
                
                writer.writerow({
                    'system_type': system_type,
                    'username': username,
                    'chapter_code': lr['chapter_code'],
                    'unit_code': lr['unit_code'],
                    'duration_seconds': duration_sec
                })

        # ==========================================
        # 產出 3: Log CSV
        # ==========================================
        user_emotions = []
        for er in emotion_rows:
            if er['timestamp']:
                try:
                    er_time = datetime.strptime(er['timestamp'].split('.')[0], '%Y-%m-%d %H:%M:%S')
                    user_emotions.append({'time': er_time, 'emotion': er['emotion']})
                except Exception:
                    pass

        log_fieldnames = [
            'timestamp', 'student_id', 'role_group', 'system_type', 'chapter_code', 'unit_code', 'emotion', 
            'engage_level', 'CRT_Sequence', 'Total_Struggle_Time', 'action_type', 'user_input', 
            'system_reply', 'extended_question', 'hint_is_used', 'click_time', 'Task_Latency'
        ]

        with open(log_filename, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=log_fieldnames)
            writer.writeheader()

            last_event_time = None
            current_unit = None

            for row in question_rows:
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

                if unit != current_unit:
                    last_event_time = None
                    current_unit = unit

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
                            interval_emotions.append(em)

                    task_latency = round((q_time - last_event_time).total_seconds(), 2)
                    last_event_time = q_time 

                crt_sequence = []
                in_confusion = False
                confusion_start_time = None
                first_engagement_time = None
                last_confusion_time = None

                for em in interval_emotions:
                    current_emotion = em['emotion']
                    current_time = em['time']

                    if current_emotion == 'engagement' and first_engagement_time is None:
                        first_engagement_time = current_time
                    if current_emotion == 'confusion':
                        last_confusion_time = current_time

                    if current_emotion == 'confusion' and not in_confusion:
                        in_confusion = True
                        confusion_start_time = current_time
                    elif current_emotion == 'engagement' and in_confusion:
                        crt = (current_time - confusion_start_time).total_seconds()
                        crt_sequence.append(int(crt))
                        in_confusion = False

                total_struggle_time = 0.0
                if first_engagement_time and last_confusion_time and (last_confusion_time > first_engagement_time):
                    total_struggle_time = (last_confusion_time - first_engagement_time).total_seconds()

                formatted_ts = raw_ts
                if q_time:
                    local_dt = q_time + timedelta(hours=8)
                    formatted_ts = local_dt.strftime('%Y-%m-%d %H:%M:%S')

                raw_click_time = row['click_time']
                formatted_click_time = "Null"
                if raw_click_time:
                    try:
                        ct_time = datetime.strptime(raw_click_time.split('.')[0], '%Y-%m-%d %H:%M:%S')
                        local_ct = ct_time + timedelta(hours=8)
                        formatted_click_time = local_ct.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        formatted_click_time = raw_click_time

                emotion_str_list = [em['emotion'] for em in interval_emotions]
                emotion_val = f"[{', '.join(emotion_str_list)}]" if emotion_str_list else "[]"
                crt_val = f"[{', '.join(map(str, crt_sequence))}]"

                writer.writerow({
                    'timestamp': formatted_ts,
                    'student_id': username,
                    'role_group': role_group,
                    'system_type': system_type,
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
                    'click_time': formatted_click_time,
                    'Task_Latency': task_latency
                })

        # 2. 更新回傳的檔案名稱，加上 username_data/ 前綴，讓前端顯示更精確
        return {
            'status': 'success', 
            'files': [
                f"{username}_data/{username}_log.csv", 
                f"{username}_data/{username}_emotion.csv", 
                f"{username}_data/{username}_duration.csv"
            ]
        }

    except sqlite3.Error as e:
        return {'status': 'error', 'message': f'資料庫錯誤: {e}'}
    finally:
        if conn:
            conn.close()