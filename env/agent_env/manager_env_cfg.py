# Copyright (c) 2025-2026 Junjie Zhu
# SPDX-License-Identifier: Apache-2.0

import math
from dataclasses import MISSING

import omni.isaac.lab.sim as sim_utils
from omni.isaac.lab.assets import ArticulationCfg, AssetBaseCfg
from omni.isaac.lab.envs import ManagerBasedRLEnvCfg
from omni.isaac.lab.managers import CurriculumTermCfg as CurrTerm
from omni.isaac.lab.managers import EventTermCfg as EventTerm
from omni.isaac.lab.managers import ObservationGroupCfg as ObsGroup
from omni.isaac.lab.managers import ObservationTermCfg as ObsTerm
from omni.isaac.lab.managers import RewardTermCfg as RewTerm
from omni.isaac.lab.managers import SceneEntityCfg
from omni.isaac.lab.managers import TerminationTermCfg as DoneTerm
from omni.isaac.lab.scene import InteractiveSceneCfg
from omni.isaac.lab.sensors import ContactSensorCfg, RayCasterCfg, patterns
from omni.isaac.lab.terrains import TerrainImporterCfg, TerrainGeneratorCfg
from omni.isaac.lab.utils import configclass
from omni.isaac.lab.utils.assets import ISAAC_NUCLEUS_DIR, ISAACLAB_NUCLEUS_DIR
from omni.isaac.lab.utils.noise import AdditiveUniformNoiseCfg as Unoise
import omni.isaac.lab.terrains as terrain_gen

import omni.isaac.lab_tasks.manager_based.locomotion.velocity.mdp as mdp

from .local_mdp import observations, rewards,commands_cfg
##
# Pre-defined configs
##
from omni.isaac.lab.terrains.config.rough import ROUGH_TERRAINS_CFG  # isort: skip


##
# Scene definition
##

Go2_BASE_TERRAINS_CFG = TerrainGeneratorCfg(
    size=(8.0, 8.0),
    border_width=20.0,
    num_rows=10,
    num_cols=20,
    horizontal_scale=0.1,
    vertical_scale=0.005,
    slope_threshold=0.75,
    use_cache=False,
    sub_terrains={
        "flat": terrain_gen.MeshPlaneTerrainCfg(proportion=0.3),
        "random_rough": terrain_gen.HfRandomUniformTerrainCfg(
            proportion=0.7, noise_range=(-0.01, 0.05), noise_step=0.02, border_width=0.25
        ),
    },
)


@configclass
class MySceneCfg(InteractiveSceneCfg):
    """Configuration for the terrain scene with a legged robot."""

    # ground terrain
    terrain = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="generator",
        terrain_generator=Go2_BASE_TERRAINS_CFG,
        max_init_terrain_level=5,
        collision_group=-1,
        physics_material=sim_utils.RigidBodyMaterialCfg(
            friction_combine_mode="multiply",
            restitution_combine_mode="multiply",
            static_friction=1.0,
            dynamic_friction=1.0,
        ),
        visual_material=sim_utils.MdlFileCfg(
            mdl_path=f"{ISAACLAB_NUCLEUS_DIR}/Materials/TilesMarbleSpiderWhiteBrickBondHoned/TilesMarbleSpiderWhiteBrickBondHoned.mdl",
            project_uvw=True,
            texture_scale=(0.25, 0.25),
        ),
        debug_vis=False,
    )
    # robots
    robot: ArticulationCfg = MISSING
    # sensors
    height_scanner = RayCasterCfg(
        prim_path="{ENV_REGEX_NS}/Robot/base",
        offset=RayCasterCfg.OffsetCfg(pos=(0.0, 0.0, 20.0)),
        attach_yaw_only=True,
        pattern_cfg=patterns.GridPatternCfg(resolution=0.1, size=[1.6, 1.0]),
        debug_vis=False,
        mesh_prim_paths=["/World/ground"],
    )
    contact_forces = ContactSensorCfg(prim_path="{ENV_REGEX_NS}/Robot/.*", history_length=3, track_air_time=True)
    # lights
    sky_light = AssetBaseCfg(
        prim_path="/World/skyLight",
        spawn=sim_utils.DomeLightCfg(
            intensity=750.0,
            texture_file=f"{ISAAC_NUCLEUS_DIR}/Materials/Textures/Skies/PolyHaven/kloofendal_43d_clear_puresky_4k.hdr",
        ),
    )


