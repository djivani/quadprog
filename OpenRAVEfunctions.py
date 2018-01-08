# -*- coding: utf-8 -*-
"""
Created on Mon Dec  4 12:16:39 2017

@author: yc
"""

#! /usr/bin/env python
import numpy as np
import math
from openravepy import *
import rospy
from openravepy.misc import *

def rotx(theta):
  M = np.matrix([[1,0,0], [0, np.cos(theta), -np.sin(theta)], [0, np.sin(theta), np.cos(theta)]])
  return M

def roty(theta):
  M = np.matrix([[np.cos(theta), 0, np.sin(theta)], [0,1,0], [-np.sin(theta), 0, np.cos(theta)]])
  return M

def rotz(theta):
  M = np.matrix([[np.cos(theta), -np.sin(theta), 0], [np.sin(theta), np.cos(theta), 0], [0,0,1]])
  return M


def translation_matrix(direction):
    """Return matrix to translate by direction vector.

    >>> v = numpy.random.random(3) - 0.5
    >>> numpy.allclose(v, translation_matrix(v)[:3, 3])
    True

    """
    M = np.identity(4)
    M[:3, 3] = direction[:3]
    return M

def quaternion_matrix(quaternion):
    """Return homogeneous rotation matrix from quaternion.

    >>> M = quaternion_matrix([0.99810947, 0.06146124, 0, 0])
    >>> numpy.allclose(M, rotation_matrix(0.123, [1, 0, 0]))
    True
    >>> M = quaternion_matrix([1, 0, 0, 0])
    >>> numpy.allclose(M, numpy.identity(4))
    True
    >>> M = quaternion_matrix([0, 1, 0, 0])
    >>> numpy.allclose(M, numpy.diag([1, -1, -1, 1]))
    True

    """
    q = np.array(quaternion, dtype=np.float64, copy=True)
    n = np.dot(q, q)
    if n < _EPS:
        return np.identity(4)
    q *= math.sqrt(2.0 / n)
    q = np.outer(q, q)
    return np.array([
        [1.0-q[2, 2]-q[3, 3],     q[1, 2]-q[3, 0],     q[1, 3]+q[2, 0], 0.0],
        [    q[1, 2]+q[3, 0], 1.0-q[1, 1]-q[3, 3],     q[2, 3]-q[1, 0], 0.0],
        [    q[1, 3]-q[2, 0],     q[2, 3]+q[1, 0], 1.0-q[1, 1]-q[2, 2], 0.0],
        [                0.0,                 0.0,                 0.0, 1.0]])
        

def FK_Matrix2(J):
  R01 = rotz(J[0])
  R12 = roty(J[1])
  R23 = roty(J[2])
  R34 = rotx(J[3])
  R45 = roty(J[4])
  R56 = rotx(J[5])
  R06 = np.dot(R01, np.dot(R12, np.dot(R23, np.dot(R34, np.dot(R45,R56)))))
  p12 = np.array([0.32,0,0.78]).reshape(3,1)
  p23 = np.array([0,0,1.075]).reshape(3,1)
  p34 = np.array([1.392,0,0.2]).reshape(3,1)
  p6T = np.array([0.15,0, -0.1]).reshape(3,1)
  p0T = np.dot(R01,p12) + np.dot(R01, np.dot(R12,p23)) + np.dot(R01, np.dot(R12,np.dot(R23,p34))) + np.dot(R06,p6T) + np.array([0.13,0, -0.40]).reshape(3,1)
  return np.dot(translation_matrix(p0T.flatten().tolist()[0]), np.r_[np.c_[R06,[0,0,0]],np.array([0,0,0,1]).reshape(1,4)].tolist())


