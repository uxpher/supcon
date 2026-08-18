#!/usr/bin/env python3
"""步骤 8：灵巧手手型记录（读 position → 写独立待审核文件，不改正式配置）。

⚠️ O10 的 HTTP API 没有拖动/零力矩接口，所以"摆手型"是：
   用 --set 发候选手型 → 人工看手指 → 反复调 → 满意后用 --record 记录。

本脚本只读写独立的"待核验文件" check_pos/灵巧手_手型_待核验.json，
**绝不修改 config.yaml / task3.json / task2.json**。审核后请手动把数值填入正式配置。

用法：
  # ① 打印当前手型（归一化 position + 弧度 joint_rad）
  python scripts/08_record_hand_pose.py --where

  # ② 程序摆一个候选手型（10 个逗号分隔，0-1）
  python scripts/08_record_hand_pose.py --set 0.5,0.5,0.5,1,0,0,0,0,0,0

  # ③ 满意后，把当前手型记录到待审核文件（open_pose/close_pose/point_pose）
  python scripts/08_record_hand_pose.py --record point_pose

  # ④ 记录某个形状的抓取手型（Task3 用，对齐 task3.json 的 hand_grasps 字段）
  python scripts/08_record_hand_pose.py --record-grasp block

  # ⑤ 记录任务2长方体的抓取手型（4 块同尺寸，独立于任务3 → task2.json default_hand_grasp）
  python scripts/08_record_hand_pose.py --record-task2-grasp

  # ⑥ 查看待审核文件全部内容
  python scripts/08_record_hand_pose.py --show

  # ⑦ 回放校验某个已记录手型（确认能复现）
  python scripts/08_record_hand_pose.py --apply point_pose
  python scripts/08_record_hand_pose.py --apply-grasp block
  python scripts/08_record_hand_pose.py --apply-task2-grasp
"""
import argparse
import json
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from supcon.config import load_config
from supcon.robot.hand import JOINT_NAMES, O10Client
from supcon.utils import setup_logging

# 待核验文件（相对项目根目录），独立于任何正式配置
REVIEW_FILE = "check_pos/灵巧手_手型_待核验.json"

HAND_KEYS = ("open_pose", "close_pose", "point_pose")
# 与 config/templates/task3.example.json 的 hand_grasps 字段对齐
GRASP_SHAPES = ("block", "hexagonal_prism", "triangular_prism", "cylinder")

# 每个字段的中文说明（写进 _comment，方便肉眼审核时对照）
HAND_MEANING = {
    "open_pose": "张手：让手指完全张开",
    "close_pose": "握拳：让手指完全闭合",
    "point_pose": "点按姿态：食指伸直、其余手指收拢（Task1 按压用）",
}
GRASP_MEANING = {
    "block": "长方体（block）抓取手型",
    "hexagonal_prism": "正六棱柱（hexagonal_prism）抓取手型",
    "triangular_prism": "三棱柱（triangular_prism）抓取手型",
    "cylinder": "圆柱体（cylinder）抓取手型",
}

EMPTY = {
    "_comment": (
        "灵巧手手型 待核验记录（归一化 position，0-1 × 10，索引 0-9 = "
        "拇指旋转/拇指外展/拇指弯曲/食指侧摆/食指弯曲/中指弯曲/无名指侧摆/无名指弯曲/小指侧摆/小指弯曲）。"
        "hand.open_pose=张手；hand.close_pose=握拳；hand.point_pose=食指伸直点按。"
        "task2_hand_grasp=任务2长方体抓取手型（4 块同尺寸，独立于任务3）。"
        "task3_hand_grasps.*=任务3各形状的抓取手型。"
        "审核后手动填入 config.yaml 的 hand.*、task2.json 的 default_hand_grasp 或 task3.json 的 hand_grasps.*。"
        "本文件不改动任何正式配置。"
    ),
    "hand": {k: None for k in HAND_KEYS},
    "task2_hand_grasp": None,
    "task3_hand_grasps": {k: None for k in GRASP_SHAPES},
}


def _review_path(cfg) -> str:
    return cfg.resolve(REVIEW_FILE)


def _load_review(cfg) -> dict:
    p = _review_path(cfg)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.loads(json.dumps(EMPTY))
    # 补齐缺失字段，保证结构完整
    data.setdefault("_comment", EMPTY["_comment"])
    hand = data.setdefault("hand", {})
    for k in HAND_KEYS:
        hand.setdefault(k, None)
    data.setdefault("task2_hand_grasp", None)
    grasps = data.setdefault("task3_hand_grasps", {})
    for k in GRASP_SHAPES:
        grasps.setdefault(k, None)
    return data


def _save_review(cfg, data: dict) -> str:
    p = _review_path(cfg)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return p


def _current_position(hand) -> list:
    s = hand.status()
    pos = s.get("position") or []
    if len(pos) != 10:
        sys.exit(
            f"读不到 10 维 position（实际 {len(pos)}）。"
            f"connected={s.get('connected')}, hand_type={s.get('hand_type')}"
        )
    return [float(p) for p in pos]


def _print_position(pos, rad):
    print("归一化 position:", [round(p, 3) for p in pos])
    if rad and len(rad) == 10:
        print("弧度 joint_rad :", [round(r, 3) for r in rad])
    print("关节名(0-9)    :", ", ".join(JOINT_NAMES))