@configclass
class EventCfg:
    """Configuration for events."""

    # startup
    physics_material = EventTerm(
        func=mdp.randomize_rigid_body_material,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names=".*"),
            "static_friction_range": (0.5, 4.0),
            "dynamic_friction_range": (0.5, 2.0),
            "restitution_range": (0.0, 0.0),
            "num_buckets": 64,
        },
    )

    add_base_mass = EventTerm(
        func=mdp.randomize_rigid_body_mass,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="base"),
            "mass_distribution_params": (-3.0, 3.0),
            "operation": "add",
        },
    )

    add_ee_mass = EventTerm(
        func=mdp.randomize_rigid_body_mass,
        mode="startup",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="gripper_link"),
            "mass_distribution_params": (-0.1, 0.5),
            "operation": "add",
        },
    )

    # reset
    base_external_force_torque = EventTerm(
        func=mdp.apply_external_force_torque,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot", body_names="base"),
            "force_range": (0.0, 0.0),
            "torque_range": (-0.0, 0.0),
        },
    )

    reset_base = EventTerm(
        func=mdp.reset_root_state_uniform,
        mode="reset",
        params={
            "pose_range": {"x": (-0.5, 0.5), "y": (-0.5, 0.5), "yaw": (-3.14, 3.14)},
            "velocity_range": {
                "x": (-0.5, 0.5),
                "y": (-0.5, 0.5),
                "z": (-0.5, 0.5),
                "roll": (-0.5, 0.5),
                "pitch": (-0.5, 0.5),
                "yaw": (-0.5, 0.5),
            },
        },
    )
    
    actuator_gains = EventTerm(
        func=mdp.randomize_actuator_gains,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot", joint_names=".*"),
            "stiffness_distribution_params": (0.8, 1.2),
            "damping_distribution_params": (0.8, 1.2),
            "operation": "scale",
        },
    )

    reset_robot_joints = EventTerm(
        func=mdp.reset_joints_by_scale,
        mode="reset",
        params={
            "position_range": (0.5, 1.5),
            "velocity_range": (0.0, 0.0),
        },
    )

    # interval
    # push_robot = EventTerm(
    #     func=mdp.push_by_setting_velocity,
    #     mode="interval",
    #     interval_range_s=(10.0, 15.0),
    #     params={"velocity_range": {"x": (-0.5, 0.5), "y": (-0.5, 0.5)}},
    # )

##
# MDP settings
##

@configclass
class CommandsCfg:
    """Command specifications for the MDP."""
    ## Go2ARM

    ee_pose = commands_cfg.UniformPoseCommandCfg(
        asset_name="robot",
        body_name="gripper_link",
        resampling_time_range=(6.0,8.0),
        debug_vis=True,
        is_Go2ARM=True,
        curriculum_coeff = 1000,      # Optimal accuracy is achieved at num_env=4096, while other settings may lead to suboptimal results.         
        ranges_final =commands_cfg.UniformPoseCommandCfg.Ranges(
            pos_x=(0.4, 0.6),
            pos_y=(-0.35, 0.35),
            pos_z=(0.1, 0.55), # world frame not base frame
            roll=(-0.0, 0.0),
            pitch=(-3.14 / 9, 3.14 / 9),  # depends on end-effector axis
            yaw=(-3.14 / 9, 3.14 / 9),
        ),
        ranges = commands_cfg.UniformPoseCommandCfg.Ranges(
            pos_x=(0.4, 0.6),
            pos_y=(-0.35, 0.35),
            pos_z=(0.1, 0.55), # world frame not base frame
            roll=(-0.0, 0.0),
            pitch=(-3.14 / 9, 3.14 / 9),  # depends on end-effector axis
            yaw=(-3.14 / 9, 3.14 / 9),
        ),
        ranges_init=commands_cfg.UniformPoseCommandCfg.Ranges(
            pos_x=(0.45, 0.5), 
            pos_y=(-0.05, 0.05),
            pos_z=(0.35, 0.4), # world frame not base frame
            roll=(-0.0, 0.0),
            pitch=(-0.0, 0.0),  # depends on end-effector axis
            yaw=(-0.0, 0.0),
        ),
    )

    base_velocity = commands_cfg.UniformVelocityCommandCfg(
        asset_name="robot",
        resampling_time_range=(10.0, 10.0),
        rel_standing_envs=0.1,
        debug_vis=True,
        is_Go2ARM=True,
        curriculum_coeff= 1000,     # Optimal accuracy is achieved at num_env=4096, while other settings may lead to suboptimal results.        
        ranges=commands_cfg.UniformVelocityCommandCfg.Ranges(
            lin_vel_x=(0.2, 1.0), lin_vel_y=(-0.5, 0.5), ang_vel_z=(-0.5, 0.5),heading=(-0.0, 0.0)
        ),
        ranges_final=commands_cfg.UniformVelocityCommandCfg.Ranges(
            lin_vel_x=(0.1, 0.8), lin_vel_y=(-0.5, 0.5), ang_vel_z=(-0.5, 0.5),heading=(-0.0, 0.0)
        ),
        ranges_init=commands_cfg.UniformVelocityCommandCfg.Ranges(
            lin_vel_x=(0.1, 0.35), lin_vel_y=(-0.1, 0.1), ang_vel_z=(-0.1, 0.1),heading=(-0.0, 0.0)
        ),
    )