class CollisionChecker:

  def __init__(self, gui=False):
    self.load_env()
    self.load_viewer(gui)
    self.load_distance_checker()
    rospy.loginfo('[CollisionChecker] Initialization finished.')

  def load_env(self):

    self.env = Environment()
    module = RaveCreateModule(self.env, 'urdf')

    self.bodies = {}
    self.joints = {}
    
    #urdf_folder = rospkg.RosPack().get_path('abb_irb6640_support')+'/urdf/'
    urdf_folder = '/home/Shuyang/catkin_ws/src/irb6640/irb6640_description/urdf/'
    
    #names = ['irb6640_185_280_Testbed', 'ball']
    #urdfs = ['irb6640_185_280_or', 'ball']
    #names = ['robot', 'Walls']
    #urdfs = ['irb6640', 'Walls_or']
    
    names = ['irb6640_185_280_Testbed', 'Walls']
    urdfs = ['irb6640_185_280_or', 'Walls_or']
    
    model_urdf = {}
    for name, urdf in zip(names, urdfs):
      model_urdf[name] = urdf

    with self.env:
      for name in model_urdf:
        urdf = model_urdf[name]
        if urdf == 'box':
          body = RaveCreateKinBody(self.env, '')
          body.SetName(name)
          #body.SetName(urdf)
          body.InitFromBoxes(np.array([[0, 0, 0, 0.1, 0.1, 0.1]]), True) #0.6096, 0.01524, 0.3048
          
        elif urdf == 'ball':
          body = RaveCreateKinBody(self.env, '')
          body.SetName(name)
          body.InitFromSpheres(np.array([[0, 0, 0, 0.2]]), True) #0.6096, 0.01524, 0.3048
          
        else:
          body = self.env.GetKinBody(module.SendCommand('LoadURI '+urdf_folder+urdf+'.urdf'))
          
        self.env.AddKinBody(body)
        self.bodies[name] = body
        self.joints[name] = [ joint.GetName() for joint in body.GetJoints() ]
    
  def load_viewer(self, gui=False):
    if gui:
      #SetViewerUserThread(self.env,'qtcoin',self.do_nothing)
      self.env.SetViewer('qtcoin')

  def load_distance_checker(self):
    with self.env:
      options = CollisionOptions.Distance|CollisionOptions.Contacts
      if not self.env.GetCollisionChecker().SetCollisionOptions(options):
        rospy.loginfo('[CollisionChecker] Switching to pqp for collision distance information.')
        
        # pqp collision checker
        collisionChecker = RaveCreateCollisionChecker(self.env,'pqp')
        collisionChecker.SetCollisionOptions(options)
        self.env.SetCollisionChecker(collisionChecker)
        print collisionChecker

  def check_safety(self, collision_poi, collision_env, joints=[]):

    # Find out background objects
    background = [ x for x in collision_env if x not in collision_poi ]

    # Update background transforms
    for bkg in background:
      if bkg in self.bodies:
        self.bodies[bkg].SetTransform(collision_env[bkg])

    # Update point of interest transforms
    for poi in collision_poi:
      if poi in self.bodies:
        self.bodies[poi].SetTransform(collision_poi[poi])
        #bodyexcluded.append(self.bodies[poi])

    # Update joint values
    for jnt in joints:
      if jnt in self.bodies:
        self.bodies[jnt].SetDOFValues(joints[jnt])

    # Check collisions
    report = CollisionReport()
    
    """ """
    report_2 = CollisionReport()
    
    ClosestPosition = [0,0]
    ContactCnt = 0
    minDistance = np.infty
    
    with self.env:
      for poi in collision_poi:
        #for bkg in background + ['floor']:
        for bkg in background:
          # return True if collision happens
          if self.env.CheckCollision(link1=self.bodies[poi], link2=self.bodies[bkg], report=report):
            return False, report.minDistance
          elif minDistance > report.minDistance:
            minDistance = report.minDistance
            ClosestPosition = report.contacts[0].pos
            
            """ """
            self.env.CheckCollision(link1=self.bodies[bkg], link2=self.bodies[poi], report=report)
            # closest point in the environment
            ClosestPosition_env = report.contacts[0].pos
            
            ContactCnt = len(report.contacts)
    # plot will not work here since the environment is locked with "with self.env" above
    """      
    handles = []
      
    handles.append(self.env.plot3(points=np.array(ClosestPosition),#ClosestPosition,
                   pointsize=20,
                   colors=np.array((0,0,1))))
    """
          
    """ """           
    return True, minDistance, ClosestPosition, ClosestPosition_env, ContactCnt
    

_EPS = np.finfo(float).eps * 4.0