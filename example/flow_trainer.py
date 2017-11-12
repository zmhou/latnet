#!/usr/bin/env python

import sys

# import latnet
sys.path.append('../latnet')
from domain import Domain
from controller import LatNetController
import utils.binvox_rw as binvox_rw
import numpy as np
import glob

def rand_vel(max_vel=.10, min_vel=.09):
  vel = np.random.uniform(min_vel, max_vel)
  angle = np.random.uniform(-np.pi/2, np.pi/2)
  vel_x = vel * np.cos(angle)
  vel_y = vel * np.sin(angle)
  return (vel_x, vel_y)

def floodfill(image, x, y):
    edge = [(x, y)]
    image[x,y] = -1
    while edge:
        newedge = []
        for (x, y) in edge:
            for (s, t) in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
                if     ((0 <= s) and (s < image.shape[0])
                   and (0 <= t) and (t < image.shape[1])
                   and (image[s, t] == 0)):
                    image[s, t] = -1 
                    newedge.append((s, t))
        edge = newedge

def make_boundary(hx):
  boundary = (hx == -2)
  all_vox_files = glob.glob('../data/train/**/*.binvox')
  num_file_try = np.random.randint(2, 6)
  for i in xrange(num_file_try):
    file_ind = np.random.randint(0, len(all_vox_files))
    with open(all_vox_files[file_ind], 'rb') as f:
      model = binvox_rw.read_as_3d_array(f)
      model = model.data[:,:,model.dims[2]/2]
    model = np.array(model, dtype=np.int)
    model = np.pad(model, ((1,1),(1, 1)), 'constant', constant_values=0)
    floodfill(model, 0, 0)
    model = np.greater(model, -0.1)

    pos_x = np.random.randint(1, hx.shape[0]-model.shape[0]-1)
    pos_y = np.random.randint(1, hx.shape[1]-model.shape[1]-1)
    boundary[pos_x:pos_x+model.shape[0], pos_y:pos_y+model.shape[0]] = model | boundary[pos_x:pos_x+model.shape[0], pos_y:pos_y+model.shape[0]]

  return boundary

class TrainDomain(Domain):
  script_name = __file__
  max_v = 0.1
  vel = rand_vel()

  def geometry_boundary_conditions(self, hx, hy, shape):
    walls = (hx == -2)
    #y_wall = np.random.randint(0,2)
    #if y_wall == 0:
    #  walls = (hy == 0) | (hy == shape[0] - 1) | walls
    obj_boundary = make_boundary(hx)
    where_boundary = walls | obj_boundary
    return where_boundary

  def velocity_boundary_conditions(self, hx, hy, shape):
    #where_velocity = (hx == 0) & np.logical_not(walls)
    where_velocity = (hx == 0)
    velocity = self.vel
    return where_velocity, velocity
 
  def density_boundary_conditions(self, hx, hy, shape):
    #where_density = (hx == shape[0] - 1) & np.logical_not(walls)
    where_density = (hx == shape[0] - 1)
    density = 1.0
    return where_density, density

  def velocity_initial_conditions(self, hx, hy, shape):
    velocity = self.vel
    return velocity

  def density_initial_conditions(self, hx, hy, shape):
    rho = 1.0
    return rho


  def __init__(self, *args, **kwargs):
    super(TrainDomain, self).__init__(*args, **kwargs)

if __name__ == '__main__':
  sim = LatNetController(train_sim=TrainDomain)
  sim.run()
    

