#六種學習情緒對應參與度分數
EMOTION_TO_ENGAGEMENT = {
  "喜悅": 1.0,
  "投入": 1.0,
  "驚訝": 1.0,
  "無聊": 0.0,
  "挫折": 0.0,
}

#正面/負向情緒
POSITIVE = {"喜悅", "投入", "驚訝"}
NEGATIVE = {"無聊", "挫折"}

#情緒字串轉成對應的參與度分數
def map_emotion_to_score(emotion):
  scores = []
  n = len(emotion)
  #遍歷每個情緒
  for i, e in enumerate(emotion):
    #困惑情緒處理
    if e == "困惑":
      if i + 1 < n: #有下一個情緒
        next_e = emotion[i + 1]
        if next_e in POSITIVE: #後續為正向
          scores.append(1.0) #分數設為1.0
        elif next_e in NEGATIVE: #後續為負向
          scores.append(0.0) #分數設為0.0
        else: #後續為困惑
          scores.append(0.5) #分數設為0.5
      else: #最後一個為困惑
        scores.append(0.5) #設為0.5
    else:
      if e not in EMOTION_TO_ENGAGEMENT:
          # 遇到 "未知"、"None" 或其他未知情緒時，不再報錯，而是給予預設的 0.5 分 (中性)
          scores.append(0.5)
      else:
          scores.append(EMOTION_TO_ENGAGEMENT[e])
  return scores

#輸入情緒序列，回傳參與度分數
def compute_engagement(emotions):
  """
  "ema" (指數平滑法)：即時追蹤學習狀態，快速反應「最近」的情緒
  """
  #一開始進入系統
  if emotions == ["None"]:
    return "high"

  #空序列
  if not emotions:
    return "high"

  #情緒字串轉成數值分數
  scores = map_emotion_to_score(emotions)

  #平均分數法
  #if method == "mean":
    #return sum(scores) / len(scores)

  #指數平滑法
  alpha = 0.2  #越大越重視最近的情緒
  ema = scores[0]
  for x in scores[1:]:
    ema = alpha * x + (1 - alpha) * ema

  if ema >= 0.5:
    return "high"
  else:
    return "low"


# ===== 統一的參與度狀態（docs/SPEC_實驗資料與部署.md R6）=====
# 情緒辨識 API、主動介入判斷、送給 LLM 的參與度都使用這裡的結果，並存入 EmotionRecord。
CONFIDENCE_THRESHOLD = 0.5  # 信心度低於此值的樣本不列入參與度計算（與前端 camera.js 一致）
ENGAGEMENT_WINDOW = 10      # 以最近 10 筆有效樣本計算參與度


def update_engagement_state(record):
  """
  計算並存入一筆 EmotionRecord 的 low_confidence、engagement、low_streak。
  - 低信心樣本：engagement 留空，low_streak 沿用前一筆有效樣本（不增加也不中斷）
  - 有效樣本：以最近 ENGAGEMENT_WINDOW 筆有效樣本（含本筆）計算參與度；
    low 時 low_streak = 前一筆有效樣本的 low_streak + 1，high 時歸零
  """
  from emotion.models import EmotionRecord

  labels = dict(EmotionRecord.EMOTION_CHOICES)  # 英文代碼 → 中文
  previous_valid = (EmotionRecord.objects
                    .filter(user=record.user, low_confidence=False, timestamp__lte=record.timestamp)
                    .exclude(pk=record.pk)
                    .order_by("-timestamp", "-pk")
                    .first())
  record.low_confidence = record.confidence < CONFIDENCE_THRESHOLD

  if record.low_confidence:
    record.engagement = None
    record.low_streak = previous_valid.low_streak if previous_valid else 0
  else:
    window = list(EmotionRecord.objects
                  .filter(user=record.user, low_confidence=False, timestamp__lte=record.timestamp)
                  .exclude(pk=record.pk)
                  .order_by("-timestamp", "-pk")[:ENGAGEMENT_WINDOW - 1])
    emotions = [labels.get(r.emotion, "未知") for r in reversed(window)] + [labels.get(record.emotion, "未知")]
    record.engagement = compute_engagement(emotions)
    if record.engagement == "low":
      record.low_streak = (previous_valid.low_streak if previous_valid else 0) + 1
    else:
      record.low_streak = 0

  record.save(update_fields=["low_confidence", "engagement", "low_streak"])
  return record


def current_engagement(user):
  """使用者目前的參與度：最新一筆有效樣本的 engagement；尚無樣本時為 high（與原本預設一致）"""
  from emotion.models import EmotionRecord

  latest = (EmotionRecord.objects
            .filter(user=user, low_confidence=False, engagement__isnull=False)
            .order_by("-timestamp", "-pk")
            .first())
  return latest.engagement if latest else "high"
