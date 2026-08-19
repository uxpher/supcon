#!/usr/bin/env python3
"""步骤4（可选）：手眼标定 AX=XB。Task1 不需要，为 Task2/3 预留。

原理：T_world_camera = T_world_eef · T_eef_camera，解出固定外参 T_eef_camera。
流程：臂依次到采集位姿 → 拍照检测 ChArUco 板 → 记录 T_base_eef 与板位姿
     → cv2.calibrateHandEye 解 AX=XB → 写入 config.yaml 的 task3.calibration。

⚠️ 注意事项：
- 采集位姿要空间分布好、旋转变化充分（避免姿态近似平行，否则 AX=XB 退化）；
- 解出的矩阵方向要用多点反投影验证后再用；
- 本脚本只能求 T_eef_camera；Task3 还需要单独示教/测量实际抓取 TCP，
  并在 task3.calibration 增加 T_eef_tcp 后才会允许运动；
- Task1 开关位姿是直接示教的，本脚本纯属为后续任务准备。
"""
import pathlib
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon.config import load_config, write_task_value
from supcon.robot.arm import B9Client
from supcon.utils import pose_to_matrix, setup_logging
from supcon.vision.camera import make_camera

# 采集位姿（示例：X=0.275 平面，真机上按实际工作域修改）
COLLECT_POSES = [
    {"x": 0.275, "y": -0.20, "z": 0.50, "roll": -3.141, "pitch": -1.55, "yaw": 3.14},
    {"x": 0.275, "y": -0.12, "z": 0.50, "roll": -3.141, "pitch": -1.55, "yaw": 3.14},
    {"x": 0.275, "y": -0.20, "z": 0.44, "roll": -3.141, "pitch": -1.55, "yaw": 3.14},
    {"x": 0.275, "y": -0.12, "z": 0.44, "roll": -3.141, "pitch": -1.55, "yaw": 3.14},
    {"x": 0.275, "y": -0.20, "z": 0.50, "roll": -2.94, "pitch": -1.40, "yaw": 3.00},
    {"x": 0.275, "y": -0.12, "z": 0.50, "roll": -3.30, "pitch": -1.70, "yaw": 3.20},
    {"x": 0.275, "y": -0.16, "z": 0.52, "roll": -3.141, "pitch": -1.55, "yaw": 3.14},
    {"x": 0.275, "y": -0.16, "z": 0.46, "roll": -3.141, "pitch": -1.55, "yaw": 3.14},
]


def main():
    cfg = load_config()
    setup_logging("INFO", None)
    arm = B9Client(cfg.arm)
    camera = make_camera(cfg.camera)

    # ChArUco 板（5x7 格，方格 0.03m，marker 0.023m —— 按自己的标定板改）
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    board = cv2.aruco.CharucoBoard((7, 5), 0.03, 0.023, aruco_dict)
    detector = cv2.aruco.CharucoDetector(board)
    intrinsics = getattr(camera, "intrinsics", None)
    if not isinstance(intrinsics, dict):
        sys.exit("无法从相机 SDK 读取 RGB 内参；请先修复相机内参读取，再进行手眼标定")
    try:
        K = np.array([[float(intrinsics["fx"]), 0.0, float(intrinsics["cx"])],
                      [0.0, float(intrinsics["fy"]), float(intrinsics["cy"])],
                      [0.0, 0.0, 1.0]], dtype=float)
    except (KeyError, TypeError, ValueError) as exc:
        sys.exit(f"相机内参无效: {exc}")
    # SDK 未暴露畸变项时只能先以零畸变近似；若复投影误差不合格，须改用
    # 标定得到的 distCoeffs，而不是继续使用这份外参。
    dist = np.zeros((5, 1), dtype=float)

    ok, why = arm.healthy()
    if not ok:
        sys.exit(f"机械臂电机异常: {why}")
    arm.enable()

    R_g2b, t_g2b, R_t2c, t_t2c = [], [], [], []
    for i, pose in enumerate(COLLECT_POSES):
        arm.goto_pose(pose, vel=0.1)
        time.sleep(0.8)
        rgb = camera.grab_rgb()
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        charuco_corners, charuco_ids, marker_corners, marker_ids = \
            detector.detectBoard(gray)
        if charuco_ids is None or len(charuco_ids) < 6:
            print(f"位姿 {i}: 未检测到板（角点 {0 if charuco_ids is None else len(charuco_ids)}），跳过")
            continue
        okp, rvec, tvec = cv2.aruco.estimatePoseCharucoBoard(
            charuco_corners, charuco_ids, board, camera_matrix=K, dist_coeffs=dist)
        if not okp:
            print(f"位姿 {i}: 板位姿估计失败，跳过")
            continue
        print(f"位姿 {i}: 检测到 {len(charuco_ids)} 个 ChArUco 角点")

        T_base_eef = pose_to_matrix(arm.pose())
        # OpenCV 输入约定正是 gripper->base 和 target(board)->camera，
        # 不能取 T_base_eef 的逆。
        R_g2b.append(T_base_eef[:3, :3])
        t_g2b.append(T_base_eef[:3, 3])
        R_t2c.append(cv2.Rodrigues(rvec)[0])
        t_t2c.append(tvec.reshape(3))

    if len(R_g2b) < 5:
        sys.exit("有效位姿不足 5 个，无法可靠解 AX=XB，请调整采集位姿")

    R_cam2grip, t_cam2grip = cv2.calibrateHandEye(R_g2b, t_g2b, R_t2c, t_t2c)
    T_cam2grip = np.eye(4)
    T_cam2grip[:3, :3] = R_cam2grip
    T_cam2grip[:3, 3] = t_cam2grip.reshape(3)
    # OpenCV 返回 camera→gripper；B9 的 gripper 即 EEF，因此它正是本项目
    # 使用的 T_eef_camera（相机坐标点左乘后落在末端坐标系）。
    T_eef_camera = T_cam2grip
    calibration = dict(cfg.task3.calibration or {})
    calibration["T_eef_camera"] = T_eef_camera.tolist()
    calibration.setdefault("T_eef_tcp", None)
    calibration["note"] = "仅含 T_eef_camera；使用前必须多点反投影验证，并人工补充 T_eef_tcp。"
    out = write_task_value("task3", "calibration", calibration)
    print(f"已写入 {out} 的 task3.calibration")
    print("⚠️ 请用多点反投影验证外参，并人工补充实际抓取 TCP 的 T_eef_tcp；"
          "Task3 在该字段缺失时会安全拒绝运动。")


if __name__ == "__main__":
    main()
