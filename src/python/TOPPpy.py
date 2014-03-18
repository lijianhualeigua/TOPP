# -*- coding: utf-8 -*-
# Copyright (C) 2013 Quang-Cuong Pham <cuong.pham@normalesup.org>
#
# This file is part of the Time-Optimal Path Parameterization (TOPP) library.
# TOPP is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from pylab import *
from numpy import *
import pylab
import time

from Trajectory import PiecewisePolynomialTrajectory
from Trajectory import NoTrajectoryFound

DEFAULTS = {
    'discrtimestep': 1e-2,
    'integrationtimestep': 1e-3,
    'reparamtimestep': 1e-3,
    'passswitchpointnsteps': 5,
}


################### Public interface ######################

class RaveInstance(object):
    def __init__(self, robot, traj, tau_min, tau_max, v_max,
                 discrtimestep=DEFAULTS['discrtimestep'],
                 integrationtimestep=DEFAULTS['integrationtimestep'],
                 reparamtimestep=DEFAULTS['reparamtimestep'],
                 passswitchpointnsteps=DEFAULTS['passswitchpointnsteps']):
        self.discrtimestep = discrtimestep
        self.integrationtimestep = integrationtimestep
        self.reparamtimestep = reparamtimestep
        self.passswitchpointnsteps = passswitchpointnsteps
        self.solver = None  # set by child class

    def GetTrajectory(self, sd_beg=0., sd_end=0.):
        return_code = self.solver.RunComputeProfiles(sd_beg, sd_end)
        if return_code != 1:
            raise NoTrajectoryFound

        return_code = self.solver.ReparameterizeTrajectory()
        if return_code < 0:
            raise NoTrajectoryFound

        self.solver.WriteResultTrajectory()
        traj_str = self.solver.restrajectorystring
        return PiecewisePolynomialTrajectory.FromString(traj_str)

    def GetAVP(self, sd_min, sd_max):
        return_code = self.solver.RunVIP(sd_min, sd_max)
        if return_code == 0:
            raise NoTrajectoryFound
        sd_end_min = self.solver.sdendmin
        sd_end_max = self.solver.sdendmax
        return (sd_end_min, sd_end_max)


###################### Utilities #########################

def vector2string(v):
    ndof = len(v);
    s = str(ndof)
    for a in v:
        s+= ' %f'%a
    return s


def vect2str(v):
    return ' '.join(map(str, v))


def Interpolate3rdDegree(q0, q1, qd0, qd1, T):
    a = ((qd1 - qd0) * T - 2 * (q1 - q0 - qd0 * T)) / T ** 3
    b = (3 * (q1 - q0 - qd0 * T) - (qd1 - qd0) * T) / T ** 2
    c = qd0
    d = q0
    return a, b, c, d


def Interpolate5thDegree(q0, q1, qd0, qd1, qdd0, qdd1, T):
    a = (6.0*(q1 - q0) - T*3.0*(qd1 + qd0) + (T**2)*0.5*(qdd1 - qdd0))/(T**5)
    b = (-15.0*(q1 - q0) + (7.0*qd1 + 8.0*qd0)*T - (qdd1 - 1.5*qdd0)*(T**2))/(T**4)
    c = (10.0*(q1 - q0) - (4.0*qd1 + 6.0*qd0)*T + (0.5*qdd1 - 1.5*qdd0)*(T**2))/(T**3)
    d = 0.5*qdd0
    e = qd0
    f = q0
    return a, b, c, d, e, f


def BezierToPolynomial(T, p0, p1, p2, p3):
    a = -p0 + 3 * p1 - 3 * p2 + p3
    b = 3 * p0 - 6 * p1 + 3 * p2
    c = -3 * p0 + 3 * p1
    d = p0
    return a / (T * T * T), b / (T * T), c / T, d


def BezierToTrajectoryString(Tv, p0v, p1v, p2v, p3v):
    nchunks = len(Tv)
    dimension = len(p0v[0])
    trajectorystring = ""
    for i in range(nchunks):
        if i > 0:
            trajectorystring += "\n"
        trajectorystring += str(Tv[i]) + "\n" + str(dimension)
        for j in range(dimension):
            a, b, c, d = BezierToPolynomial(Tv[i], p0v[i][j], p1v[i][j],
                                            p2v[i][j], p3v[i][j])
            trajectorystring += "\n%f %f %f %f" % (d, c, b, a)
    return trajectorystring


################# Reading from string #####################

