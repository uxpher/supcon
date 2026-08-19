# Task2 / Task3 现场标定与运行指南

这两个任务均已接入 `/api/task2/execute` 和 `/api/task3/execute`。代码**不会使用示例坐标执行真机动作**：缺少 `config.yaml` 中的正式标定字段时会安全返回 `success=false`。

若 `task2.reuse_placement_1_for_all: true`，Task2 会将 1～4 号木块均直接放到
`table_placements.'1'.place_pose`，不要求/执行放置接近位；释放后执行该配置的
`retreat_pose`（当前填为 Task2 安全位）。该配置不做已放木块碰撞规避。

Task2 如已由现场人员明确决定使用 OMPL 自由路径调试，可直跑
`python scripts/05_test_task2.py --unsafe-free-path`，或服务方式启动
`python scripts/06_serve.py --unsafe-free-path` 后调用 `POST /api/execute`、请求体
`{"task": 2}`。
该模式跳过 `plan_only` 与软件安全监控，失败后不自动撤离，服务会根据请求字段选择 Task1 或 Task2，并禁用 Task3；仅在急停可用且全程有人监控时使用。

所有位姿记录都**只写 `check_pos/` 待核验文件、不改正式配置**，肉眼审核后手动填入 `config.yaml` 的 `task2.scene` / `task3.scene`。

## 位姿（pose）含义速查

所有 pose 都是机械臂末端（带灵巧手）的绝对位姿（x/y/z/roll/pitch/yaw，米/弧度），三段一组对应「抓取 → 转运 → 放置」。

| 侧 | pose | 含义 | 末端位置 |
| --- | --- | --- | --- |
| 源工位（抓取） | `approach_pose` | 接近位 | 物体正上方安全高度 |
| | `grasp_tcp_pose` | 抓取位 | 下降贴住/包住物体 |
| | `lift_pose` | 抬升位 | 抓后抬起离开工位 |
| 目标（放置） | `approach_pose` | 接近位 | 槽/放置点正上方 |
| | `place_pose` | 放置位 | 下降到底部入槽 |
| | `retreat_pose` | 撤离位 | 张手后退开 |

动作序列：`approach_pose → grasp_tcp_pose → 闭合抓取 → lift_pose → 目标 approach_pose → place_pose → 张手释放 → retreat_pose`

## 通用：观察位与安全位（09 脚本）

**3 个任务的安全位各自独立**（防直线移动碰撞），观察位也各自独立：

```bash
# Task2 安全位（远离槽位/台面）+ 观察位（拍全 4 个源槽位顶面）
python scripts/09_record_arm_pose.py --task 2 --key safe_pose
python scripts/09_record_arm_pose.py --task 2 --key observe_pose

# Task3 安全位（远离几何体/槽位）+ 观察位
python scripts/09_record_arm_pose.py --task 3 --key safe_pose
python scripts/09_record_arm_pose.py --task 3 --key observe_pose
```

> 摆位方式：B9 网页控制面板 / teach_mode 手动拖到位 → 记录；`--where` 可打印当前位姿。

## Task2：顶面数字长方体

规则基线：数字仅在顶面；必须按 `1 → 2 → 3 → 4` 顺序抓取；将物体放至指定台面，并复现其初始竖直姿态。

1. `config.yaml` 已内置 `task2.scene` 模板；直接在其中填写示教位姿。
2. 数字识别用**整图 OCR**：在观察位拍一张顶视图，OCR 按文本框 x 坐标左→右读出 4 个数字，依次对应方位 `left → midleft → midright → right`。**无需 ROI、无需数字模板**。
3. 录制 Task2 长方体抓取手型（4 块同尺寸，独立于 Task3）：
   ```bash
   python scripts/08_record_hand_pose.py --set 0.5,0.5,0.5,1,0,0,0,0,0,0   # 试摆
   python scripts/08_record_hand_pose.py --record-task2-grasp              # 记录
   python scripts/08_record_hand_pose.py --apply-task2-grasp               # 回放校验
   # 审核后填入 config.yaml 的 task2.scene.default_hand_grasp
   ```
