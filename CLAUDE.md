# HCI-Slideshow-Interaction

Hệ thống điều khiển slide bằng cử chỉ tay, có cơ chế chống Midas touch (kích hoạt nhầm).
Model GRU được **train ở repo nghiên cứu riêng** `HCI-project` (máy nhóm: `C:\Users\admin\OneDrive\Máy tính\Pacman\HCI-project`). Repo này chỉ **dùng** model, không train.

## Chạy

```powershell
python -m src ui                     # giao diện (mở ở chế độ TẬP, không gửi phím)
python -m src live --send-keys       # gửi phím thật vào PowerPoint
python -m src replay sessions/x.jsonl --policies fixed,abstain
python -m pytest -q --continue-on-collection-errors
```

Chọn bộ nhận diện trong `config.yaml`: `recognizer: hybrid | gru | rule` (`rule` chỉ có tư thế tĩnh, không chuyển slide được).
Random Forest + script thu/train cũ (`03_collect`, `04_train`, `06_hagrid`, `landmark_utils`) và cử chỉ 1–2 ngón đã bị xóa.

## Luồng xử lý (`src/pipeline.py`)

```
CameraSource (lật gương) -> HandTracker -> Observation -> FeatureExtractor -> FeatureWindow
  -> Recognizer -> Hypothesis -> IntentGate (policy) -> Decision -> ActionDispatcher -> phím
```

- `IntentGate`: IDLE -> (nắm tay giữ `arm_hold_ms`) ARMED -> COMMAND (giữ `hold_ms`) -> EXECUTE -> COOLDOWN.
  Thumb up (`like`) = `start_show` (Shift+F5), thumb down (`dislike`) = `exit_show` (Esc), ánh xạ ở `datatypes.POSE_COMMANDS`; giữ `command_hold_ms` (600),
  phải bỏ tư thế ra mới nhận lại (không lặp khi giữ tay). CONFIRM còn trong code nhưng `confirm_commands: []`. Cử chỉ 3 ngón đã bỏ.
  Mọi policy trừ `naive` và `swipe` đều bắt buộc ARM.
- Policy (`src/decision/policies.py`): naive | fixed | adaptive (khắt khe hơn khi tay nhanh) | abstain (UNCERTAIN khi margin thấp) | combined.
- **Mặc định `policy: swipe`**: không cần ARM, gate đang để lỏng theo yêu cầu: `conf` 0.7, `gru_override` 0.7, `swipe_hold_ms` 0 (đỉnh GRU chỉ dài ~300 ms), `cooldown_ms` 800,
  `reverse_block_ms` 2500 (bỏ qua vuốt chiều ngược sau một cú vuốt: nhịp đưa tay về bị GRU đọc thành lệnh ngược). Nhảy slide bừa -> tăng `conf`/`gru_override`. Pipeline reset GRU
  sau mỗi lệnh nên một cú vuốt không bị đếm 2 lần. `disabled_commands: [play_pause]` vì mở bàn tay -> Space -> PowerPoint sang slide khi đang nói.
  `command_hold_ms` áp dụng cho `swipe` và các policy có ARM (không áp dụng cho `naive`).

## GRU / Hybrid (`src/perception/gru_recognizer.py`)

- **hybrid** (hướng nhóm chọn): GRU nhận **vuốt** phải = `next`, vuốt trái = `previous`; luật hình học (`RuleRecognizer`) nhận
  tư thế tĩnh `arm`, `play_pause`, `like`, `dislike`. Không còn mẫu next/previous tĩnh trong `RULE_TEMPLATES`.
  GRU thắng khi `p >= gru_override`; tay nhanh hơn `static_max_speed` thì không nhận tư thế lệnh tĩnh (tránh vuốt bàn tay mở bị đọc thành play_pause).
- Zoom (`zoom_in/zoom_out`) **tạm bỏ**: xác suất gộp vào `none`.
- Model nằm ở `models/gru/`: `gru.keras`, `gru.labels.json`, `gru.meta.json`. Cập nhật model = copy 3 file từ `HCI-project/models/`.
  `meta.json` quyết định `sequence_length` và `step_ms` — **không đặt cứng trong code**.

### Bất biến bắt buộc (sai là model chạy sai mà không báo lỗi)

1. Tiền xử lý giống hệt `HCI-project/src/sequence_utils.py`: 63 tọa độ ảnh **thô** (không chuẩn hóa, không làm mượt) + 7 motion so với bước trước;
   không thấy tay -> 0, motion = 0 khi bước này hoặc bước trước không có tay; cửa sổ đệm 0 bên trái.
   Vì vậy `FeatureWindow.landmarks` mang tọa độ thô; đừng đưa `FeatureWindow.vector` (đã chuẩn hóa + trung bình) vào GRU.
2. Lấy mẫu theo **thời gian** (`step_ms`), không theo số khung camera.
3. `gru_flip_x: true`: CameraSource lật gương còn ảnh Jester thì không (Jester "Swiping Left" có dx > 0). Tắt cờ này là next/previous bị đảo.
4. `tests/fixtures/gru_parity.json` sinh từ code + model của repo nghiên cứu. Đổi tiền xử lý hoặc model -> sinh lại fixture
   rồi chạy `tests/test_gru_recognizer.py`.
5. `Pipeline` gọi `recognizer.reset()` lúc ACCEPT và ở mọi khung COOLDOWN: cửa sổ GRU (~2.7 s) dài hơn cooldown, không xóa thì
   phần đuôi của chính cú vuốt vừa thực hiện bị nhận lại thành lệnh thứ hai.
6. Model chạy qua `tf.function` (graph, shape cố định): ~3 ms/lần. Gọi eager `keras_model(x)` mất ~180 ms/lần, làm khựng camera.

## Tình trạng đã biết

- Có sẵn 17 test fail (từ trước khi tích hợp GRU): `tests/helpers.make_hand` unpack sai `THUMBS` (4 điểm, code mong 2 giá trị),
  một số test mong nhãn `none` trong probs, và vài test vẫn dựng next/previous bằng tư thế 1–2 ngón (đã bỏ). `test_gru_recognizer.py` dùng helper riêng.
- Model GRU hiện tại (v1, `models/gru/`): train trên CSV Jester theo frame (58k video, 6 fps, `step_ms` 166.7), accuracy 92.2% offline
  (F1 next 0.88, previous 0.88, none 0.94). Bản cũ v0 (1 dòng/video, 81%) đã xóa khỏi repo này; còn backup ở `HCI-project/models/v0_video_level/`.
- Mô phỏng offline với cấu hình hệ thống (chỉ next/previous, conf 0.8, giữ 200 ms, cooldown 2 s): vuốt đúng 82.5%, nhưng 16.6% cú vuốt
  có thêm lệnh NGƯỢC CHIỀU, phần lớn bắn TRƯỚC lệnh đúng (đoạn lấy đà) rồi cooldown chặn luôn lệnh đúng. Tăng `swipe_hold_ms` lên 350–500
  và/hoặc `conf` 0.9 giảm còn 4–12% (xem bảng trong `HCI-project/reports/frames/`). Cần kiểm chứng bằng session webcam thật.
- TensorFlow chỉ được import khi `recognizer` là `gru`/`hybrid`.
