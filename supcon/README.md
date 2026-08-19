# 中控杯赛题 2 · 算法服务工程

> 中控杯智能制造挑战赛赛题 2「工业多模态感知与无人化智能操作」的 Task1、Task2、Task3。
> 硬件：FTArm 580-B9 机械臂（HTTP/WS :8087）+ O10 灵巧手（HTTP/WS :8088）+ Gemini 335 相机（eye-in-hand）。
> 语言：Python 3.10+。**不需要 VLA / 大模型**，全部是确定性管线。

## 快速开始

```bash
cd supcon
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# ① 离线冒烟测试（不需要任何硬件，验证全流程代码能跑通）
python tests/smoke_mock.py

# ② 无真机联调：起两个 mock 服务 + 算法服务
python mocks/mock_arm.py --port 8087 &
python mocks/mock_hand.py --port 8088 &
python scripts/06_serve.py
curl http://127.0.0.1:5000/api/health
curl -X POST http://127.0.0.1:5000/api/task1/execute

# ③ 真机：Task1 按 docs/TASK1_GUIDE.md，Task2/3 按 docs/TASK23_GUIDE.md 标定
```

## 目录结构

```
supcon/
├── config/                  # 配置、模板与现场标定文件
│   ├── config.yaml          # ★ 所有可调参数
│   ├── templates/           # 可提交的 Task1/2/3 标定模板
│   └── runtime/             # 本机现场标定（默认不纳入版本管理）
├── docs/                    # 上机与总调试手册
├── mocks/                   # 模拟机械臂 / 灵巧手（无硬件开发用）
├── runtime/logs/            # 运行日志
├── scripts/                 # 上机操作脚本（标定/示教/自测/启动）
├── src/supcon/              # Python 包（算法服务核心）
│   ├── config.py            # 配置加载（默认值 + YAML 覆盖）
│   ├── utils.py             # 日志、姿态矩阵工具
│   ├── robot/               # 臂 / 手 / 安全监控客户端
│   ├── vision/              # 相机、亮灯、数字、形状与手眼标定
│   ├── tasks/               # Task1 拨按、Task2 顶面数字、Task3 竖直分拣
│   └── service.py           # FastAPI 服务（对接竞赛软件）
├── test_utils/              # 视觉算法离线测试（test_color/test_ocr/test_shape）
├── tests/                   # 单测 + 离线冒烟
└── requirements.txt
```

## 核心设计（为什么这样做）

1. **Task1 视觉只回答「哪盏灯亮」**：面板固定，3 盏灯在图像中的位置预先标定（`panel.json`）。白底面板用**做差标定**（`03_calibrate_panel.py --mode diff`：全灭基准帧 + 亮灯帧做差聚出 3 个灯位，并写入 ROI 亮度基线），运行时用「ROI 亮度 − 基线」增量判定，不需要模型、不需要手眼标定。
2. **示教与视觉各司其职**：开关的「按压/拨动」位姿在真机上用网页控制面板拖动 + `scripts/02_record_pose.py` 记录；Task2 抓放位姿用 `scripts/08/09/10_record_*.py` 记录。Task3 只示教全局观察位、目标槽位和手型，源物体 XY 由 RGB-D + 手眼标定在运行时计算。
3. **Task2 整图 OCR**：观察位拍一张顶视图整图送入 PaddleOCR，按文本框 x 坐标左→右读出 4 个数字，依次映射到 `left/midleft/midright/right`，再严格按 `1→2→3→4` 抓取放置（无需 ROI/数字模板）。
4. **Task3 形状分拣**：Gemini335 同帧对齐 RGB-D 做桌面平面分割、顶面轮廓分类；经 `T_eef_camera` / `T_eef_tcp` 变换生成抓取位，并在预抓高度复拍校正，竖直抓放、不做空中翻转。
5. **先预览后执行、全程直线**：每个位姿 `plan_only` 校验可达性，执行后检查 message 是否含 `OMPL`（回退非直线 = 危险）。
6. **安全兜底**：后台监控线程持续查臂电机故障与手过流，任何异常立即停止后续动作；可选力矩绝对值上限急停（`--effort-guard`）。
7. **离线可开发**：mock 臂/手 + 模拟相机，全流程可以零硬件跑通后再上机；`debug.dump_enabled` 可把任务执行时相机帧/深度图落盘到 `runtime/debug/` 与 `img_vis/` 排查。
