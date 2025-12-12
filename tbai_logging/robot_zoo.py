#!/usr/bin/env python3

from robot_descriptions import DESCRIPTIONS
from robot_descriptions.loaders.pinocchio import load_robot_description


def all_robots() -> list[str]:
  return [name for (name, value) in DESCRIPTIONS.items() if value.has_urdf]


def get_robot_model(robot_name: str):
  """Load a robot model from robot_descriptions. Returns the model and the pinocchio visual geometry model."""
  robot = load_robot_description(robot_name)
  return robot.model, robot.visual_model


__all__ = ["get_robot_model", "all_robots"]