def ProfileFromLines(lines):
    l = lines[0]
    [duration, dt] = [double(x) for x in l.split(' ')]
    l = lines[1]
    sarray = array([double(x) for x in l.split(' ')])
    l = lines[2]
    sdarray = array([double(x) for x in l.split(' ')])
    return [duration, dt, sarray, sdarray]

def ProfilesFromString(s):
    s = s.strip(" \n")
    profileslist = []
    lines = [l.strip(" \n") for l in s.split('\n')]
    n = len(lines) / 3
    for i in range(n):
        profileslist.append(ProfileFromLines(lines[3 * i:3 * i + 3]))
    return profileslist

def ExtraFromString(s):
    s = s.strip(" \n")
    lines = [l.strip(" \n") for l in s.split('\n')]
    lines.pop(0)
    tvect = []
    torques = []
    for i in range(len(lines)/2):
        tvect.append(double(lines[2*i]))
        torques.append(array([double(x) for x in lines[2*i+1].split(' ')]))
    return array(tvect),array(torques)

def SwitchPointsFromString(s):
    if len(s) == 0:
        return []
    s = s.strip(" \n")
    switchpointslist = []
    lines = [l.strip(" \n") for l in s.split('\n')]
    for l in lines:
        switchpointslist.append(VectorFromString(l))
    return switchpointslist


def VectorFromString(s):
    # left for compatibility TODO: remove?
    s = s.strip(" \n")
    return array([double(x) for x in s.split(' ')])


def GenerateRandomTrajectory(ncurve,ndof,bound):    
    p0a = vector2string(rand(ndof)*2*bound-bound)
    p0b = vector2string(rand(ndof)*2*bound-bound)
    p1a = vector2string(rand(ndof)*2*bound-bound)
    p1b = vector2string(rand(ndof)*2*bound-bound)
    s = '%d'%ncurve
    s+= '\n1.0 ' + p0a + ' ' + p0b
    for k in range(ncurve-1):    
        a = rand(ndof)*2*bound-bound
        b = rand(ndof)*2*bound-bound
        c = 2*b-a
        pa = vector2string(a)
        pb = vector2string(b)
        pc = vector2string(c)
        s+= ' ' + pa + ' ' + pb + '\n1.0 ' + pb + ' ' + pc
    s+= ' ' + p1a + ' ' + p1b
    Tv,p0v,p1v,p2v,p3v = string2p(s)
    return BezierToTrajectoryString(Tv,p0v,p1v,p2v,p3v)


################# Compute constraints #####################

def ComputeKinematicConstraints(traj, amax, discrtimestep):
    # Sample the dynamics constraints
    ndiscrsteps = int((traj.duration + 1e-10) / discrtimestep) + 1
    constraintstring = ""
    for i in range(ndiscrsteps):
        t = i * discrtimestep
        qd = traj.Evald(t)
        qdd = traj.Evaldd(t)
        constraintstring += "\n" + vect2str(+qd) + " " + vect2str(-qd)
        constraintstring += "\n" + vect2str(+qdd) + " " + vect2str(-qdd)
        constraintstring += "\n" + vect2str(-amax) + " " + vect2str(-amax)
    return constraintstring


######################## Plots ############################

def PlotProfiles(profileslist0, switchpointslist=[], figstart=1):
    profileslist = list(profileslist0)
    figure(figstart)
    clf()
    hold('on')
    mvcbobrow = profileslist.pop(0)
    plot(mvcbobrow[2], mvcbobrow[3], 'm--', linewidth=4)
    mvcdirect = profileslist.pop(0)
    plot(mvcdirect[2], mvcdirect[3], 'c--', linewidth=4)
    colorcycle = ['r', 'g', 'b', 'y', 'k']
    ax = gca()
    ax.set_color_cycle(colorcycle)
    for p in profileslist:
        plot(p[2], p[3], linewidth=2)
    if len(profileslist) > 0:
        M = 2 * max([max(p[3]) for p in profileslist])
    else:
        M = 20
        bobrow = filter((lambda x: x < M), mvcbobrow[3])
        direct = filter((lambda x: x < M), mvcdirect[3])
        if len(bobrow) > 0:
            M = max(M, max(bobrow))
        if len(direct) > 0:
            M = max(M, max(direct))
    for sw in switchpointslist:
        if sw[2] == 0:
            plot(sw[0], sw[1], 'ro', markersize=8)
        if sw[2] == 1:
            plot(sw[0], sw[1], 'go', markersize=8)
        if sw[2] == 2:
            plot(sw[0], sw[1], 'bo', markersize=8)
        if sw[2] == 3:
            plot(sw[0], sw[1], 'yo', markersize=8)
    s_max, sd_max = mvcbobrow[0], M
    axis([0, s_max, 0, sd_max])
    title('Maximum Velocity Curves and profiles',fontsize=20)
    xlabel('$s$',fontsize=22)
    ylabel('$\dot s$',fontsize=22)
    return s_max, sd_max  # return this for PlotPhase (yurk!)


