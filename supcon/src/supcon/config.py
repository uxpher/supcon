"""配置加载：默认值 + config/config.yaml 覆盖，提供类型化访问。"""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 推荐固定姿态（文档：X=0.275 平面、324 点采样验证的直线安全工作域）
R_DEF, P_DEF, Y_DEF = -3.141, -1.552, 3.141

DEFAULTS: dict = {
    "service": {"host": "127.0.0.1", "port": 5000},
    "arm": {
        "base_url": "http://127.0.0.1:8087",
        "arm": "right_arm",
        "pose_key": "right",
        "default_rpy": [R_DEF, P_DEF, Y_DEF],
        "velocity_fast": 0.20,
        "velocity_slow": 0.05,
        "acceleration_scaling": 0.12,
        "eef_step": 0.015,
        "action_gap_s": 0.3,
        "timeout": 90,
        "task1_safe_pose": {"x": 0.275, "y": -0.16, "z": 0.48,
                            "roll": R_DEF, "pitch": P_DEF, "yaw": Y_DEF},
        "task2_safe_pose": {"x": 0.275, "y": -0.16, "z": 0.48,
                            "roll": R_DEF, "pitch": P_DEF, "yaw": Y_DEF},
        "task3_safe_pose": {"x": 0.275, "y": -0.16, "z": 0.48,
                            "roll": R_DEF, "pitch": P_DEF, "yaw": Y_DEF},
        "observe_pose": {"x": 0.275, "y": -0.16, "z": 0.48,
                         "roll": R_DEF, "pitch": P_DEF, "yaw": Y_DEF},
    },
    "hand": {
        "base_url": "http://127.0.0.1:8088",
        "open_pose": [1] * 10,
        "close_pose": [0] * 10,
        "point_pose": [0.5, 0.5, 0.5, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "neutral_pose": [0.5] * 10,
        "torque_ma": 200,
        "verify": {"timeout_s": 3.0, "settle_frames": 3, "moved_tol": 0.02,
                   "near_full_tol": 0.05, "poll_interval": 0.05},
    },
    "camera": {
        "mode": "file",
        "color_file": "config/runtime/panel_capture.png",
        "depth_file": "",
        "intrinsics_file": "",
        "align_depth_to_color": True,
        "width": 640,
        "height": 480,
    },
    "task1": {
        "panel": None,  # 主配置；panel_file 仅兼容旧版现场文件
        "panel_file": "config/runtime/panel.json",
        "approach_vel": 0.15,
        "fine_vel": 0.05,
        "press_dwell_s": 0.3,
        "max_retry": 1,
        "lamp_margin": 15.0,
        "lamp_abs_min": 60.0,
        "roi_radius": 18,
        "diff_max_dist": 80.0,
        "preview_first_move": True,
        "confirm_frames": 3,
        "frame_interval_s": 0.12,
        "action_verify": "motion_only",  # motion_only / lamp_change
        "action_change_min": 12.0,
    },
    "task2": {
        "scene": None,  # 主配置；scene_file 仅兼容旧版现场文件
        "scene_file": "config/runtime/task2.json",
        "observe_vel": 0.15,
        "fine_vel": 0.05,
        "preflight": True,
    },
    "task3": {
        "scene": None,        # 主配置；scene_file 仅兼容旧版现场文件
        "calibration": None,  # Task3 手眼/TCP 标定，主配置
        "scene_file": "config/runtime/task3.json",
        "observe_vel": 0.15,
        "fine_vel": 0.05,
        "preflight": True,
    },
    "safety": {
        "poll_interval_s": 0.3,
        "disable_arm_on_emergency": False,
        "effort_guard_enabled": False,
        "effort_guard_threshold": 10.0,
        # HTTP 查询的 feedback_age 并非控制器的实时心跳；需持续足够久并连续
        # 多次异常才允许阻断任务。
        "feedback_age_stop_s": 2.0,
        "feedback_fault_confirmations": 4,
    },
    "debug": {
        "dump_enabled": False,       # 任务执行时是否把相机帧/深度可视化图落盘（调试用）
        "dump_dir": "runtime/debug",  # task1/2/3 的 RGB 落盘根目录（下分 color/ocr/shape）
        "depth_vis_dir": "img_vis",   # task3 深度可视化图目录（→ supcon/img_vis/）
    },
    "logging": {"level": "INFO", "file": "runtime/logs/service.log"},
}


def _merge(base: dict, override: dict) -> dict:
    """深合并：override 覆盖 base，未提供的键保持默认。"""
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _obj(cls, d: dict):
    """用 dict 中与 dataclass 字段同名的键构造实例，其余忽略。"""
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in names})


@dataclass
class ServiceConfig:
    host: str = "127.0.0.1"
    port: int = 5000


@dataclass
class ArmConfig:
    base_url: str = "http://127.0.0.1:8087"
    arm: str = "right_arm"                 # right_arm / left_arm
    pose_key: str = "right"                # right / left
    default_rpy: list = field(default_factory=lambda: [R_DEF, P_DEF, Y_DEF])
    velocity_fast: float = 0.20
    velocity_slow: float = 0.05
    acceleration_scaling: float = 0.12
    eef_step: float = 0.015
    action_gap_s: float = 0.3
    timeout: int = 90
    task1_safe_pose: dict = field(default_factory=lambda: {
        "x": 0.275, "y": -0.16, "z": 0.48, "roll": R_DEF, "pitch": P_DEF, "yaw": Y_DEF})
    task2_safe_pose: dict = field(default_factory=lambda: {
        "x": 0.275, "y": -0.16, "z": 0.48, "roll": R_DEF, "pitch": P_DEF, "yaw": Y_DEF})
    task3_safe_pose: dict = field(default_factory=lambda: {
        "x": 0.275, "y": -0.16, "z": 0.48, "roll": R_DEF, "pitch": P_DEF, "yaw": Y_DEF})
    observe_pose: dict = field(default_factory=lambda: {
        "x": 0.275, "y": -0.16, "z": 0.48, "roll": R_DEF, "pitch": P_DEF, "yaw": Y_DEF})


