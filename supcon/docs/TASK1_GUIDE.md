# Task1 上机指南（按顺序执行）

> 目标：竞赛软件点一次「调用算法操作」，你的服务让机械臂+灵巧手完成一次「亮灯下方开关的点按/拨动」。共 3 次调用，每次独立。
> 评分：每个开关 30 分 ×3 = 90 分 + 设备保护 10 分（磕碰一次 -3，撞坏判失败）。

---

## 0. 总体思路（先理解再动手）

1. **视觉只回答一个问题：「哪盏灯亮」**。面板固定，3 盏灯在图像中的位置预先标定存进 `config.yaml` 的 `task1.panel`；运行时连续多帧比较 ROI 亮度（可选使用三灯熄灭基线），不需要模型、不需要手眼标定。
2. **动作位置全靠示教**。开关的「上方/压到底/拨动起止」位姿，在真机上手动摆好 → 记录末端位姿存进 `task1.panel`。这是新手最稳的路线：视觉不参与 3D 坐标计算。
3. **每步都走直线 + 低速**。先 `plan_only` 预览可达性，执行后检查 message 是否含 `OMPL`（含 = 回退成自由路径，危险）。
4. **后台安全监控常开**：手过流、臂明确 `fault` 立即停后续动作；HTTP 反馈年龄异常须持续超过配置阈值且连续确认，避免运动期间假急停。

## 1. 环境准备

```bash
cd supcon
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# 真机相机还需：pip install pyorbbecsdk（版本与 Python 匹配）
```

## 2. 无硬件先跑通（强烈建议）

```bash
python tests/test_lamp.py        # 亮灯检测单测
python tests/smoke_mock.py       # 全流程冒烟（mock 臂/手 + 模拟相机）
```

冒烟通过说明：接口契约、任务状态机、检测逻辑代码层面都没问题，剩下的全是真机标定工作。

## 3. 真机流程（上机后按这个顺序做）

### 3.1 连通性检查
- 浏览器打开 `http://<臂IP>:8087/`（网页控制面板）与 `http://<手IP>:8088/`，确认两个服务都在；
- `curl http://<臂IP>:8087/api/motors`：`fault=0、has_feedback=1`；
- `curl http://<手IP>:8088/api/status`：`connected=true`。

### 3.2 手型语义实测（⚠️ 第一件事）
```bash
python scripts/01_hand_semantics.py
```
看输出里 `value=1` 时指关节靠近上界还是下界，据此修改 `config.yaml` 的 `hand.open_pose / close_pose / point_pose`。**不测就动手 = 可能张握完全反向。**

### 3.3 标定观察位与安全位（09 脚本，只写待核验文件）
1. 用网页控制面板把臂摆到「能清楚拍全 3 盏灯」的位置 → 记录观察位：
   `python scripts/09_record_arm_pose.py --task 1 --key observe_pose`
2. 再摆一个「远离面板、绝对安全」的休息位 → 记录安全位：
   `python scripts/09_record_arm_pose.py --task 1 --key safe_pose`
3. 肉眼审核 `check_pos/机械臂_安全位观察位_待核验.json` 后，手动填入 `config.yaml` 的 `arm.observe_pose` / `arm.task1_safe_pose`。
   （提示：观察位尽量让相机正对面板；安全位放在直线安全工作域内，Y∈[-0.28,-0.04]、Z∈[0.44,0.52] 那类区域，可参考文档验证过的固定姿态 roll=-3.141/pitch=-1.552/yaw=3.141。）

### 3.4 面板灯位标定（config.yaml 的 task1.panel → lamps）

当前 Task1 使用 **HSV 绿色直接阈值** 判定亮灯，不需要熄灯基线。先让机械臂停在观察位，
再用手动方式拍图并标出三盏灯中心（最稳）：

```bash
python scripts/03_calibrate_panel.py --mode manual    # 弹出窗口，左→右点 3 盏灯中心
```

（`--mode auto` 仅适用深色背景；摄像头模式由 `camera.mode` 决定，真机改 `real`。）

### 3.5 开关位姿示教（config.yaml 的 task1.panel → switches）★ 核心工作量
对每个开关（预设：开关 0、2 是按钮，开关 1 是中间拨杆）：

| 步骤 | 操作 | 记录命令 |
| --- | --- | --- |
| 1 | 网页面板手动摆臂：**指尖**悬在开关正上方 1~2cm | `python scripts/02_record_pose.py --switch 0 --key approach_pose` |
| 2 | 手动摆到「按钮完全压到底」 | `python scripts/02_record_pose.py --switch 0 --key press_pose` |
| 3 | 开关2（按钮）重复步骤 1、2（--switch 2） | |
| 4 | 拨动开关（中间，--switch 1）：摆到拨杆**中心** | `python scripts/02_record_pose.py --switch 1 --key flick_start_pose` |
| 5 | 摆到拨杆**上拨或下拨终点** | `python scripts/02_record_pose.py --switch 1 --key flick_end_pose` |
| 6 | 拨动开关正上方 | `python scripts/02_record_pose.py --switch 1 --key approach_pose` |

要点：
- 面板配置里 3 个开关的类型已预设为 button/toggle/button（中间是拨杆），若实际排列不同，直接改 `config.yaml` 的 `task1.panel`；每盏灯还必须显式填写 `switch_id`，**不能依赖灯与开关的左右顺序相同**；
- **拨动方向**必须在示教时就在实物上确认（flick_start → flick_end 的矢量就是拨动方向）；
- 摆位时把灵巧手也摆成 `point_pose`（食指伸直）再记位姿，保证「记录位姿时的姿态 = 执行时的姿态」；
- 每次记录前确认当前无报警、记录后立即 `--verify` 一次：
  ```bash
  python scripts/02_record_pose.py --verify
  ```
  出现 ⚠️ OMPL/不可达的位姿要重新摆（说明该位置直线规划会回退成自由路径）。