def PlotComputedProfiles(topp_bind, figstart=1):
    topp_bind.WriteProfilesList()
    topp_bind.WriteSwitchPointsList()
    profileslist = ProfilesFromString(topp_bind.resprofilesliststring)
    switchpointslist = SwitchPointsFromString(topp_bind.switchpointsliststring)
    PlotProfiles(profileslist, switchpointslist, figstart)


def PlotAlphaBeta(topp_inst, prec=30):
    smin, smax, sdmin, sdmax = axis()
    if sdmin <= 0.:
        sdmin = 1e-2
    s_coord = linspace(smin, smax, prec)
    sd_coord = linspace(sdmin, sdmax, prec)
    ds0 = s_coord[1] - s_coord[0]
    dsd0 = sd_coord[1] - sd_coord[0]
    nalpha = lambda s, sd: topp_inst.GetAlpha(s, sd) / sd
    nbeta = lambda s, sd: topp_inst.GetBeta(s, sd) / sd
    yscl = dsd0 / ds0
    for s in s_coord:
        for sd in sd_coord:
            ds = ds0 / 2
            a, b = nalpha(s, sd), nbeta(s, sd)
            na, nb = 1. / sqrt(1. + a ** 2), 1. / sqrt(1. + b ** 2)
            na = 1 / sqrt(1 + (a / yscl) ** 2)
            nb = 1 / sqrt(1 + (b / yscl) ** 2)
            plot([s, s + na * ds], [sd, sd + na * a * ds], 'b', alpha=.3)
            plot([s, s + nb * ds], [sd, sd + nb * b * ds], 'r', alpha=.3)
            if a > b:
                plot([s, s], [sd, sd], 'ko', alpha=.3, markersize=3)
    axis([smin, smax, sdmin, sdmax])


def PlotKinematics(traj0, traj1, dt=0.01, vmax=[], amax=[], figstart=0):
    colorcycle = ['r', 'g', 'b', 'm', 'c', 'y', 'k']
    colorcycle = colorcycle[0:traj0.dimension]
    Tmax = max(traj0.duration, traj1.duration)
    # Joint angles
    figure(figstart)
    clf()
    hold('on')
    ax = gca()
    ax.set_color_cycle(colorcycle)
    traj0.Plot(dt, '--')
    ax.set_color_cycle(colorcycle)
    traj1.Plot(dt)
    title('Joint values',fontsize=20)
    xlabel('Time (s)',fontsize=18)
    ylabel('Joint values (rad)',fontsize=18)
    # Velocity
    figure(figstart + 1)
    clf()
    hold('on')
    ax = gca()
    ax.set_color_cycle(colorcycle)
    traj0.Plotd(dt, '--')
    ax.set_color_cycle(colorcycle)
    traj1.Plotd(dt)
    for v in vmax:
        plot([0, Tmax], [v, v], '-.')
    for v in vmax:
        plot([0, Tmax], [-v, -v], '-.')
    if len(vmax) > 0:
        Vmax = 1.2 * max(vmax)
        if Vmax < 0.1:
            Vmax = 10
        axis([0, Tmax, -Vmax, Vmax])
    title('Joint velocities',fontsize=20)
    xlabel('Time (s)',fontsize=18)
    ylabel('Joint velocities (rad/s)',fontsize=18)
    # Acceleration
    figure(figstart + 2)
    clf()
    ax = gca()
    ax.set_color_cycle(colorcycle)
    hold('on')
    traj0.Plotdd(dt, '--')
    ax.set_color_cycle(colorcycle)
    traj1.Plotdd(dt)
    for a in amax:
        plot([0, Tmax], [a, a], '-.')
    for a in amax:
        plot([0, Tmax], [-a, -a], '-.')
    if len(amax) > 0:
        Amax = 1.2 * max(amax)
        axis([0, Tmax, -Amax, Amax])
    title('Joint accelerations',fontsize=20)
    xlabel('Time (s)',fontsize=18)
    ylabel('Joint accelerations (rad/s^2)',fontsize=18)


