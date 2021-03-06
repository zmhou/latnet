

import time
from copy import copy
import os
from termcolor import colored, cprint
import tensorflow as tf
import numpy as np
from tqdm import *

import lattice
import nn as nn

from shape_converter import ShapeConverter
from optimizer import Optimizer
from shape_converter import SubDomain
from network_saver import NetworkSaver
from data_queue import DataQueue
from utils.python_utils import *

class Trainer(object):
  # default network name
  #network_name = 'advanced_network'

  def __init__(self, config):
    # in and out tensors
    self.config = config # TODO remove this when config is corrected
    self.DxQy = lattice.TYPES[config.DxQy]()
    self.network_dir  = config.latnet_network_dir
    self.seq_length = config.seq_length
    self.gan = config.gan
    self.train_autoencoder = config.train_autoencoder
    self.train_iters = config.train_iters
    gpus = config.gpus.split(',')
    self.gpus = map(int, gpus)
    self.loss_stats = {}
    self.time_stats = {}
    self.start_time = time.time()
    self.tic = time.time()
    self.toc = time.time()
    self.stats_history_length = 300

  @classmethod
  def add_options(cls, group, network_name):
    pass

  def init_network(self):
    self._network = self.network(self.config)
    self._network.train_unroll()

  def make_data_queue(self):
    # add script name to domains
    for domain in self.domains:
      domain.script_name = self.script_name
    self.data_queue = DataQueue(self.config, self.domains, self._network.train_shape_converter())

  def train(self):
 
    # steps per print (hard set for now untill done debugging)
    steps_per_print = 20

    while True: 
      # get batch of data
      feed_dict = self.data_queue.minibatch()
      feed_dict['phase'] = 1

      # perform optimization step for gen
      gen_names = ['gen_train_op', 'loss_gen']
      if not self.gan:
        if self.train_autoencoder:
          gen_names += ['loss_auto_l2']
        gen_names += ['loss_comp_l2']
      if self.gan:
        gen_names += ['loss_l1', 'loss_gen_un_class', 'loss_layer_l2', 'loss_gen_con_class']
      gen_output = self._network.run(gen_names, feed_dict=feed_dict, return_dict=True)
      if self.gan:
        disc_names = ['disc_train_op', 'loss_disc', 'loss_disc_un_class', 'loss_disc_con_class']
        disc_output = self._network.run(disc_names, feed_dict=feed_dict, return_dict=True)
        gen_output.update(disc_output)
         
      # update loss summary
      self.update_loss_stats(gen_output)

      # update time summary
      self.update_time_stats()

      # print required data and save
      step = self._network.run('gen_global_step')
      if step % steps_per_print == 0:
        self.print_stats(self.loss_stats, self.time_stats, self.data_queue.queue_stats(), step)
        # TODO integrat this into self.saver
        tf_feed_dict = {}
        for name in feed_dict.keys():
          if type(feed_dict[name]) is tuple:
            tf_feed_dict[self._network.in_tensors[name]] = feed_dict[name][0]
            tf_feed_dict[self._network.in_pad_tensors[name]] = feed_dict[name][1]
          else:
            tf_feed_dict[self._network.in_tensors[name]] = feed_dict[name]
        ###
        self._network.saver.save_summary(self._network.sess, tf_feed_dict, int(self._network.run('gen_global_step')))

      if step % self.config.save_network_freq == 0:
        self._network.saver.save_checkpoint(self._network.sess, int(self._network.run('gen_global_step')))

      if step % 400 == 0:
        print("getting new data")
        self.active_data_add()

      # end simulation
      if step > self.train_iters:
        break

  def active_data_add(self):
    # TODO this should be cleaned up
    loss_data_point_pair = []
    for i in tqdm(xrange(200)):
      sim_index, data_point, feed_dict = self.data_queue.rand_data_point()
      loss_names = ['loss_gen']
      loss_output = self._network.run(loss_names, feed_dict=feed_dict, return_dict=True)
      loss_data_point_pair.append((loss_output['loss_gen'], sim_index, data_point))

    loss_data_point_pair.sort() 
    for i in xrange(40):
      self.data_queue.add_data_point(loss_data_point_pair[-i][1], loss_data_point_pair[-i][2])

  def update_loss_stats(self, output):
    names = output.keys()
    names.sort()
    for name in names:
      if 'loss' in name:
        # update loss history
        if name + '_history' not in self.loss_stats.keys():
          self.loss_stats[name + '_history'] = []
        self.loss_stats[name + '_history'].append(output[name])
        if len(self.loss_stats[name + '_history']) > self.stats_history_length:
          self.loss_stats[name + '_history'].pop(0)
        # update loss
        self.loss_stats[name] = float(output[name])
        # update ave loss
        self.loss_stats[name + '_ave'] = float(np.sum(np.array(self.loss_stats[name + '_history']))
                                         / len(self.loss_stats[name + '_history']))
        # update var loss
        self.loss_stats[name + '_std'] = np.sqrt(np.var(np.array(self.loss_stats[name + '_history'])))

  def update_time_stats(self):
    # stop timer
    self.toc = time.time()
    # update total run time
    self.time_stats['run_time'] = int(time.time() - self.start_time)
    # update total step time
    self.time_stats['step_time'] = ((self.toc - self.tic) / 
                                    (self.config.batch_size * len(self.config.gpus)))
    # update time history
    if 'step_time_history' not in self.time_stats.keys():
      self.time_stats['step_time_history'] = []
    self.time_stats['step_time_history'].append(self.time_stats['step_time'])
    if len(self.time_stats['step_time_history']) > self.stats_history_length:
      self.time_stats['step_time_history'].pop(0)
    # update time ave
    self.time_stats['step_time_ave'] = float(np.sum(np.array(self.time_stats['step_time_history']))
                   / len(self.time_stats['step_time_history']))
    # start timer
    self.tic = time.time()

  def print_stats(self, loss_stats, time_stats, queue_stats, step):
    loss_string = print_dict('LOSS STATS', loss_stats, 'blue')
    time_string = print_dict('TIME STATS', time_stats, 'magenta')
    queue_string = print_dict('QUEUE STATS', queue_stats, 'yellow')
    print_string = loss_string + time_string + queue_string
    os.system('clear')
    print("TRAIN INFO - step " + str(step))
    print(print_string)

