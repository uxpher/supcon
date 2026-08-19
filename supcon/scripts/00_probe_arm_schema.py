#!/usr/bin/env python3
"""只规划探测 B9 /api/end_effector 所接受的 mode 与目标位姿字段。

不下发执行轨迹：每个请求都带 plan_only=true，目标为当前末端位姿。
用于现场出现 ``Invalid mode or missing target`` 时识别 left/right API 兼容差异。
"""
import pathlib
import sys

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon.config import load_config


def main():
    cfg = load_config()
    base = cfg.arm.base_url.rstrip("/")
    pose_response = requests.get(f"{base}/api/pose", timeout=5)
    pose_response.raise_for_status()
    pose = pose_response.json().get("pose")
    required = {"x", "y", "z", "roll", "pitch", "yaw"}
    if not isinstance(pose, dict) or not required.issubset(pose):
        raise RuntimeError(f"/api/pose 未返回完整末端位姿：{pose}")

    # 先试当前配置，再试 B9 常见的三个组合；保序去重。
    candidates = []
    for item in ((cfg.arm.arm, cfg.arm.target_pose_key),
                 ("left_arm", "left"), ("left_arm", "right"),
                 ("right_arm", "right"), ("right_arm", "left")):
        if item not in candidates:
            candidates.append(item)

    print("仅 plan_only 探测，不会执行运动；目标=当前末端位姿。")
    accepted = []
    for mode, target_key in candidates:
        payload = {
            "mode": mode,
            target_key: pose,
            "cartesian_linear": True,
            "velocity_scaling": 0.03,
            "acceleration_scaling": cfg.arm.acceleration_scaling,
            "cartesian_eef_step": cfg.arm.eef_step,
            "plan_only": True,
        }
        try:
            response = requests.post(f"{base}/api/end_effector", json=payload, timeout=15)
            try:
                body = response.json()
            except ValueError:
                body = response.text[:500]
            success = response.ok and isinstance(body, dict) and body.get("success") is True
            print(f"mode={mode:<9} target={target_key:<5} HTTP {response.status_code}: {body}")
            if success:
                accepted.append((mode, target_key))
        except requests.RequestException as exc:
            print(f"mode={mode:<9} target={target_key:<5} 请求失败: {exc}")

    if len(accepted) == 1:
        mode, target_key = accepted[0]
        print("\n唯一可用组合：请填写 config/config.yaml：")
        print(f'  arm: "{mode}"')
        print(f'  target_pose_key: "{target_key}"')
    elif not accepted:
        print("\n没有组合通过：请检查 B9 运动服务、当前控制模式与服务端日志。")
    else:
        print(f"\n存在多个可用组合 {accepted}；优先保留当前实际控制臂对应的组合。")


if __name__ == "__main__":
    main()