def string2p(s):
    lines = [l.strip(" \n") for l in s.split('\n')]
    Tv = []
    p0v = []
    p1v = []
    p2v = []
    p3v = []
    for i in range(1,len(lines)):
        l = [float(x) for x in lines[i].split(' ')]
        Tv.append(l.pop(0))
        ndof = int(l[0])
        p0v.append(l[1:ndof + 1])
        p1v.append(l[ndof + 2:2 * (ndof + 1)])
        p2v.append(l[2 * (ndof + 1) + 1:3 * (ndof + 1)])
        p3v.append(l[3 * (ndof + 1) + 1:4 * (ndof + 1)])
    return Tv, p0v, p1v, p2v, p3v


############################### (s, sd)-RRT ###################################

class __PhaseRRT(object):
    class Node(object):
        def __init__(self, s, sd, parent=None):
            self.s = s
            self.sd = sd
            self.parent = parent

    def __init__(self, topp_inst, traj, sd_beg_min, sd_beg_max, ds):
        sd_start = linspace(sd_beg_min, sd_beg_max, 42)
        self.topp_inst = topp_inst
        self.traj = traj
        self.ds = ds
        self.sd_beg_max = sd_beg_max
        self.nodes = [self.Node(0., sd) for sd in sd_start]
        self.end_node = None
        self.max_reached_s = 0.
        self.max_reached_sd = self.sd_beg_max

    def found_solution(self):
        return self.end_node is not None

    def plot_tree(self):
        cur_axis = pylab.axis()
        for node in self.nodes:
            s, sd = node.s, node.sd
            plot([s], [sd], 'bo')
            if node.parent:
                ps, psd = node.parent.s, node.parent.sd
                plot([ps, s], [psd, sd], 'g-', linewidth=1)
        pylab.axis(cur_axis)

    def plot_path(self, node):
        if node.parent:
            s, sd, ps, psd = node.s, node.sd, node.parent.s, node.parent.sd
            plot([ps, s], [psd, sd], 'r-', linewidth=3)
            return self.plot_path(node.parent)

    def plot_solution(self):
        cur_axis = pylab.axis()
        if self.end_node:
            self.plot_path(self.end_node)
        pylab.axis(cur_axis)

    def steer(self, node, target):
        """Returns True iff the steering reached the target."""
        interp_step = (target.sd - node.sd) / (target.s - node.s)
        interp_sd = lambda s: (s - node.s) * interp_step + node.sd
        for s in arange(node.s, target.s, self.ds):
            sd = interp_sd(s)
            alpha = self.topp_inst.GetAlpha(s, sd)
            beta = self.topp_inst.GetBeta(s, sd)
            # stepping condition is: alpha / sd <= sdd <= beta / sd
            if sd <= 0 or not (alpha <= interp_step * sd <= beta):
                return False
        return True

    def extend(self, target, k=10):
        from random import sample
        candidates = [node for node in self.nodes if node.s < target.s]
        if len(candidates) > k:
            candidates = sample(candidates, k)
        for candidate in candidates:
            if not self.steer(candidate, target):
                continue
            new_node = self.Node(target.s, target.sd, candidate)
            self.nodes.append(new_node)
            if target.s >= self.traj.duration:
                self.end_node = new_node
            if target.s > self.max_reached_s:
                self.max_reached_s = target.s
            if target.sd > 0.75 * self.max_reached_sd:
                self.max_reached_sd *= 1.25

    def run(self, max_nodes, time_budget):
        """Runs until the time budget is exhausted."""
        smax = self.traj.duration
        svar = smax / 10.
        start_time = time.time()
        while not self.found_solution():
            if len(self.nodes) > max_nodes \
               or time.time() - start_time > time_budget:
                break
            if pylab.random() < 0.1:
                s = pylab.random() * self.traj.duration
            else:
                s = pylab.normal(.5 * (smax + self.max_reached_s), svar)
                s = max(0., min(smax, s))
            sd = pylab.random() * self.max_reached_sd
            self.extend(self.Node(s, sd))
            if sd < self.max_reached_sd / 10:  # happens 1/10 times
                sd_end = pylab.random() * self.max_reached_sd
                self.extend(self.Node(smax, sd_end))
        print "RRT run time: %d s" % int(time.time() - start_time)


def TryRRT(topp_inst, traj, sd_beg_min, sd_beg_max, ds=1e-3, max_nodes=500,
           time_budget=360):
    rrt = __PhaseRRT(topp_inst, traj, sd_beg_min, sd_beg_max, ds)
    rrt.run(max_nodes, time_budget)
    return rrt