@configclass
class ActionsCfg:
    """Action specifications for the MDP."""
    joint_pos = mdp.JointPositionActionCfg(asset_name="robot", 
                                           joint_names=[
                                                    "FR_hip_joint", "FR_thigh_joint", "FR_calf_joint",
                                                    "FL_hip_joint", "FL_thigh_joint", "FL_calf_joint",
                                                    "RR_hip_joint", "RR_thigh_joint", "RR_calf_joint",
                                                    "RL_hip_joint", "RL_thigh_joint", "RL_calf_joint",
                                                    ],
                                           scale = {"FR_hip_joint": 0.25, "FR_thigh_joint": 0.25, "FR_calf_joint": 0.25,
                                                    "FL_hip_joint": 0.25, "FL_thigh_joint": 0.25, "FL_calf_joint": 0.25,
                                                    "RR_hip_joint": 0.25, "RR_thigh_joint": 0.25, "RR_calf_joint": 0.25,
                                                    "RL_hip_joint": 0.25, "RL_thigh_joint": 0.25, "RL_calf_joint": 0.25,}, 
                                         use_default_offset=True,
                                         preserve_order=True,
    )   
    arm_pose = mdp.JointPositionActionCfg(asset_name="robot",
                                          joint_names=[
                                              "waist", "shoulder", "elbow", 
                                              "forearm_roll", "wrist_angle", "wrist_rotate"],
                                           scale = {"waist":        0.5, # 0.8
                                                    "shoulder":     0.5, # 0.35
                                                    "elbow":        0.5, # 0.35
                                                    "forearm_roll": 0.5, # 0.35
                                                    "wrist_angle":  0.5, # 0.35
                                                    "wrist_rotate": 0.5}, # 0.35
                                            use_default_offset=True,
                                            preserve_order=True,
    )


