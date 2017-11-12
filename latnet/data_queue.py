
import numpy as np
import matplotlib.pyplot as plt
from lxml import etree
import glob
from tqdm import *
import sys
import os.path
import gc
import skfmm
import time
import psutil as ps
import shutil
from sim_runner import SimRunner

from Queue import Queue
import threading

class DataQueue:
  def __init__(self, config, train_sim):

    # base dir where all the xml files are
    self.base_dir = config.sailfish_sim_dir
    self.script_name = train_sim.script_name

    # configs
    self.batch_size      = config.batch_size
    self.num_simulations = config.num_simulations
    self.seq_length      = config.seq_length
    self.free_gpu        = True

    # shape
    sim_shape = config.sim_shape.split('x')
    sim_shape = map(int, sim_shape)
    self.sim_shape = sim_shape
    input_shape = config.input_shape.split('x')
    input_shape = map(int, input_shape)
    self.input_shape = input_shape

    # generate base dataset
    self.sim_runners = []
    for i in xrange(self.num_simulations):
      self.sim_runners.append(SimRunner(config, self.base_dir + 'sim_' + str(i), self.script_name))
      self.sim_runners[i].generate_cpoint()
 
    # make queue
    self.max_queue = config.max_queue
    self.queue = Queue() # to stop halting when putting on the queue
    self.queue_batches = []

    # Start threads
    for i in xrange(config.nr_threads):
      get_thread = threading.Thread(target=self.data_worker)
      get_thread.daemon = True
      get_thread.start()

  def data_worker(self):
    while True:
      sim_runner, padding_decrease_seq = self.queue.get()

      # if there is a free gpu open then run simulation farther
      if self.free_gpu:
        self.free_gpu = False
        sim_runner.generate_cpoint() 
      self.free_gpu = True

      # select random piece to grab from data
      rand_pos = [np.random.randint(0, self.sim_shape[0]), np.random.randint(0, self.sim_shape[1])]
      radius = self.input_shape[0]/2

      # get geometry and lat data
      geometry_array = sim_runner.read_geometry(rand_pos, radius)
      lat_in, lat_out = sim_runner.read_seq_states(self.seq_length, rand_pos, radius, padding_decrease_seq)

      # add to que
      self.queue_batches.append((geometry_array, lat_in, lat_out))
      self.queue.task_done()
 
  def minibatch(self, state_in=None, state_out=None, boundary=None, padding_decrease_seq=None):

    # queue up data if needed
    for i in xrange(self.max_queue - len(self.queue_batches) - self.queue.qsize()):
      sim_index = np.random.randint(0, self.num_simulations)
      self.queue.put((self.sim_runners[sim_index], padding_decrease_seq))
   
    # possibly wait if data needs time to queue up
    while len(self.queue_batches) < self.batch_size:
      print("spending time waiting for queue")
      time.sleep(1.01)

    # generate batch of data in the form of a feed dict
    batch_boundary = []
    batch_state_in = []
    batch_state_out = []
    for i in xrange(self.batch_size): 
      batch_boundary.append(self.queue_batches[0][0].astype(np.float32))
      batch_state_in.append(self.queue_batches[0][1])
      batch_state_out.append(self.queue_batches[0][2])
      self.queue_batches.pop(0)

    # concate batches together
    new_batch_state_out = []
    for i in xrange(self.seq_length):
      new_batch_state_out.append(np.stack(batch_state_out[:][i], axis=0))
    batch_state_out = new_batch_state_out
    batch_state_in = np.stack(batch_state_in, axis=0)
    batch_boundary = np.stack(batch_boundary, axis=0)
    return {boundary:batch_boundary, state_in:batch_state_in, state_out:batch_state_out}

