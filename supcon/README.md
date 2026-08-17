# 中控杯赛题 2 · 算法服务工程

> 中控杯智能制造挑战赛赛题 2「工业多模态感知与无人化智能操作」的 Task1、Task2、Task3。
> 硬件：FTArm 580-B9 机械臂（HTTP/WS :8087）+ O10 灵巧手（HTTP/WS :8088）+ Gemini 335 相机（eye-in-hand）。
> 语言：Python 3.10+。**不需要 VLA / 大模型**，全部是确定性管线。

## 快速开始

```bash
cd supcon_task2
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
supcon_task2/
├── config/                  # 配置、模板与现场标定文件
│   ├── config.yaml          # ★ 所有可调参数
│   ├── templates/           # 可提交的 Task1/2/3 标定模板
│   └── runtime/             # 本机现场标定（默认不纳入版本管理）
├── docs/                    # 上机与总调试手册
├── mocks/                   # 模拟机械臂 / 灵巧手（无硬件开发用）
├── runtime/logs/            # 运行日志
├── scripts/                 # 上机操作脚本（标定/示教/自测/启动）
├── src/supcon_task2/        # Python 包（算法服务核心）
│   ├── config.py            # 配置加载（默认值 + YAML 覆盖）
│   ├── utils.py             # 日志、姿态矩阵工具
│   ├── robot/               # 臂 / 手 / 安全监控客户端
│   ├── vision/              # 相机、亮灯、数字、形状与手眼标定
│   ├── tasks/               # Task1 拨按、Task2 顶面数字、Task3 竖直分拣
│   └── service.py           # FastAPI 服务（对接竞赛软件）
├── tests/                   # 单测 + 离线冒烟
└── requirements.txt
```

## 核心设计（为什么这样做）

1. **Task1 视觉只回答「哪盏灯亮」**：面板固定，3 盏灯在图像中的位置预先标定（`panel.json`），运行时用多帧 ROI 亮度增量判定，不需要训练模型。
2. **动作位置全靠示教**：开关的「按压/拨动」位姿在真机上用网页控制面板拖动 + `scripts/02_record_pose.py` 记录。**Task1 不需要手眼标定**，把 3D 坐标转换问题彻底绕开（新手最稳路线）。
3. **先预览后执行、全程直线**：每个位姿 `plan_only` 校验可达性，执行后检查 message 是否含 `OMPL`（回退非直线 = 危险）。
4. **安全兜底**：后台监控线程持续查臂电机故障与手过流，任何异常立即停止后续动作。
5. **离线可开发**：mock 臂/手 + 模拟相机，全流程可以零硬件跑通后再上机。