@configclass
class ObservationsCfg:
    """Observation specifications for the MDP."""

    @configclass
    class PolicyCfg(ObsGroup):
        """Observations for policy group."""
        # observation terms (order preserved)
        base_ang_vel = ObsTerm(func=observations.base_ang_vel, history_length=10,noise=Unoise(n_min=-0.1, n_max=0.1))  # dim = 3
        joint_pos = ObsTerm(func=observations.joint_pos_rel, history_length=10,noise=Unoise(n_min=-0.01, n_max=0.01)) # dim = 20 - 2
        joint_vel = ObsTerm(func=observations.joint_vel_rel, history_length=10, noise=Unoise(n_min=-0.5, n_max=0.5)) # dim = 20 - 2
        actions = ObsTerm(func=observations.last_action, history_length=10) # dim = 18
        velocity_commands = ObsTerm(func=observations.generated_commands, history_length=10,
                                    params={"command_name": "base_velocity"}) # dim = 3
        Go2_pose_command = ObsTerm(func=observations.generated_commands, history_length=10,
                                   params={"command_name": "ee_pose"}) # dim = 7
        projected_gravity = ObsTerm(
            func=observations.projected_gravity,
            noise=Unoise(n_min=-0.1, n_max=0.1),
            history_length=10
        )        # dim = 3
        
        # priv 
        # must have a prefix of "priv_". 
        # priv_base_orientation = ObsTerm(func=observations.root_yaw_angle_w) # dim = 1
        priv_mass_base = ObsTerm(func=observations.get_mass_base)# dim = 1
        priv_mass_ee = ObsTerm(func=observations.get_mass_ee) # dim = 1
        priv_joint_torques = ObsTerm(func=observations.get_joints_torques) # dim = 18
        priv_base_lin_vel = ObsTerm(func=observations.base_lin_vel)  # dim = 3
        priv_feet_contact = ObsTerm(func=observations.feet_contact,
                               params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot")}) # dim = 4 bool
        # more priv_obs:
        # priv_xxx = xxx
        
        def __post_init__(self):
            self.enable_corruption = True
            self.concatenate_terms = True
        
    # observation groups
    policy: PolicyCfg = PolicyCfg()


@configclass
class RewardsCfg:
    """Reward terms for the MDP."""

    # -- ARM 
    # The name must have a prefix of "end_effector_".
    end_effector_position_tracking = RewTerm(
        func=rewards.Go2_position_command_error_exp,
        weight=2.5,
        params={"asset_cfg": SceneEntityCfg("robot", body_names="gripper_link"),
                "command_name": "ee_pose",
                "std": 0.2},
    )

    end_effector_orientation_tracking = RewTerm(
        func=rewards.GO2_orientation_command_error,
        weight=-1.5,
        params={"asset_cfg": SceneEntityCfg("robot", body_names="gripper_link"), 
                "command_name": "ee_pose"},
    )

    end_effector_action_rate = RewTerm(func=rewards.action_rate_l2_arm, weight=-0.005)

    end_effector_action_smoothness = RewTerm(func=rewards.arm_action_smoothness_penalty, weight=-0.02)

    # more rewards
    # end_effector_xxx = xxx


    # -- LEG
    tracking_lin_vel_x_l1 = RewTerm(
        func=rewards.track_lin_vel_xy_exp, 
        weight=1.5, 
        params={
                "command_name": "base_velocity", 
                "std":0.2}
    )
    track_ang_vel_z_exp = RewTerm(
        func=rewards.track_ang_vel_z_exp, 
        weight=1.5,
         params={ 
                 "command_name": "base_velocity", 
                 "std": math.sqrt(0.2)}
    )

    lin_vel_z_l2 = RewTerm(func=rewards.lin_vel_z_l2, weight=-2.5)
    ang_vel_xy_l2 = RewTerm(func=rewards.ang_vel_xy_l2, weight=-0.02) # -0.05
    dof_torques_l2 = RewTerm(func=rewards.joint_torques_l2_Go2, weight=-2.0e-5) # - 0.0002
    dof_acc_l2 = RewTerm(func=rewards.joint_acc_l2_Go2, weight=-2.5e-7)
    action_rate_l2 = RewTerm(func=rewards.action_rate_l2_Go2, weight=-0.01)

    F_feet_air_time = RewTerm(
        func=rewards.feet_air_time,
        weight= 0.5,
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_foot"),
            "command_name": "base_velocity",
            "threshold": 0.5,
        },
    )

    # F_feet_air_time = RewTerm(
    #     func=rewards.feet_air_time,
    #     weight= 0.5,
    #     params={
    #         "sensor_cfg": SceneEntityCfg("contact_forces", body_names="F.*_foot"),
    #         "command_name": "base_velocity",
    #         "threshold": 0.5,
    #     },
    # )
    # R_feet_air_time = RewTerm(
    #     func=rewards.feet_air_time,
    #     weight= 2.0,
    #     params={
    #         "sensor_cfg": SceneEntityCfg("contact_forces", body_names="R.*_foot"),
    #         "command_name": "base_velocity",
    #         "threshold": 0.5,
    #     },
    # )

    foot_contact = RewTerm(
        func=rewards.standing_feet_contact_force,
        weight= 0.003,
        params={
            "sensor_cfg": SceneEntityCfg("contact_forces", body_names="R.*_foot"),
            "command_name": "base_velocity",
            "force_threshold": 7.5,
            "command_threshold": 0.1,
        },
    )

    hip_deviation = RewTerm(
        func=rewards.joint_deviation_l1,
        weight=-0.4,
        # params={"asset_cfg": SceneEntityCfg("robot", joint_names=[".*_hip_joint", ".*_thigh_joint", ".*_calf_joint"])},
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=[".*_hip_joint"])},
    )

    joint_deviation = RewTerm(
        func=rewards.joint_deviation_l1,
        weight=-0.04,
        params={"asset_cfg": SceneEntityCfg("robot", joint_names=[".*_thigh_joint", ".*_calf_joint"])},
    )

    action_smoothness = RewTerm(
        func=rewards.leg_action_smoothness_penalty,
        weight=-0.02,
    )

    height_reward = RewTerm(func=rewards.base_height_l2, weight=-2.0, params={"target_height": 0.3})

    flat_orientation_l2 = RewTerm(func=rewards.flat_orientation_l2, weight=-1.0)
   
   
    # thigh_contact = RewTerm(
    #     func=rewards.undesired_contacts,
    #     weight=-2.0,
    #     params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_thigh"), "threshold": 0.5},
    # )

    # calf_contact = RewTerm(
    #     func=rewards.undesired_contacts,
    #     weight=-2.0,
    #     params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_calf"), "threshold": 0.5},
    # )

    # arm_contact = RewTerm(
    #     func=rewards.undesired_contacts,
    #     weight=-2.0,
    #     params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_link"), "threshold": 0.5},
    # )