@dataclass
class HandVerifyConfig:
    timeout_s: float = 3.0
    settle_frames: int = 3
    moved_tol: float = 0.02
    near_full_tol: float = 0.05
    poll_interval: float = 0.05


@dataclass
class HandConfig:
    base_url: str = "http://127.0.0.1:8088"
    open_pose: list = field(default_factory=lambda: [1] * 10)
    close_pose: list = field(default_factory=lambda: [0] * 10)
    point_pose: list = field(default_factory=lambda:
                             [0.5, 0.5, 0.5, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    neutral_pose: list = field(default_factory=lambda: [0.5] * 10)
    torque_ma: int = 200
    verify: HandVerifyConfig = field(default_factory=HandVerifyConfig)


@dataclass
class CameraConfig:
    mode: str = "file"                     # file / real / mock
    color_file: str = "config/runtime/panel_capture.png"
    depth_file: str = ""
    intrinsics_file: str = ""
    align_depth_to_color: bool = True
    width: int = 640
    height: int = 480


@dataclass
class Task1Config:
    panel: dict | None = None
    panel_file: str = "config/runtime/panel.json"
    approach_vel: float = 0.15
    fine_vel: float = 0.05
    press_dwell_s: float = 0.3
    max_retry: int = 1
    lamp_margin: float = 15.0
    lamp_abs_min: float = 60.0
    roi_radius: int = 18
    diff_max_dist: float = 80.0
    preview_first_move: bool = True
    confirm_frames: int = 3
    frame_interval_s: float = 0.12
    action_verify: str = "motion_only"
    action_change_min: float = 12.0


@dataclass
class Task2Config:
    scene: dict | None = None
    scene_file: str = "config/runtime/task2.json"
    observe_vel: float = 0.15
    fine_vel: float = 0.05
    preflight: bool = True


@dataclass
class Task3Config:
    scene: dict | None = None
    calibration: dict | None = None
    scene_file: str = "config/runtime/task3.json"
    observe_vel: float = 0.15
    fine_vel: float = 0.05
    preflight: bool = True


@dataclass
class SafetyConfig:
    poll_interval_s: float = 0.3
    disable_arm_on_emergency: bool = False
    effort_guard_enabled: bool = False
    effort_guard_threshold: float = 10.0
    feedback_age_stop_s: float = 2.0
    feedback_fault_confirmations: int = 4


@dataclass
class DebugConfig:
    dump_enabled: bool = False
    dump_dir: str = "runtime/debug"
    depth_vis_dir: str = "img_vis"


@dataclass
class AppConfig:
    service: ServiceConfig = field(default_factory=ServiceConfig)
    arm: ArmConfig = field(default_factory=ArmConfig)
    hand: HandConfig = field(default_factory=HandConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    task1: Task1Config = field(default_factory=Task1Config)
    task2: Task2Config = field(default_factory=Task2Config)
    task3: Task3Config = field(default_factory=Task3Config)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    logging: dict = field(default_factory=lambda: {"level": "INFO", "file": "runtime/logs/service.log"})

    def resolve(self, rel_path: str) -> str:
        """相对路径统一转成项目根目录下的绝对路径。"""
        if os.path.isabs(rel_path):
            return rel_path
        return str(PROJECT_ROOT / rel_path)


def load_config(path: str | None = None) -> AppConfig:
    """加载配置。path=None 时读项目默认 config/config.yaml。"""
    if path is None:
        path = PROJECT_ROOT / "config" / "config.yaml"
    data: dict = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    merged = _merge(DEFAULTS, data)

    hand_d = dict(merged["hand"])
    verify_d = hand_d.pop("verify", {})
    hand = _obj(HandConfig, hand_d)
    hand.verify = _obj(HandVerifyConfig, verify_d)

    return AppConfig(
        service=_obj(ServiceConfig, merged["service"]),
        arm=_obj(ArmConfig, merged["arm"]),
        hand=hand,
        camera=_obj(CameraConfig, merged["camera"]),
        task1=_obj(Task1Config, merged["task1"]),
        task2=_obj(Task2Config, merged["task2"]),
        task3=_obj(Task3Config, merged["task3"]),
        safety=_obj(SafetyConfig, merged["safety"]),
        debug=_obj(DebugConfig, merged["debug"]),
        logging=dict(merged["logging"]),
    )


def config_yaml_path() -> Path:
    """项目正式配置文件路径（现场标定脚本的唯一写入目标）。"""
    return PROJECT_ROOT / "config" / "config.yaml"


def write_task_value(task: str, key: str, value, path: str | Path | None = None) -> Path:
    """把一个任务字段安全地写回 config.yaml。

    标定工具使用此函数写 ``task1.panel`` 和 ``task3.calibration``，从而不再
    产生散落在 runtime 下的 JSON 配置文件。PyYAML 会规范化 YAML 的排版；
    因此建议将现场配置纳入版本控制或在标定前备份。
    """
    target = Path(path) if path is not None else config_yaml_path()
    with open(target, encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    section = data.setdefault(task, {})
    if not isinstance(section, dict):
        raise ValueError(f"config.yaml 的 {task} 必须是对象")
    section[key] = value
    with open(target, "w", encoding="utf-8") as stream:
        yaml.safe_dump(data, stream, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return target
