
import sys
import time

import matplotlib.pyplot as plt


# import latnet files
import utils.numpy_utils as numpy_utils
from shape_converter import SubDomain

# import sailfish
sys.path.append('../sailfish')
from sailfish.subdomain import Subdomain2D
from sailfish.node_type import NTEquilibriumVelocity, NTFullBBWall, NTDoNothing

# import external librarys
import numpy as np
import math
import itertools
from tqdm import *
from copy import copy


class Domain(object):

  def __init__(self, config):
    self.config = config

  @classmethod
  def update_defaults(cls, defaults):
      pass

  def geometry_boundary_conditions(self, hx, hy, shape):
    pass

  def velocity_boundary_conditions(self, hx, hy, shape):
    pass

  def density_boundary_conditions(self, hx, hy, shape):
    pass

  def velocity_initial_conditions(self, hx, hy, shape):
    pass

  def density_initial_conditions(self, hx, hy, shape):
    pass

  def make_geometry_input(self, where_boundary, velocity, where_velocity, density, where_density):
    # TODO Clean this
    input_geometry = np.concatenate([np.expand_dims(where_boundary, axis=-1).astype(np.float32),
                                     np.array(velocity).reshape(len(where_velocity.shape) * [1] + [2]) 
                                       * np.expand_dims(where_velocity, axis=-1).astype(np.float32),
                                     density 
                                       *  np.expand_dims(where_density, axis=-1).astype(np.float32)], axis=-1)
    return input_geometry

  def make_sailfish_subdomain(self):

    where_boundary = geometry_boundary_conditions(hx, hy, [self.gx, self.gy])
          where_velocity, velocity = velocity_boundary_conditions(hx, hy, [self.gx, self.gy])
          where_density, density = density_boundary_conditions(hx, hy, [self.gx, self.gy])
    

    class SailfishSubdomain(Subdomain2D):
      
      bc = NTFullBBWall

      def boundary_conditions(self, hx, hy):

        # restore from old dir or make new geometry
        if self.config.restore_geometry:
          restore_boundary_conditions = np.load(train_sim_dir[:-10] + "flow_geometry.npy")
          where_boundary = restore_boundary_conditions[...,0].astype(np.bool)
          where_velocity = np.logical_or(restore_boundary_conditions[...,1].astype(np.bool), restore_boundary_conditions[...,1].astype(np.bool))
          velocity = (restore_boundary_conditions[np.where(where_velocity)[0][0], np.where(where_velocity)[1][0], 1],
                      restore_boundary_conditions[np.where(where_velocity)[0][0], np.where(where_velocity)[1][0], 2])
          where_density  = restore_boundary_conditions[...,3].astype(np.bool)
          density = 1.0
        else:
          where_boundary = geometry_boundary_conditions(hx, hy, [self.gx, self.gy])
          where_velocity, velocity = velocity_boundary_conditions(hx, hy, [self.gx, self.gy])
          where_density, density = density_boundary_conditions(hx, hy, [self.gx, self.gy])

        # set boundarys
        self.set_node(where_boundary, self.bc)

        # set velocities
        self.set_node(where_velocity, NTEquilibriumVelocity(velocity))

        # set densitys
        self.set_node(where_density, NTDoNothing)

        # save geometry
        save_geometry = make_geometry_input(where_boundary, velocity, where_velocity, density, where_density)
        np.save(train_sim_dir + "_geometry.npy", save_geometry)

      def initial_conditions(self, sim, hx, hy):
        # set start density
        rho = density_initial_conditions(hx, hy,  [self.gx, self.gy])
        sim.rho[:] = rho

        # set start velocity
        vel = velocity_initial_conditions(hx, hy,  [self.gx, self.gy])
        sim.vx[:] = vel[0]
        sim.vy[:] = vel[1]

    return SailfishSubdomain
   

