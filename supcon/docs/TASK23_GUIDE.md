# Task2 / Task3 现场标定与运行指南

这两个任务均已接入 `/api/task2/execute` 和 `/api/task3/execute`。代码**不会使用示例坐标执行真机动作**：缺少正式标定文件或字段时会安全返回 `success=false`。

所有位姿记录都**只写 `check_pos/` 待核验文件、不改正式配置**，肉眼审核后手动填入 `task2.json` / `task3.json` / `config.yaml`。

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

1. 复制模板：`mkdir -p config/runtime && cp config/templates/task2.example.json config/runtime/task2.json`。
2. 数字识别用**整图 OCR**：在观察位拍一张顶视图，OCR 按文本框 x 坐标左→右读出 4 个数字，依次对应方位 `left → midleft → midright → right`。**无需 ROI、无需数字模板**。
3. 录制 Task2 长方体抓取手型（4 块同尺寸，独立于 Task3）：
   ```bash
   python scripts/08_record_hand_pose.py --set 0.5,0.5,0.5,1,0,0,0,0,0,0   # 试摆
   python scripts/08_record_hand_pose.py --record-task2-grasp              # 记录
   python scripts/08_record_hand_pose.py --apply-task2-grasp               # 回放校验
   # 审核后填入 task2.json 的 default_hand_grasp
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

## Task3：竖直几何体分拣

规则基线：四个几何体均竖直摆放；识别形状后放进外侧标有对应名称的槽位；物体需完全入槽。

**观察位设计（8 个，解决中心俯视斜视角变形）**：抓取端 4 个（每个源工位正上方）+ 放置端 4 个（每个目标槽正上方）。识别形状 OCR 优先、轮廓分类兜底；维护已放置槽位集合，已放过的槽跳过观察。

1. 复制模板：`mkdir -p config/runtime && cp config/templates/task3.example.json config/runtime/task3.json`。
2. 填写每个源工位的 `roi`（物体轮廓区域）与 `label_roi`（若有汉字标签）。
3. 示教每个源工位的**观察位** + 抓取三段（`10` 脚本，`--source 0..3`）：

   ```bash
   python scripts/10_record_scene_pose.py --task 3 --source 0 --key observe_pose    # 抓取观察位（柱体正上方）
   python scripts/10_record_scene_pose.py --task 3 --source 0 --key approach_pose
   python scripts/10_record_scene_pose.py --task 3 --source 0 --key grasp_tcp_pose
   python scripts/10_record_scene_pose.py --task 3 --source 0 --key lift_pose
   # source 1/2/3 同理
   ```

4. 现场确认槽位标签后，示教各形状槽的**观察位** + 放置三段（`10` 脚本，`--dest 形状名`）：

   ```bash
   python scripts/10_record_scene_pose.py --task 3 --dest block --key observe_pose   # 放置观察位（槽正上方）
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

6. 对于轮廓算法低置信或道具颜色接近工装的情况，在 `type_override` 填写现场确认后的类别，不能靠猜测。
7. 运行 `python scripts/07_validate_scene.py --task 3 --plan-only`。

Task3 按更新后的竖直摆放规则实现，**不执行旧方案中的空中 6-DOF 翻转**；这能显著减少碰撞和掉落风险。

## 上场前共同检查

- O10 开合、抓取手型和 B9 控制 TCP 均已在真机确认。
- 相机像素格式、画面方向、ROI 和赛场光照已复核。
- 所有示教位姿均通过 `plan_only`，且正式执行不会出现 `OMPL`。
- 所有 `check_pos/` 待核验文件已审核并填入正式配置（`config.yaml` / `task2.json` / `task3.json`）。
- Task1 的 `config/runtime/panel.json`、Task2 的 `config/runtime/task2.json`、Task3 的 `config/runtime/task3.json` 均已随部署包备份。