def main():
    ap = argparse.ArgumentParser(
        description="灵巧手手型记录（只写独立待审核文件，不改正式配置）"
    )
    ap.add_argument("--where", action="store_true", help="打印当前手型")
    ap.add_argument("--set", type=str, help="程序摆候选手型，逗号分隔 10 个 0-1 值")
    ap.add_argument("--record", choices=HAND_KEYS, help="记录当前手型到 hand.<key>")
    ap.add_argument("--record-grasp", choices=GRASP_SHAPES,
                    help="记录抓取手型到 task3_hand_grasps.<shape>")
    ap.add_argument("--record-task2-grasp", action="store_true",
                    help="记录任务2长方体抓取手型到 task2_hand_grasp")
    ap.add_argument("--apply", choices=HAND_KEYS, help="回放校验 hand.<key>")
    ap.add_argument("--apply-grasp", choices=GRASP_SHAPES,
                    help="回放校验 task3_hand_grasps.<shape>")
    ap.add_argument("--apply-task2-grasp", action="store_true",
                    help="回放校验 task2_hand_grasp")
    ap.add_argument("--show", action="store_true", help="查看待审核文件内容")
    a = ap.parse_args()

    cfg = load_config()
    setup_logging("INFO", None)
    hand = O10Client(cfg.hand)

    if a.set:
        parts = [float(x) for x in a.set.split(",")]
        if len(parts) != 10 or any(not (0.0 <= p <= 1.0) for p in parts):
            sys.exit("--set 需要 10 个逗号分隔的 0-1 数值")
        hand.set_pos(parts)
        time.sleep(0.8)
        s = hand.status()
        print("已发送候选值，当前状态:")
        _print_position(parts, s.get("joint_rad") or [])
        print("\n（人工确认手指姿态满意后，再跑 --record / --record-grasp 记录）")
        return

    if a.where:
        s = hand.status()
        _print_position(s.get("position") or [], s.get("joint_rad") or [])
        return

    if a.record:
        pos = _current_position(hand)
        data = _load_review(cfg)
        data["hand"][a.record] = pos
        p = _save_review(cfg, data)
        print(f"已记录 hand.{a.record} = {[round(x, 3) for x in pos]}")
        print(f"→ 已写入待审核文件: {p}")
        print("→ 未改动 config.yaml，审核后请手动填入正式配置")
        return

    if a.record_grasp:
        pos = _current_position(hand)
        data = _load_review(cfg)
        data["task3_hand_grasps"][a.record_grasp] = pos
        p = _save_review(cfg, data)
        print(f"已记录 task3_hand_grasps.{a.record_grasp} = {[round(x, 3) for x in pos]}")
        print(f"→ 已写入待审核文件: {p}")
        print("→ 未改动 task3.json，审核后请手动填入正式配置")
        return

    if a.record_task2_grasp:
        pos = _current_position(hand)
        data = _load_review(cfg)
        data["task2_hand_grasp"] = pos
        p = _save_review(cfg, data)
        print(f"已记录 task2_hand_grasp = {[round(x, 3) for x in pos]}")
        print(f"→ 已写入待审核文件: {p}")
        print("→ 未改动 task2.json，审核后请手动填入 task2.json 的 default_hand_grasp")
        return

    if a.apply:
        data = _load_review(cfg)
        pos = data["hand"].get(a.apply)
        if not pos:
            sys.exit(f"待审核文件里还没有 hand.{a.apply}，先 --record 记录")
        hand.set_pos(pos)
        time.sleep(0.8)
        cur = _current_position(hand)
        diff = max(abs(x - y) for x, y in zip(pos, cur))
        print(f"回放 hand.{a.apply}")
        print(f"  目标 = {[round(x, 3) for x in pos]}")
        print(f"  实际 = {[round(x, 3) for x in cur]}  最大偏差 = {diff:.3f}")
        print("✅ 可复现" if diff < 0.05 else "⚠️ 偏差较大，请检查是否堵转/误触")
        return

    if a.apply_grasp:
        data = _load_review(cfg)
        pos = data["task3_hand_grasps"].get(a.apply_grasp)
        if not pos:
            sys.exit(f"待审核文件里还没有 task3_hand_grasps.{a.apply_grasp}，先 --record-grasp 记录")
        hand.set_pos(pos)
        time.sleep(0.8)
        cur = _current_position(hand)
        diff = max(abs(x - y) for x, y in zip(pos, cur))
        print(f"回放 task3_hand_grasps.{a.apply_grasp}")
        print(f"  目标 = {[round(x, 3) for x in pos]}")
        print(f"  实际 = {[round(x, 3) for x in cur]}  最大偏差 = {diff:.3f}")
        print("✅ 可复现" if diff < 0.05 else "⚠️ 偏差较大，请检查是否堵转/误触")
        return

    if a.apply_task2_grasp:
        data = _load_review(cfg)
        pos = data.get("task2_hand_grasp")
        if not pos:
            sys.exit("待审核文件里还没有 task2_hand_grasp，先 --record-task2-grasp 记录")
        hand.set_pos(pos)
        time.sleep(0.8)
        cur = _current_position(hand)
        diff = max(abs(x - y) for x, y in zip(pos, cur))
        print("回放 task2_hand_grasp")
        print(f"  目标 = {[round(x, 3) for x in pos]}")
        print(f"  实际 = {[round(x, 3) for x in cur]}  最大偏差 = {diff:.3f}")
        print("✅ 可复现" if diff < 0.05 else "⚠️ 偏差较大，请检查是否堵转/误触")
        return

    if a.show:
        data = _load_review(cfg)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"\n（待审核文件位置: {_review_path(cfg)}）")
        return

    ap.print_help()


if __name__ == "__main__":
    main()
