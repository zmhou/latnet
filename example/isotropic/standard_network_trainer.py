#!/usr/bin/env python

import sys
import os
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# import domains
from isotropic_flow import IsotropicDomain

# import latnet
sys.path.append('../../latnet')
from domain import Domain
from controller import LatNetController
from trainer import Trainer
from network_architectures.standard_network import StandardNetwork
import numpy as np
import cv2
import glob

class StandardTrainer(Trainer):
  script_name = __file__
  network = StandardNetwork
  domains = [IsotropicDomain]

  @classmethod
  def update_defaults(cls, defaults):
    defaults.update({
        'train_sim_dir': './train_data',
        'latnet_network_dir': './network_save',
        'visc': 0.01,
        'lb_to_ln': 128,
        'input_cshape': '16x16',
        'max_sim_iters': 100})

if __name__ == '__main__':
  sim = LatNetController(trainer=StandardTrainer)
  sim.run()

