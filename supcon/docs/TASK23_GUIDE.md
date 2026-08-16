# Task2 / Task3 现场标定与运行指南

这两个任务均已接入 `/api/task2/execute` 和 `/api/task3/execute`。代码**不会使用示例坐标执行真机动作**：缺少正式标定文件或字段时会安全返回 `success=false`。

## Task2：顶面数字长方体

规则基线：数字仅在顶面；必须按 `1 → 2 → 3 → 4` 顺序抓取；将物体放至指定台面，并复现其初始竖直姿态。

1. 复制模板：`mkdir -p config/runtime && cp config/templates/task2.example.json config/runtime/task2.json`。
2. 在固定观察位拍摄面向四个源槽位的顶视图，填写每个 `top_digit_roi`。
3. 以赛场相机、赛场光照采集顶面数字模板，存为 `config/digit_templates/1.png` 至 `4.png`。
4. 以固定的点按/抓取手型，示教每个源槽位的 `approach_pose`、`grasp_tcp_pose`、`lift_pose`。
5. 在指定台面上示教数字 1–4 的独立放置位置，填写 `table_placements`。位置必须都在指定台面内，且 RPY 与初始物块姿态一致。
6. 执行 `python scripts/07_validate_scene.py --task 2 --plan-only`；任何 OMPL 回退或不可达都必须重新示教。

Task2 的 OCR 仅在观察位读取顶面。出现数字缺失、重复或低置信度时，任务会停止并退回安全位，不会猜测顺序。

## Task3：竖直几何体分拣

规则基线：四个几何体均竖直摆放；识别形状后放进外侧标有对应名称的槽位；物体需完全入槽。

1. 复制模板：`mkdir -p config/runtime && cp config/templates/task3.example.json config/runtime/task3.json`。
2. 填写每个源工位的 `roi` 与三段抓取 TCP 位姿。
3. 现场确认槽位标签后，填写 `destinations` 的类别名称和各槽位三段放置位姿。
4. 为每种真实道具录制 `hand_grasp`；对于轮廓算法低置信或道具颜色接近工装的情况，在 `type_override` 填写现场确认后的类别，不能靠猜测。
5. 运行 `python scripts/07_validate_scene.py --task 3 --plan-only`。

Task3 按更新后的竖直摆放规则实现，**不执行旧方案中的空中 6-DOF 翻转**；这能显著减少碰撞和掉落风险。

## 上场前共同检查

- O10 开合、抓取手型和 B9 控制 TCP 均已在真机确认。
- 相机像素格式、画面方向、ROI 和赛场光照已复核。
- 所有示教位姿均通过 `plan_only`，且正式执行不会出现 `OMPL`。
- Task1 的 `config/runtime/panel.json`、Task2 的 `config/runtime/task2.json`、Task3 的 `config/runtime/task3.json` 和数字模板均已随部署包备份。