### 3.5.1 HSV 直接阈值调参

运行时逐灯统计 ROI 内同时满足 `H∈[green_h_min, green_h_max]`、
`S≥green_s_min`、`V≥green_v_min` 的绿色像素占比；占比达到
`green_ratio_min` 的唯一灯即为亮灯。白色未亮灯的饱和度低，会被排除。
首次拍图后可在 `config.yaml` 调整这些五个阈值；不需要运行 `--save-baseline`。

### 3.6 干跑自测（不经过竞赛软件）

程序先读取当前末端位姿：若不在 `arm.task1_safe_pose`，会以低速、逐段直线自动
回安全位；若读不到完整位姿、任一段无法直线规划或未到位则立即停止。第一轮只验证路径：

```bash
python scripts/05_test_task1.py --observe-only
```

该模式不启动相机、不读取灯位和开关位姿，到达观察位后保持不动，须人工确认后恢复。
确认路径无碰撞后，再让三盏灯分别亮起并执行完整自测：

```bash
python scripts/05_test_task1.py
```
预期：日志显示「安全位→观察位（分段）→检测亮灯 #N→开关接近位（分段）→按压/拨动（分段）→观察位→安全位」。任何异常或 OMPL 回退都会停止在当前位置，**不自动撤离**；全程盯着臂，手放在急停旁边。失败看 `runtime/logs/service.log` 的 `OMPL诊断`，并在 B9/ROS/MoveIt 服务端日志中查碰撞、IK 或关节限位根因。

### 3.7 接入竞赛软件
```bash
python scripts/06_serve.py
```
- 竞赛软件 Base URL 填 `http://127.0.0.1:5000`；
- 自测：`curl http://127.0.0.1:5000/api/health` → `{"success":true}`；
- 在软件里点任务1的「调用算法操作」，观察日志与耗时。
- 现场先确认动作后的可观测状态：若对应灯应熄灭或变化，可将 `task1.action_verify` 从 `motion_only` 改为 `lamp_change`，启用动作后复拍校验；规则不保证灯会变化时保留 `motion_only`。

## 4. 关键参数（config.yaml，现场调优顺序）

| 参数 | 含义 | 调优建议 |
| --- | --- | --- |
| `task1.green_h_min/max` | 绿色 Hue 范围（OpenCV 0~179） | 先 35~95；绿灯偏黄/青时扩展范围 |
| `task1.green_s_min` / `green_v_min` | 绿色最低饱和度/亮度 | 漏检→逐步调低；白色或反光误判→调高 S |
| `task1.green_ratio_min` | ROI 内绿色像素占比阈值 | 灯在 ROI 占比小→调低；绿色反光误判→调高 |
| `task1.diff_max_dist` | 做差判定：亮斑到灯位中心的最大允许距离(px) | 灯位有漂移→调大；误匹配→调小 |
| `task1.fine_vel` | 下压/拨动速度 | 先 0.05，稳了再逐步提 |
| `task1.press_dwell_s` | 按压停留 | 按钮行程长→加大 |
| `arm.velocity_fast/slow` | 转运/贴脸速度 | 真机 ≤0.3，长距离可 0.25~0.3 |
| `hand.point_pose` | 按压手型 | 01 脚本实测后定 |

## 5. 常见问题（FAQ）

| 现象 | 原因与处理 |
| --- | --- |
| 运动返回 `Motion timeout (60s)` | 低速长距离超服务器上限 → 提速，或后续版本切 WebSocket |
| message 含 `OMPL` | 直线回退成自由路径 → 目标出安全工作域/姿态偏离，重新摆位示教 |
| `All planning strategies failed` | 目标不可达 → 重摆位姿 |
| 检测不到亮灯 | ROI 偏了（重跑 03）／HSV 阈值不合适（调 green_*）／拍照时灯没亮 |
| 使能成功但臂不动 | 服务器主栈可能以只读安全模式部署（auto_enable=false）→ 找现场工程师 |
| `/api/pose` 返回 null | 系统刚启动 TF 未就绪 → 等几秒重试 |
| 失能后臂下坠 | 这是文档明确的行为（软急停失力矩），**只在低位且有托扶时失能** |
| 手张握方向反了 | 没跑 01 脚本 → 回去做 3.2 |

## 6. 安全纪律（违反直接丢分/取消资格）

- 演示期间禁止任何编程调试；开赛 30 秒内必须点「开始」（逾期 -5）；
- 磕碰一次 -3 分：所有位姿必须 `--verify` 通过 + 全程直线 + 低速贴脸；
- 不确定的动作先 `plan_only` 预览（代码里观察位已默认预览，示教位姿已 verify 过）；
- 紧急情况：网页控制面板急停 / `POST /api/disable`（会掉臂，慎用）。

## 7. 做完 Task1 之后的下一步

- Task2/3 需要「观察位/动作位分离 + 顶面数字识别 + 抓取验证（O10 无触觉，用电流/堵转判据，`hand.close_with_verify` 已内置）+ 手眼标定（`scripts/04_calibrate_handeye.py` 骨架已留好）」；
- 本工程的 arm/hand 客户端、相机抽象、安全监控全部可复用，直接写 `tasks/task2.py`、`tasks/task3.py` 并在 `service.py` 挂上即可。