4. 示教每个源槽位的抓取三段位姿（`10` 脚本，`--source left/midleft/midright/right`）：
   ```bash
   python scripts/10_record_scene_pose.py --task 2 --source left --key approach_pose   # 接近位（正上方）
   python scripts/10_record_scene_pose.py --task 2 --source left --key grasp_tcp_pose  # 抓取位（下降贴住）
   python scripts/10_record_scene_pose.py --task 2 --source left --key lift_pose       # 抬升位（抓后抬起）
   # midleft / midright / right 同理
   ```
5. 示教台面放置位（`10` 脚本，数字 `1~4` 各三段）：
   ```bash
   python scripts/10_record_scene_pose.py --task 2 --dest 1 --key approach_pose
   python scripts/10_record_scene_pose.py --task 2 --dest 1 --key place_pose
   python scripts/10_record_scene_pose.py --task 2 --dest 1 --key retreat_pose
   # dest 2/3/4 同理；位置必须都在指定台面内，RPY 与初始物块姿态一致
   ```
6. 校验：`python scripts/07_validate_scene.py --task 2 --plan-only`；任何 OMPL 回退或不可达都必须重新示教。

Task2 仅在观察位读一次整图 OCR。若 OCR 未能读出恰好 `{1,2,3,4}` 四个数字，任务停止并退回安全位，不会猜测顺序。

## Task3：竖直几何体动态分拣

规则基线：四个几何体均竖直摆放；识别形状后放进外侧标有对应名称的槽位；物体需完全入槽。源物体的桌面 XY **不示教、不固定**。

运行流程是：全局观察位采集同帧、对齐的 RGB-D → RANSAC 分割桌面和四个突出物 → 顶面轮廓分类 → 根据实时 B9 末端位姿及手眼外参转换到基座系 → 预抓高度复拍校正 → 竖直抓/放。识别到数量、类别、置信度或位置偏差不符合要求时会停止，不猜测坐标。

1. `config.yaml` 已内置 `task3.scene` 和 `task3.calibration` 模板；直接在其中填写。
2. 使用 `09` 记录唯一的全局 `observe_pose`；它须能完整看到桌面工作区，且高度高于所有木块。填写 `perception.workspace_roi`、深度范围、实际 RGB 内参（真机可由 SDK 自动读取）。
3. 完成手眼标定：`python scripts/04_calibrate_handeye.py` 会写入 `task3.calibration.T_eef_camera`。随后测量实际抓取 TCP，并在 `config.yaml` 补充 `task3.calibration.T_eef_tcp`。两矩阵均须用多点反投影与低速试抓复核；缺少任一个字段，Task3 会拒绝使能/运动。
4. 现场确认槽位文字后，示教各形状槽的放置三段（`10` 脚本，`--dest 形状名`）：

   ```bash
   python scripts/10_record_scene_pose.py --task 3 --dest block --key approach_pose
   python scripts/10_record_scene_pose.py --task 3 --dest block --key place_pose
   python scripts/10_record_scene_pose.py --task 3 --dest block --key retreat_pose
   # hexagonal_prism / triangular_prism / cylinder 同理
   ```

5. 录制每种形状的抓取手型（`08` 脚本，10 维）：

   ```bash
   python scripts/08_record_hand_pose.py --set 0.5,0.5,0.5,1,0,0,0,0,0,0   # 试摆
   python scripts/08_record_hand_pose.py --record-grasp block               # 记录
   python scripts/08_record_hand_pose.py --apply-grasp block                # 回放校验
   # hexagonal_prism / triangular_prism / cylinder 同理
   ```

6. 调高 `min_shape_confidence`、缩小 `workspace_roi` 直到四物体稳定各识别一次；不要添加固定 `type_override` 或固定抓取坐标来绕过检测。
7. 运行 `python scripts/07_validate_scene.py --task 3 --plan-only`。该命令验证观察位、槽位与两份外参，并只规划静态位姿；动态抓取位会在运行时逐件 `plan_only`。

Task3 按更新后的竖直摆放规则实现，**不执行旧方案中的空中 6-DOF 翻转**；这能显著减少碰撞和掉落风险。

## 上场前共同检查

- O10 开合、抓取手型和 B9 控制 TCP 均已在真机确认。
- 相机像素格式、画面方向、ROI 和赛场光照已复核。
- 所有示教位姿均通过 `plan_only`，且正式执行不会出现 `OMPL`。
- 所有 `check_pos/` 待核验文件已审核并填入正式配置 `config.yaml`。
- 已备份 `config/config.yaml` 与标定图片。
