#!/usr/bin/env python3

import os
import numpy as np
import scipy.spatial.transform as st
import rerun as rr
import trimesh
import pinocchio as pin
import hppfcl

from tbai_logging import robot_zoo

import logging


class RobotLogger:
  def __init__(self, model: pin.Model, visual_model: pin.GeometryModel, prefix: str = "") -> None:
    self.model = model
    self.visual_model = visual_model
    self.data = model.createData()
    self.visual_data = visual_model.createData()

    self.meshes_logged = set()
    self.prefix = prefix.rstrip("/")
    self.static_transforms_logged = False

    # Build joint name to index mapping
    self._joint_name_to_idx = {}
    for i in range(1, self.model.njoints):  # Skip universe joint at 0
      self._joint_name_to_idx[self.model.names[i]] = i

  def _entity_path(self, name: str) -> str:
    """Get entity path with optional prefix."""
    return f"{self.prefix}/{name}" if self.prefix else name

  @classmethod
  def from_zoo(cls, robot_name: str, prefix: str = "") -> "RobotLogger":
    model, visual_model = robot_zoo.get_robot_model(robot_name)
    return cls(model, visual_model, prefix=prefix)

  @property
  def joint_names(self):
    """Return list of actuated joint names (excludes universe joint)."""
    return [self.model.names[i] for i in range(1, self.model.njoints)]

  def log_static_transforms(self):
    """Log the static geometry."""
    rr.log("", rr.ViewCoordinates.RIGHT_HAND_Z_UP)

    # Log all visual geometries (meshes are static, transforms will be updated)
    for geom in self.visual_model.geometryObjects:
      entity_path = self._entity_path(geom.name)
      self.log_geometry(entity_path, geom)

  def log_state(self, *, joint_positions=None, base_position=None, base_orientation=None, logtime=None):
    """Log the current state (transforms only)."""
    rr.set_time_seconds("robot_time", logtime)

    if not self.static_transforms_logged:
      self.log_static_transforms()
      self.static_transforms_logged = True

    # Build configuration vector
    q = pin.neutral(self.model)

    if joint_positions:
      for joint_name, pos in joint_positions.items():
        if joint_name in self._joint_name_to_idx:
          joint_id = self._joint_name_to_idx[joint_name]
          idx_q = self.model.joints[joint_id].idx_q
          q[idx_q] = pos

    # Compute forward kinematics
    pin.forwardKinematics(self.model, self.data, q)
    pin.updateFramePlacements(self.model, self.data)
    pin.updateGeometryPlacements(self.model, self.data, self.visual_model, self.visual_data)

    # Base transform
    base_transform = pin.SE3.Identity()
    if base_position is not None and base_orientation is not None:
      rotation_matrix = st.Rotation.from_quat(base_orientation).as_matrix()
      base_transform = pin.SE3(rotation_matrix, np.array(base_position))

    # Log transforms for each visual geometry
    for i, geom in enumerate(self.visual_model.geometryObjects):
      entity_path = self._entity_path(geom.name)

      # Get geometry world placement from visual_data
      oMg = self.visual_data.oMg[i]

      # Apply base transform
      world_transform = base_transform * oMg

      rr.log(
        entity_path,
        rr.Transform3D(translation=world_transform.translation, mat3x3=world_transform.rotation),
      )

  def log_geometry(self, entity_path: str, geom: pin.GeometryObject) -> None:
    """Log a visual geometry object (mesh only, no transform)."""
    if entity_path in self.meshes_logged:
      return

    try:
      # Get color
      color = None
      if hasattr(geom, "meshColor") and geom.meshColor is not None:
        color = geom.meshColor

      fcl_geom = geom.geometry
      mesh_path = geom.meshPath if hasattr(geom, "meshPath") else ""
      scale = np.array(geom.meshScale) if hasattr(geom, "meshScale") and geom.meshScale is not None else None

      if mesh_path and os.path.exists(mesh_path):
        # It's a mesh file
        logging.debug(f"Loading mesh from: {mesh_path}")
        logging.debug(f"File size: {os.path.getsize(mesh_path) / 1024 / 1024:.2f} MB")
        mesh_or_scene = trimesh.load_mesh(mesh_path)

        # Apply mesh scale
        if scale is not None:
          mesh_or_scene.apply_scale(scale)

      elif isinstance(fcl_geom, hppfcl.Box):
        extents = [fcl_geom.halfSide[i] * 2 for i in range(3)]
        mesh_or_scene = trimesh.creation.box(extents=extents)

      elif isinstance(fcl_geom, hppfcl.Cylinder):
        mesh_or_scene = trimesh.creation.cylinder(radius=fcl_geom.radius, height=fcl_geom.halfLength * 2)

      elif isinstance(fcl_geom, hppfcl.Sphere):
        mesh_or_scene = trimesh.creation.icosphere(radius=fcl_geom.radius)

      elif isinstance(fcl_geom, hppfcl.Capsule):
        mesh_or_scene = trimesh.creation.capsule(radius=fcl_geom.radius, height=fcl_geom.halfLength * 2)

      elif isinstance(fcl_geom, (hppfcl.BVHModelOBBRSS, hppfcl.BVHModelOBB, hppfcl.Convex)):
        # Handle BVH mesh models - try to load from mesh path first
        if mesh_path and os.path.exists(mesh_path):
          mesh_or_scene = trimesh.load_mesh(mesh_path)
          if scale is not None:
            mesh_or_scene.apply_scale(scale)
        elif hasattr(fcl_geom, "vertices") and hasattr(fcl_geom, "tri_indices"):
          vertices = np.array([fcl_geom.vertices(i) for i in range(fcl_geom.num_vertices)])
          faces = np.array([fcl_geom.tri_indices(i) for i in range(fcl_geom.num_tris)])
          mesh_or_scene = trimesh.Trimesh(vertices=vertices, faces=faces)
        else:
          logging.warning(f"Cannot extract mesh from BVH model: {entity_path}")
          mesh_or_scene = trimesh.creation.box(extents=[0.1, 0.1, 0.1])

      else:
        logging.warning(f"Unsupported geometry type: {type(fcl_geom)}, mesh_path: {mesh_path}")
        mesh_or_scene = trimesh.creation.box(extents=[0.1, 0.1, 0.1])

      if isinstance(mesh_or_scene, trimesh.Scene):
        scene = mesh_or_scene
        for i, mesh in enumerate(scene.dump()):
          if color is not None:
            mesh.visual = trimesh.visual.ColorVisuals()
            mesh.visual.vertex_colors = color
          self.log_trimesh(entity_path + f"/{i}", mesh)
          self.meshes_logged.add(entity_path + f"/{i}")
      else:
        mesh = mesh_or_scene
        if color is not None and str(mesh_path).lower().endswith(".stl"):
          mesh.visual = trimesh.visual.ColorVisuals()
          mesh.visual.vertex_colors = color
        self.log_trimesh(entity_path, mesh)
        self.meshes_logged.add(entity_path)

    except Exception as e:
      logging.error(f"Error loading visual for {entity_path}: {str(e)}")
      mesh = trimesh.creation.box(extents=[0.1, 0.1, 0.1])
      self.log_trimesh(entity_path, mesh)
      self.meshes_logged.add(entity_path)

  def log_trimesh(self, entity_path: str, mesh: trimesh.Trimesh) -> None:
    vertex_colors = albedo_texture = vertex_texcoords = None
    if isinstance(mesh.visual, trimesh.visual.color.ColorVisuals):
      vertex_colors = mesh.visual.vertex_colors
    elif isinstance(mesh.visual, trimesh.visual.texture.TextureVisuals):
      albedo_texture = mesh.visual.material.baseColorTexture
      if len(np.asarray(albedo_texture).shape) == 2:
        albedo_texture = np.stack([albedo_texture] * 3, axis=-1)
      vertex_texcoords = mesh.visual.uv
      if vertex_texcoords is not None:
        vertex_texcoords[:, 1] = 1.0 - vertex_texcoords[:, 1]

    rr.log(
      entity_path,
      rr.Mesh3D(
        vertex_positions=mesh.vertices,
        triangle_indices=mesh.faces,
        vertex_normals=mesh.vertex_normals,
        vertex_colors=vertex_colors,
        albedo_texture=albedo_texture,
        vertex_texcoords=vertex_texcoords,
      ),
    )