@configclass
class TerminationsCfg:
    """Termination terms for the MDP."""

    time_out = DoneTerm(func=mdp.time_out, time_out=True)
    base_contact = DoneTerm(
        func=mdp.illegal_contact,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names="base"), "threshold": 0.5},
    )
    thigh_contact = DoneTerm(
        func=mdp.illegal_contact,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_thigh"), "threshold":0.5},
    )
    arm_contact = DoneTerm(
        func=mdp.illegal_contact,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_link"), "threshold": 0.5},
    )
    calf_contact = DoneTerm(
        func=mdp.illegal_contact,
        params={"sensor_cfg": SceneEntityCfg("contact_forces", body_names=".*_calf"), "threshold": 0.5},
    )



@configclass
class CurriculumCfg:
    """Curriculum terms for the MDP."""

    # terrain_levels = CurrTerm(func=mdp.terrain_levels_vel)
    flat_ori_modify = CurrTerm(func=mdp.modify_reward_weight,
                               params={"term_name": "flat_orientation_l2",
                                       "num_steps": 2000,
                                       "weight": -0.05})


##
# Environment configuration
##


@configclass
class LocomotionVelocityRoughEnvCfg(ManagerBasedRLEnvCfg):
    """Configuration for the locomotion velocity-tracking environment."""

    # Scene settings
    scene: MySceneCfg = MySceneCfg(num_envs=4096, env_spacing=2.5)
    # Basic settings
    observations: ObservationsCfg = ObservationsCfg()
    actions: ActionsCfg = ActionsCfg()
    commands: CommandsCfg = CommandsCfg()
    # MDP settings
    rewards: RewardsCfg = RewardsCfg()
    terminations: TerminationsCfg = TerminationsCfg()
    events: EventCfg = EventCfg()
    curriculum: CurriculumCfg = CurriculumCfg()
    def __post_init__(self):
        """Post initialization."""
        # general settings
        self.decimation = 4
        self.episode_length_s = 20.0
        # simulation settings
        self.sim.dt = 0.005
        self.sim.render_interval = self.decimation
        self.sim.disable_contact_processing = True
        self.sim.physics_material = self.scene.terrain.physics_material
        # update sensor update periods
        # we tick all the sensors based on the smallest update period (physics update period)
        if self.scene.height_scanner is not None:
            self.scene.height_scanner.update_period = self.decimation * self.sim.dt
        if self.scene.contact_forces is not None:
            self.scene.contact_forces.update_period = self.sim.dt

        # check if terrain levels curriculum is enabled - if so, enable curriculum for terrain generator
        # this generates terrains with increasing difficulty and is useful for training
        if getattr(self.curriculum, "terrain_levels", None) is not None:
            if self.scene.terrain.terrain_generator is not None:
                self.scene.terrain.terrain_generator.curriculum = True
        else:
            if self.scene.terrain.terrain_generator is not None:
                self.scene.terrain.terrain_generator.curriculum = False
